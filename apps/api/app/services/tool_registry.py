from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from ..schemas import (
    AgentProfile,
    ContactProfile,
    RealtimeSession,
    ToolExecutionRecord,
    ToolExecutionStatus,
    ToolIntegration,
    ToolIntegrationInput,
    ToolKind,
)
from .runtime_config import RuntimeConfigStore


class ToolRegistry:
    def __init__(self, runtime_config: RuntimeConfigStore) -> None:
        self.runtime_config = runtime_config
        self._integrations: dict[str, ToolIntegration] = {}
        self._history: list[ToolExecutionRecord] = []
        self._seed_integrations()

    def _seed_integrations(self) -> None:
        seeded = [
            ToolIntegration(
                tool_id="tool-crm-fabric",
                name="CRM Fabric",
                kind=ToolKind.CRM,
                description="Creates CRM notes and pulls contact context for the operator console.",
                mapped_functions=["lookup_contact", "create_crm_note"],
                simulator_response="Stored a CRM note and refreshed the caller context.",
            ),
            ToolIntegration(
                tool_id="tool-schedule-orchestrator",
                name="Schedule Orchestrator",
                kind=ToolKind.CALENDAR,
                description="Books callbacks, confirms appointments, and reschedules live follow-ups.",
                mapped_functions=["book_callback", "reschedule_appointment", "confirm_booking"],
                simulator_response="Queued a callback slot and marked the booking workflow for confirmation.",
            ),
            ToolIntegration(
                tool_id="tool-messaging-hub",
                name="Messaging Hub",
                kind=ToolKind.SMS,
                description="Sends post-call recap messages and reminder summaries.",
                mapped_functions=["send_sms_summary"],
                simulator_response="Prepared a concise SMS summary for the caller.",
            ),
            ToolIntegration(
                tool_id="tool-handoff-desk",
                name="Human Handoff Desk",
                kind=ToolKind.HANDOFF,
                description="Escalates a call to a human queue with transcript context.",
                mapped_functions=["escalate_human"],
                simulator_response="Queued the conversation for a human follow-up queue.",
            ),
            ToolIntegration(
                tool_id="tool-webhook-router",
                name="Webhook Router",
                kind=ToolKind.WEBHOOK,
                description="Dispatches custom business actions to an external webhook endpoint.",
                enabled=False,
                requires_network=True,
                mapped_functions=["post_custom_webhook"],
                simulator_response="Custom webhook router is disabled until you configure an endpoint.",
            ),
        ]
        self._integrations = {integration.tool_id: integration for integration in seeded}

    def list_integrations(self) -> list[ToolIntegration]:
        return sorted(self._integrations.values(), key=lambda item: item.name)

    def list_history(self, limit: int = 40) -> list[ToolExecutionRecord]:
        return list(reversed(self._history[-limit:]))

    def create_integration(self, request: ToolIntegrationInput) -> ToolIntegration:
        tool_id = f"tool-{uuid.uuid4().hex[:10]}"
        integration = ToolIntegration(
            tool_id=tool_id,
            name=request.name,
            kind=request.kind,
            description=request.description,
            enabled=request.enabled,
            requires_network=bool(request.endpoint_url),
            endpoint_url=request.endpoint_url,
            http_method=request.http_method,
            auth_profile_id=request.auth_profile_id,
            mapped_functions=request.mapped_functions,
            static_headers=request.static_headers,
            expected_fields=request.expected_fields,
            simulator_response=request.simulator_response,
        )
        self._integrations[tool_id] = integration
        return integration

    def get_integration(self, tool_id: str) -> ToolIntegration:
        return self._integrations[tool_id]

    def get_integration_for_function(self, function_name: str) -> ToolIntegration | None:
        for integration in self._integrations.values():
            if function_name in integration.mapped_functions:
                return integration
        return None

    def _build_payload(
        self,
        session: RealtimeSession | None,
        reason: str,
        arguments: dict[str, Any],
        tool_name: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "reason": reason,
            "arguments": arguments,
        }
        if session:
            payload["session"] = {
                "session_id": session.session_id,
                "contact_id": session.contact.id,
                "contact_name": session.contact.full_name,
                "organization": session.contact.organization,
                "agent_profile_id": session.agent_profile.id,
                "agent_name": session.agent_profile.name,
                "latest_reply": session.latest_reply,
                "state": session.state.value,
            }
        return payload

    def _build_auth_headers(self, integration: ToolIntegration) -> dict[str, str]:
        headers = dict(integration.static_headers)
        if not integration.auth_profile_id:
            return headers
        profile = self.runtime_config.get_profile_payload(integration.auth_profile_id)
        api_key = profile.get("api_key")
        if api_key:
            headers.setdefault("Authorization", f"Bearer {api_key}")
        return headers

    def _record(
        self,
        session: RealtimeSession | None,
        integration: ToolIntegration,
        tool_name: str,
        reason: str,
        arguments: dict[str, Any],
        status: ToolExecutionStatus,
        output_payload: dict[str, Any],
    ) -> ToolExecutionRecord:
        record = ToolExecutionRecord(
            execution_id=f"exec-{uuid.uuid4().hex[:10]}",
            tool_id=integration.tool_id,
            tool_name=tool_name,
            status=status,
            reason=reason,
            session_id=session.session_id if session else None,
            input_payload=arguments,
            output_payload=output_payload,
        )
        integration.last_result_summary = output_payload.get("summary", status.value)
        self._history.append(record)
        if len(self._history) > 120:
            self._history = self._history[-120:]

        if session:
            session.tool_executions.append(record)
            if len(session.tool_executions) > 20:
                session.tool_executions = session.tool_executions[-20:]
            session.runtime.last_tool_name = tool_name
            session.runtime.last_tool_arguments = json.dumps(arguments)
            session.runtime.last_tool_status = status
            session.runtime.last_tool_result = output_payload.get("summary")
            session.runtime.tool_execution_count += 1

        return record

    def _simulate_output(
        self,
        integration: ToolIntegration,
        tool_name: str,
        reason: str,
        arguments: dict[str, Any],
        session: RealtimeSession | None,
    ) -> dict[str, Any]:
        if tool_name == "lookup_contact" and session:
            return {
                "mode": "simulated",
                "summary": f"Loaded context for {session.contact.full_name} at {session.contact.organization}.",
                "contact": session.contact.model_dump(),
            }
        if tool_name in {"book_callback", "reschedule_appointment", "confirm_booking"} and session:
            requested_slot = arguments.get("time_window") or "next available afternoon slot"
            return {
                "mode": "simulated",
                "summary": f"Reserved {requested_slot} for {session.contact.full_name}.",
                "booking": {
                    "status": "queued",
                    "time_window": requested_slot,
                    "agent": session.agent_profile.name,
                },
            }
        if tool_name == "send_sms_summary" and session:
            return {
                "mode": "simulated",
                "summary": f"Prepared an SMS summary for {session.contact.phone}.",
                "message_preview": f"{session.agent_profile.name}: {reason}",
            }
        if tool_name == "escalate_human" and session:
            return {
                "mode": "simulated",
                "summary": f"Escalated {session.contact.full_name} to the human callback queue.",
                "handoff": {
                    "priority": "high",
                    "owner": "sales-ops",
                },
            }
        if tool_name == "create_crm_note" and session:
            return {
                "mode": "simulated",
                "summary": f"Stored a CRM note for {session.contact.full_name}.",
                "note": reason,
            }

        return {
            "mode": "simulated",
            "summary": integration.simulator_response or f"Simulated execution for {tool_name}.",
            "reason": reason,
            "arguments": arguments,
        }

    def execute(
        self,
        tool_name: str,
        reason: str,
        arguments: dict[str, Any],
        session: RealtimeSession | None = None,
    ) -> ToolExecutionRecord:
        integration = self.get_integration_for_function(tool_name)
        if not integration:
            fallback = ToolIntegration(
                tool_id="tool-missing",
                name="Missing Integration",
                kind=ToolKind.WEBHOOK,
                description="No mapped integration found.",
                enabled=False,
                mapped_functions=[],
                simulator_response="No integration configured.",
            )
            return self._record(
                session,
                fallback,
                tool_name,
                reason,
                arguments,
                ToolExecutionStatus.SKIPPED,
                {"summary": f"No integration is mapped to {tool_name}."},
            )

        if not integration.enabled:
            return self._record(
                session,
                integration,
                tool_name,
                reason,
                arguments,
                ToolExecutionStatus.SKIPPED,
                {"summary": f"{integration.name} is disabled until an operator enables it."},
            )

        if not integration.endpoint_url:
            return self._record(
                session,
                integration,
                tool_name,
                reason,
                arguments,
                ToolExecutionStatus.SIMULATED,
                self._simulate_output(integration, tool_name, reason, arguments, session),
            )

        payload = self._build_payload(session, reason, arguments, tool_name)
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.request(
                    integration.http_method,
                    integration.endpoint_url,
                    headers=self._build_auth_headers(integration),
                    json=payload,
                )
                response.raise_for_status()
                output_payload: dict[str, Any] = {
                    "mode": "webhook",
                    "status_code": response.status_code,
                    "summary": f"{integration.name} accepted {tool_name} via {integration.http_method}.",
                }
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    output_payload["response"] = response.json()
                else:
                    output_payload["response_text"] = response.text[:400]
                return self._record(
                    session,
                    integration,
                    tool_name,
                    reason,
                    arguments,
                    ToolExecutionStatus.COMPLETED,
                    output_payload,
                )
        except Exception as exc:
            return self._record(
                session,
                integration,
                tool_name,
                reason,
                arguments,
                ToolExecutionStatus.ERROR,
                {"summary": f"{integration.name} failed: {exc}", "error": str(exc)},
            )

    async def execute_async(
        self,
        tool_name: str,
        reason: str,
        arguments: dict[str, Any],
        session: RealtimeSession | None = None,
    ) -> ToolExecutionRecord:
        integration = self.get_integration_for_function(tool_name)
        if not integration or not integration.endpoint_url or not integration.enabled:
            return self.execute(tool_name, reason, arguments, session)

        payload = self._build_payload(session, reason, arguments, tool_name)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    integration.http_method,
                    integration.endpoint_url,
                    headers=self._build_auth_headers(integration),
                    json=payload,
                )
                response.raise_for_status()
                output_payload: dict[str, Any] = {
                    "mode": "webhook",
                    "status_code": response.status_code,
                    "summary": f"{integration.name} accepted {tool_name} via {integration.http_method}.",
                }
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    output_payload["response"] = response.json()
                else:
                    output_payload["response_text"] = response.text[:400]
                return self._record(
                    session,
                    integration,
                    tool_name,
                    reason,
                    arguments,
                    ToolExecutionStatus.COMPLETED,
                    output_payload,
                )
        except Exception as exc:
            return self._record(
                session,
                integration,
                tool_name,
                reason,
                arguments,
                ToolExecutionStatus.ERROR,
                {"summary": f"{integration.name} failed: {exc}", "error": str(exc)},
            )

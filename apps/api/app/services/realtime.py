from __future__ import annotations

from ..config import settings
from ..schemas import (
    AgentProfile,
    AgentReply,
    ContactProfile,
    ProviderName,
    RealtimeSession,
    RealtimeTrace,
    SessionState,
    ToolIntegration,
)
from .compliance import evaluate_compliance


class RealtimeOrchestrator:
    def build_websocket_path(self, session_id: str) -> str:
        return f"/twilio/media-stream/{session_id}"

    def build_opening_line(self, contact: ContactProfile, agent_profile: AgentProfile) -> str:
        return (
            f"{settings.disclosure_line} "
            f"I'm the {agent_profile.name} voice assistant for {contact.organization}, "
            f"calling about {contact.use_case}. Is now an okay time for a quick update?"
        )

    def build_turn_detection(self) -> dict[str, object]:
        if settings.openai_turn_detection_mode == "semantic_vad":
            return {
                "type": "semantic_vad",
                "create_response": settings.openai_turn_create_response,
                "interrupt_response": settings.openai_turn_interrupt_response,
                "eagerness": settings.openai_semantic_eagerness,
            }

        return {
            "type": "server_vad",
            "create_response": settings.openai_turn_create_response,
            "interrupt_response": settings.openai_turn_interrupt_response,
            "idle_timeout_ms": settings.openai_idle_timeout_ms,
            "prefix_padding_ms": settings.openai_vad_prefix_padding_ms,
            "silence_duration_ms": settings.openai_vad_silence_duration_ms,
            "threshold": settings.openai_vad_threshold,
        }

    def build_session_template(
        self,
        contact: ContactProfile,
        agent_profile: AgentProfile,
        model: str | None = None,
        tool_catalog: list[ToolIntegration] | None = None,
    ) -> dict[str, object]:
        tool_catalog = tool_catalog or []
        tool_lookup = {
            function_name: integration
            for integration in tool_catalog
            for function_name in integration.mapped_functions
        }
        session: dict[str, object] = {
            "type": "realtime",
            "model": model or settings.openai_realtime_model,
            "instructions": (
                f"You are {agent_profile.name}, a realtime phone agent for {contact.organization}. "
                f"Goal: {agent_profile.goal} "
                "Always identify yourself as an AI voice assistant, remain concise, verify intent, "
                "avoid unsupported promises, and call tools instead of pretending work is complete. "
                "If a tool is available for booking, CRM updates, messaging, or escalation, prefer using it."
            ),
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": settings.openai_input_audio_format,
                    "noise_reduction": {"type": settings.openai_input_noise_reduction},
                    "transcription": {
                        "model": settings.openai_transcription_model,
                        "language": settings.openai_transcription_language,
                    },
                    "turn_detection": self.build_turn_detection(),
                },
                "output": {
                    "format": settings.openai_output_audio_format,
                    "voice": agent_profile.voice or settings.openai_voice,
                    "speed": settings.openai_output_speed,
                },
            },
            "max_output_tokens": settings.openai_max_output_tokens,
            "tools": [
                {
                    "type": "function",
                    "name": tool_name,
                    "description": (
                        tool_lookup[tool_name].description
                        if tool_name in tool_lookup
                        else f"Invoke the {tool_name} business workflow."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"},
                            "contact_id": {"type": "string"},
                            "time_window": {"type": "string"},
                        },
                        "required": ["reason"],
                        "additionalProperties": False,
                    },
                }
                for tool_name in agent_profile.tool_stack
            ],
            "tool_choice": "auto",
        }
        if settings.openai_tracing_mode and settings.openai_tracing_mode != "off":
            session["tracing"] = settings.openai_tracing_mode

        return {"type": "session.update", "session": session}

    def next_turn(self, session: RealtimeSession, caller_text: str) -> AgentReply:
        transcript = [turn.model_dump() for turn in session.turns]
        compliance = evaluate_compliance(session.contact, transcript, caller_text)
        session.compliance = compliance

        if not compliance.allowed:
            return AgentReply(
                reply="Understood. I will stop the call and mark this contact accordingly.",
                next_state=SessionState.BLOCKED,
                disposition="stop",
                confidence=1.0,
                tool_suggestion="create_crm_note",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.LOCAL,
                        model="local-policy-engine",
                        event="policy.blocked",
                        confidence=1.0,
                        detail=", ".join(compliance.reasons) or "Policy engine blocked the turn.",
                        used_fallback=False,
                    )
                ],
            )

        normalized = caller_text.lower().strip()
        first_name = session.contact.full_name.split()[0]

        if any(token in normalized for token in ["schedule", "book", "callback", "tomorrow", "later"]):
            suggested_tool = (
                "reschedule_appointment"
                if "reschedule_appointment" in session.agent_profile.tool_stack
                else "book_callback"
            )
            return AgentReply(
                reply=(
                    f"Absolutely. I can queue the next step for {first_name}. "
                    "What time window should I hold for you?"
                ),
                next_state=SessionState.FOLLOW_UP,
                disposition="schedule",
                confidence=0.9,
                tool_suggestion=suggested_tool,
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="response.create",
                        confidence=0.9,
                        detail="Realtime agent detected explicit scheduling or rescheduling intent.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        if any(token in normalized for token in ["cancel", "remove appointment", "skip it"]):
            return AgentReply(
                reply="I can note the cancellation request and send a short confirmation summary to the team.",
                next_state=SessionState.COMPLETED,
                disposition="continue",
                confidence=0.84,
                tool_suggestion="send_sms_summary",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="response.create",
                        confidence=0.84,
                        detail="Realtime agent identified cancellation-style intent.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        if any(token in normalized for token in ["human", "agent", "person", "representative"]):
            return AgentReply(
                reply="I can hand this over to a human teammate and attach a summary so you do not need to repeat yourself.",
                next_state=SessionState.HANDOFF,
                disposition="handoff",
                confidence=0.94,
                tool_suggestion="escalate_human",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="tool.plan",
                        confidence=0.94,
                        detail="Realtime agent prepared a human handoff.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        if any(token in normalized for token in ["price", "cost", "quote", "roi"]):
            return AgentReply(
                reply=(
                    "I can give a concise overview first and then line up a human follow-up for exact pricing. "
                    "Is a quick summary or a booked callback better for you?"
                ),
                next_state=SessionState.LIVE,
                disposition="continue",
                confidence=0.81,
                tool_suggestion="lookup_contact",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="response.create",
                        confidence=0.81,
                        detail="Realtime assistant detected pricing sensitivity and shifted to summary-plus-follow-up mode.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        if any(token in normalized for token in ["yes", "okay", "sure", "go ahead", "interested"]):
            return AgentReply(
                reply=(
                    f"Great. For {session.contact.use_case}, is your priority speed, cost, "
                    "or a better long-term experience?"
                ),
                next_state=SessionState.LIVE,
                disposition="continue",
                confidence=0.83,
                tool_suggestion="lookup_contact",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="response.create",
                        confidence=0.83,
                        detail="Realtime follow-up question generated from positive engagement.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        return AgentReply(
            reply=(
                "No problem. I can keep it to a 15-second summary, schedule a better time, "
                "or stop here if that is better for you."
            ),
            next_state=SessionState.LIVE,
            disposition="continue",
            confidence=0.74,
            tool_suggestion="create_crm_note",
            trace=[
                RealtimeTrace(
                    provider=ProviderName.OPENAI,
                    model=settings.openai_realtime_model,
                    event="response.create",
                    confidence=0.74,
                    detail="Realtime assistant generated a low-pressure clarification turn.",
                    used_fallback=not bool(settings.openai_api_key),
                )
            ],
        )

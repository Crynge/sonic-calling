from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket

from ..config import settings
from ..schemas import ConversationTurn, ProviderSurface, RealtimeSession, RuntimeHealth, StreamEvent
from .openai_transport import OpenAIRealtimeTransport
from .runtime_config import RuntimeConfigStore
from .tool_registry import ToolRegistry


class TwilioRealtimeBridge:
    def __init__(self, runtime_config: RuntimeConfigStore | None = None, tools: ToolRegistry | None = None) -> None:
        self.runtime_config = runtime_config or RuntimeConfigStore()
        self.tools = tools or ToolRegistry(self.runtime_config)
        self.transport = OpenAIRealtimeTransport()

    def resolve_realtime_credentials(self, profile_id: str | None = None) -> dict[str, Any]:
        return self.runtime_config.resolve_credentials(ProviderSurface.REALTIME, profile_id)

    @property
    def live_bridge_enabled(self) -> bool:
        return self.transport.enabled_for(self.resolve_realtime_credentials())

    def build_stream_url(self, session_id: str) -> str:
        base = settings.public_websocket_base.rstrip("/")
        if base.startswith("http://"):
            base = "ws://" + base.removeprefix("http://")
        elif base.startswith("https://"):
            base = "wss://" + base.removeprefix("https://")
        return f"{base}/twilio/media-stream/{session_id}"

    def build_runtime_health(self) -> RuntimeHealth:
        realtime_profile = self.runtime_config.resolve_provider_profile(ProviderSurface.REALTIME)
        telephony_profile = self.runtime_config.resolve_provider_profile(ProviderSurface.TELEPHONY)
        realtime_credentials = self.resolve_realtime_credentials()
        return RuntimeHealth(
            openai_api_configured=bool(self.transport.resolve_api_key(realtime_credentials)),
            twilio_credentials_configured=bool(
                telephony_profile
                and telephony_profile.ready
            ),
            live_bridge_enabled=self.transport.enabled_for(realtime_credentials),
            client_secret_enabled=self.transport.enabled_for(realtime_credentials),
            public_base_url=settings.public_base_url,
            public_websocket_base=settings.public_websocket_base,
            openai_websocket_url=self.transport.build_websocket_url(realtime_credentials),
            input_audio_format=settings.openai_input_audio_format,
            output_audio_format=settings.openai_output_audio_format,
            transcription_model=settings.openai_transcription_model,
            turn_detection_mode=settings.openai_turn_detection_mode,
            active_realtime_profile=realtime_profile.name if realtime_profile else None,
            active_telephony_profile=telephony_profile.name if telephony_profile else None,
            tool_integrations_enabled=sum(1 for item in self.tools.list_integrations() if item.enabled),
            byo_realtime_ready=bool(realtime_profile and realtime_profile.ready),
        )

    def normalize_twilio_message(self, raw_message: str) -> dict[str, Any]:
        payload = json.loads(raw_message)
        event = payload.get("event", "unknown")
        start = payload.get("start", {})
        stop = payload.get("stop", {})
        media = payload.get("media", {})
        mark = payload.get("mark", {})
        dtmf = payload.get("dtmf", {})
        return {
            "event": event,
            "streamSid": payload.get("streamSid") or start.get("streamSid"),
            "sequenceNumber": payload.get("sequenceNumber"),
            "start": start,
            "stop": stop,
            "media": media,
            "mark": mark,
            "dtmf": dtmf,
        }

    def build_openai_runtime_notes(self) -> dict[str, str]:
        profile = self.runtime_config.resolve_provider_profile(ProviderSurface.REALTIME)
        return {
            "provider": "openai",
            "model": profile.model if profile and profile.model else settings.openai_realtime_model,
            "voice": settings.openai_voice,
            "bridge_mode": "twilio-media-stream-to-openai-realtime",
        }

    def build_openai_audio_append_event(self, payload: str) -> dict[str, Any]:
        return {
            "type": "input_audio_buffer.append",
            "audio": payload,
        }

    def build_twilio_media_event(self, stream_sid: str, payload: str) -> dict[str, Any]:
        return {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": payload,
            },
        }

    def build_twilio_mark_event(self, stream_sid: str, name: str) -> dict[str, Any]:
        return {
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {"name": name},
        }

    def build_twilio_clear_event(self, stream_sid: str) -> dict[str, Any]:
        return {
            "event": "clear",
            "streamSid": stream_sid,
        }

    def preview_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        preview: dict[str, Any] = {}
        for key in ("streamSid", "sequenceNumber", "event", "type"):
            if key in payload:
                preview[key] = payload[key]
        if "media" in payload and isinstance(payload["media"], dict):
            preview["media"] = {
                "track": payload["media"].get("track"),
                "chunk": payload["media"].get("chunk"),
                "timestamp": payload["media"].get("timestamp"),
                "payload_bytes": len(payload["media"].get("payload", "")),
            }
        if "response" in payload and isinstance(payload["response"], dict):
            preview["response"] = {
                "id": payload["response"].get("id"),
                "status": payload["response"].get("status"),
            }
        if "error" in payload and isinstance(payload["error"], dict):
            preview["error"] = {
                "type": payload["error"].get("type"),
                "message": payload["error"].get("message"),
            }
        return preview

    def append_event(
        self,
        session: RealtimeSession,
        source: str,
        event: str,
        detail: str,
        payload_preview: dict[str, Any] | None = None,
    ) -> None:
        session.events.append(
            StreamEvent(
                source=source,
                event=event,
                detail=detail,
                payload_preview=payload_preview or {},
            )
        )
        if len(session.events) > 80:
            session.events = session.events[-80:]

    def apply_twilio_event(self, session: RealtimeSession, normalized: dict[str, Any]) -> None:
        session.runtime.twilio_event_count += 1
        event = normalized["event"]

        if normalized.get("streamSid"):
            session.runtime.stream_sid = normalized["streamSid"]

        if event == "connected":
            session.runtime.bridge_status = "connecting"
            self.append_event(session, "twilio", event, "Twilio websocket connected.", self.preview_payload(normalized))
            return

        if event == "start":
            start = normalized.get("start", {})
            session.runtime.bridge_status = "streaming"
            session.runtime.call_sid = start.get("callSid")
            self.append_event(
                session,
                "twilio",
                event,
                "Bidirectional media stream started.",
                {
                    "streamSid": normalized.get("streamSid"),
                    "callSid": start.get("callSid"),
                    "tracks": start.get("tracks"),
                    "mediaFormat": start.get("mediaFormat"),
                    "customParameters": start.get("customParameters"),
                },
            )
            return

        if event == "media":
            media = normalized.get("media", {})
            self.append_event(
                session,
                "twilio",
                event,
                "Inbound caller audio chunk received.",
                {
                    "streamSid": normalized.get("streamSid"),
                    "track": media.get("track"),
                    "chunk": media.get("chunk"),
                    "timestamp": media.get("timestamp"),
                    "payload_bytes": len(media.get("payload", "")),
                },
            )
            return

        if event == "dtmf":
            digit = normalized.get("dtmf", {}).get("digit")
            self.append_event(session, "twilio", event, f"Caller sent DTMF digit {digit}.", self.preview_payload(normalized))
            return

        if event == "mark":
            name = normalized.get("mark", {}).get("name")
            session.runtime.latest_mark = name
            self.append_event(session, "twilio", event, f"Twilio acknowledged playback mark {name}.", self.preview_payload(normalized))
            return

        if event == "stop":
            session.runtime.bridge_status = "closed"
            self.append_event(session, "twilio", event, "Twilio stream stopped or call ended.", self.preview_payload(normalized))
            return

        self.append_event(session, "twilio", event, "Unhandled Twilio event received.", self.preview_payload(normalized))

    def apply_openai_event(self, session: RealtimeSession, payload: dict[str, Any]) -> None:
        session.runtime.openai_event_count += 1
        event_type = payload.get("type", "unknown")

        if event_type in {"session.created", "session.updated"}:
            session.runtime.bridge_mode = "openai_realtime"
            session.runtime.bridge_status = "streaming"
            self.append_event(session, "openai", event_type, "OpenAI realtime session acknowledged.", self.preview_payload(payload))
            return

        if event_type == "response.created":
            response = payload.get("response", {})
            session.runtime.openai_response_id = response.get("id")
            self.append_event(session, "openai", event_type, "Assistant response started streaming.", self.preview_payload(payload))
            return

        if event_type == "conversation.item.input_audio_transcription.completed":
            transcript = payload.get("transcript", "")
            session.runtime.last_input_transcript = transcript
            if transcript:
                session.turns.append(ConversationTurn(speaker="caller", text=transcript))
            self.append_event(session, "openai", event_type, "Input audio transcription completed.", {"transcript": transcript[:180]})
            return

        if event_type == "response.output_audio_transcript.delta":
            session.runtime.last_output_transcript += payload.get("delta", "")
            return

        if event_type == "response.output_audio_transcript.done":
            transcript = payload.get("transcript", "") or session.runtime.last_output_transcript
            session.runtime.last_output_transcript = transcript
            if transcript:
                session.turns.append(ConversationTurn(speaker="agent", text=transcript))
                session.latest_reply = transcript
            self.append_event(session, "openai", event_type, "Assistant transcript completed.", {"transcript": transcript[:180]})
            return

        if event_type == "response.function_call_arguments.done":
            session.runtime.last_tool_name = payload.get("name")
            session.runtime.last_tool_arguments = payload.get("arguments")
            session.summary_note = payload.get("name", "")
            self.append_event(
                session,
                "openai",
                event_type,
                "Function call arguments completed.",
                {
                    "name": payload.get("name"),
                    "call_id": payload.get("call_id"),
                    "arguments": payload.get("arguments", "")[:200],
                },
            )
            return

        if event_type == "response.done":
            response = payload.get("response", {})
            session.latest_disposition = response.get("status", session.latest_disposition)
            self.append_event(session, "openai", event_type, "Assistant response finished.", self.preview_payload(payload))
            return

        if event_type == "error":
            error = payload.get("error", {})
            session.runtime.bridge_status = "error"
            session.runtime.last_error = error.get("message", "Unknown OpenAI realtime error.")
            self.append_event(session, "openai", event_type, "OpenAI realtime error received.", self.preview_payload(payload))
            return

        self.append_event(session, "openai", event_type, "OpenAI realtime event observed.", self.preview_payload(payload))

    async def run_simulated_capture(self, websocket: WebSocket, session: RealtimeSession) -> None:
        self.append_event(
            session,
            "system",
            "bridge.simulated",
            "Running in simulator-only mode because no ready BYO Realtime profile is active.",
        )
        try:
            while True:
                message = await websocket.receive_text()
                normalized = self.normalize_twilio_message(message)
                self.apply_twilio_event(session, normalized)
                if normalized["event"] == "stop":
                    break
        except Exception as exc:  # pragma: no cover - websocket disconnect path
            session.runtime.last_error = str(exc)
            session.runtime.bridge_status = "error"
            self.append_event(session, "system", "bridge.error", "Simulated bridge encountered an exception.", {"error": str(exc)})

    async def bridge_live_audio(
        self,
        twilio_websocket: WebSocket,
        session: RealtimeSession,
        session_template: dict[str, Any],
    ) -> None:
        session.runtime.bridge_mode = "openai_realtime"
        session.runtime.bridge_status = "connecting"
        self.append_event(session, "system", "bridge.connecting", "Connecting Twilio media stream to OpenAI Realtime.")

        realtime_credentials = self.resolve_realtime_credentials(session.provider_profile_id)
        openai_socket = await self.transport.open_websocket(realtime_credentials)
        try:
            await openai_socket.send(json.dumps(session_template))
            self.append_event(session, "system", "session.update.sent", "Sent session bootstrap to OpenAI Realtime.")

            inbound = asyncio.create_task(self._forward_twilio_to_openai(twilio_websocket, openai_socket, session))
            outbound = asyncio.create_task(self._forward_openai_to_twilio(twilio_websocket, openai_socket, session))
            done, pending = await asyncio.wait({inbound, outbound}, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            for task in done:
                exception = task.exception()
                if exception:
                    raise exception
        finally:
            session.runtime.bridge_status = "closed" if session.runtime.bridge_status != "error" else "error"
            await openai_socket.close()
            self.append_event(session, "system", "bridge.closed", "Closed OpenAI realtime transport.")

    async def _forward_twilio_to_openai(self, twilio_websocket: WebSocket, openai_socket, session: RealtimeSession) -> None:
        while True:
            message = await twilio_websocket.receive_text()
            normalized = self.normalize_twilio_message(message)
            self.apply_twilio_event(session, normalized)

            if normalized["event"] == "media":
                media_payload = normalized.get("media", {}).get("payload")
                if media_payload:
                    await openai_socket.send(json.dumps(self.build_openai_audio_append_event(media_payload)))
                continue

            if normalized["event"] == "stop":
                break

    async def _handle_realtime_tool_call(self, openai_socket, session: RealtimeSession, payload: dict[str, Any]) -> None:
        tool_name = payload.get("name") or "unknown_tool"
        raw_arguments = payload.get("arguments", "{}")
        try:
            arguments = json.loads(raw_arguments) if raw_arguments else {}
        except json.JSONDecodeError:
            arguments = {"raw_arguments": raw_arguments}
        reason = arguments.get("reason") or f"Realtime tool call for {tool_name}"
        record = await self.tools.execute_async(tool_name, reason, arguments, session)
        self.append_event(
            session,
            "tool",
            "tool.execution",
            f"Executed {tool_name} with status {record.status.value}.",
            {
                "tool_name": tool_name,
                "status": record.status.value,
                "call_id": payload.get("call_id"),
            },
        )
        if payload.get("call_id"):
            await openai_socket.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": payload["call_id"],
                            "output": json.dumps(record.output_payload),
                        },
                    }
                )
            )
            await openai_socket.send(json.dumps({"type": "response.create"}))

    async def _forward_openai_to_twilio(self, twilio_websocket: WebSocket, openai_socket, session: RealtimeSession) -> None:
        async for raw_message in openai_socket:
            payload = json.loads(raw_message)
            self.apply_openai_event(session, payload)
            event_type = payload.get("type")

            if event_type == "response.function_call_arguments.done":
                await self._handle_realtime_tool_call(openai_socket, session, payload)
                continue

            if event_type == "response.output_audio.delta" and session.runtime.stream_sid:
                delta = payload.get("delta")
                if delta:
                    await twilio_websocket.send_text(
                        json.dumps(self.build_twilio_media_event(session.runtime.stream_sid, delta))
                    )
                continue

            if event_type == "response.output_audio.done" and session.runtime.stream_sid:
                response_id = session.runtime.openai_response_id or "assistant"
                mark_name = f"{response_id}-done"
                await twilio_websocket.send_text(
                    json.dumps(self.build_twilio_mark_event(session.runtime.stream_sid, mark_name))
                )
                continue

            if event_type == "input_audio_buffer.speech_started" and session.runtime.stream_sid:
                await twilio_websocket.send_text(json.dumps(self.build_twilio_clear_event(session.runtime.stream_sid)))

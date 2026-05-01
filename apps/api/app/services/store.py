from __future__ import annotations

import uuid

from ..config import settings
from ..schemas import (
    AgentProfile,
    ComplianceResult,
    ContactProfile,
    RealtimeSession,
    SessionRuntime,
    SessionState,
    StreamEvent,
)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, RealtimeSession] = {}

    def create(
        self,
        contact: ContactProfile,
        agent_profile: AgentProfile,
        compliance: ComplianceResult,
        websocket_path: str,
        provider_profile_id: str | None = None,
        telephony_profile_id: str | None = None,
        live_bridge_enabled: bool | None = None,
    ) -> RealtimeSession:
        bridge_mode = "openai_realtime" if live_bridge_enabled else "simulated"
        session = RealtimeSession(
            session_id=f"session-{uuid.uuid4().hex[:10]}",
            contact=contact,
            agent_profile=agent_profile,
            state=SessionState.READY,
            started=False,
            turns=[],
            trace=[],
            events=[],
            runtime=SessionRuntime(
                bridge_mode=bridge_mode,
                bridge_status="idle",
                input_audio_format=settings.openai_input_audio_format,
                output_audio_format=settings.openai_output_audio_format,
                provider_profile_id=provider_profile_id,
                telephony_profile_id=telephony_profile_id,
            ),
            compliance=compliance,
            latest_reply="",
            websocket_path=websocket_path,
            provider_profile_id=provider_profile_id,
            telephony_profile_id=telephony_profile_id,
        )
        self._sessions[session.session_id] = session
        return session

    def list(self) -> list[RealtimeSession]:
        return sorted(self._sessions.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, session_id: str) -> RealtimeSession:
        return self._sessions[session_id]

    def save(self, session: RealtimeSession) -> RealtimeSession:
        self._sessions[session.session_id] = session
        return session

    def append_event(self, session: RealtimeSession, event: StreamEvent) -> RealtimeSession:
        session.events.append(event)
        if len(session.events) > 80:
            session.events = session.events[-80:]
        self.save(session)
        return session

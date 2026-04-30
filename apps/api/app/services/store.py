from __future__ import annotations

import uuid
from ..schemas import AgentProfile, ComplianceResult, ContactProfile, RealtimeSession, SessionState


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, RealtimeSession] = {}

    def create(
        self,
        contact: ContactProfile,
        agent_profile: AgentProfile,
        compliance: ComplianceResult,
        websocket_path: str,
    ) -> RealtimeSession:
        session = RealtimeSession(
            session_id=f"session-{uuid.uuid4().hex[:10]}",
            contact=contact,
            agent_profile=agent_profile,
            state=SessionState.READY,
            started=False,
            turns=[],
            trace=[],
            compliance=compliance,
            latest_reply="",
            websocket_path=websocket_path,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> RealtimeSession:
        return self._sessions[session_id]

    def save(self, session: RealtimeSession) -> RealtimeSession:
        self._sessions[session.session_id] = session
        return session

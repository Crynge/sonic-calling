from apps.api.app.data import get_agent_profile, get_contact
from apps.api.app.schemas import ComplianceResult, ConversationTurn, RealtimeSession, SessionState
from apps.api.app.services.realtime import RealtimeOrchestrator


def build_session(contact_id: str, agent_profile_id: str = "agent-sales") -> RealtimeSession:
    return RealtimeSession(
        session_id="session-test",
        contact=get_contact(contact_id),
        agent_profile=get_agent_profile(agent_profile_id),
        state=SessionState.READY,
        started=True,
        turns=[
            ConversationTurn(
                speaker="agent",
                text="Hi, this is the Sonic Calling AI assistant from Sonic Calling Labs on a recorded call.",
            )
        ],
        compliance=ComplianceResult(allowed=True, risk_level="low"),
        websocket_path="/twilio/media-stream/session-test",
    )


def test_dnc_contact_blocks_immediately() -> None:
    session = build_session("contact-003")
    orchestrator = RealtimeOrchestrator()
    reply = orchestrator.next_turn(session, "hello")
    assert reply.disposition == "stop"
    assert reply.next_state == SessionState.BLOCKED


def test_realtime_scheduler_path() -> None:
    session = build_session("contact-001", "agent-reminder")
    orchestrator = RealtimeOrchestrator()
    reply = orchestrator.next_turn(session, "Can you schedule me tomorrow morning?")
    assert reply.disposition == "schedule"
    assert reply.trace[0].provider.value == "openai"


def test_realtime_handoff_path() -> None:
    session = build_session("contact-002", "agent-sales")
    orchestrator = RealtimeOrchestrator()
    reply = orchestrator.next_turn(session, "I want to speak to a human representative.")
    assert reply.disposition == "handoff"
    assert reply.next_state == SessionState.HANDOFF

from apps.api.app.data import get_agent_profile, get_contact
from apps.api.app.schemas import ComplianceResult
from apps.api.app.services.realtime_bridge import TwilioRealtimeBridge
from apps.api.app.services.store import SessionStore


def build_session():
    store = SessionStore()
    return store.create(
        contact=get_contact("contact-001"),
        agent_profile=get_agent_profile("agent-sales"),
        compliance=ComplianceResult(allowed=True, risk_level="low"),
        websocket_path="/twilio/media-stream/test",
    )


def test_twilio_start_event_updates_runtime() -> None:
    session = build_session()
    bridge = TwilioRealtimeBridge()
    normalized = bridge.normalize_twilio_message(
        '{"event":"start","sequenceNumber":"1","start":{"callSid":"CA123","streamSid":"MZ123","tracks":["inbound"],"mediaFormat":{"encoding":"audio/x-mulaw","sampleRate":8000,"channels":1},"customParameters":{"session_id":"abc"}},"streamSid":"MZ123"}'
    )
    bridge.apply_twilio_event(session, normalized)
    assert session.runtime.bridge_status == "streaming"
    assert session.runtime.call_sid == "CA123"
    assert session.runtime.stream_sid == "MZ123"


def test_openai_response_events_capture_transcript_and_tool() -> None:
    session = build_session()
    bridge = TwilioRealtimeBridge()
    bridge.apply_openai_event(session, {"type": "response.created", "response": {"id": "resp_123", "status": "in_progress"}})
    bridge.apply_openai_event(session, {"type": "response.output_audio_transcript.delta", "delta": "Hello there"})
    bridge.apply_openai_event(session, {"type": "response.output_audio_transcript.done", "transcript": "Hello there"})
    bridge.apply_openai_event(
        session,
        {
            "type": "response.function_call_arguments.done",
            "name": "book_callback",
            "arguments": '{"reason":"caller requested schedule"}',
        },
    )
    assert session.runtime.openai_response_id == "resp_123"
    assert session.runtime.last_output_transcript == "Hello there"
    assert session.runtime.last_tool_name == "book_callback"


def test_runtime_health_reports_live_bridge_disabled_without_key() -> None:
    bridge = TwilioRealtimeBridge()
    health = bridge.build_runtime_health()
    assert health.live_bridge_enabled is False
    assert health.input_audio_format == "g711_ulaw"

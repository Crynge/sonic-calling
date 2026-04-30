from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .data import AGENT_PROFILES, SAMPLE_CONTACTS, get_agent_profile, get_contact
from .schemas import (
    ConversationTurn,
    DashboardMetric,
    DashboardSummary,
    RespondRequest,
    SessionPlanResponse,
    SessionView,
    StartSessionRequest,
)
from .services.compliance import evaluate_compliance
from .services.realtime import RealtimeOrchestrator
from .services.realtime_bridge import TwilioRealtimeBridge
from .services.store import SessionStore
from .services.twilio_adapter import build_stream_twiml

app = FastAPI(title="Sonic Calling")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = SessionStore()
orchestrator = RealtimeOrchestrator()
bridge = TwilioRealtimeBridge()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    return DashboardSummary(
        repo_name="sonic-calling",
        narrative=(
            "A realtime developer platform for AI telephony that bridges Twilio voice streams "
            "into OpenAI Realtime sessions with tool-ready agent profiles."
        ),
        metrics=[
            DashboardMetric(label="Live voice brain", value=settings.openai_realtime_model, tone="primary"),
            DashboardMetric(label="Telephony edge", value="Twilio bidirectional stream", tone="primary"),
            DashboardMetric(label="Realtime voice", value=settings.openai_voice, tone="neutral"),
            DashboardMetric(label="Blocked contacts", value="1 / 3 demo contacts", tone="warning"),
        ],
        contacts=SAMPLE_CONTACTS,
        agent_profiles=AGENT_PROFILES,
        provider_defaults={
            "openai_realtime": settings.openai_realtime_model,
            "voice": settings.openai_voice,
            "sample_rate": str(settings.openai_input_sample_rate),
        },
        compliance_rules=[
            "Block do-not-call and revoked-consent contacts",
            "Block local quiet-hour violations",
            "Require an opening disclosure for recorded calls",
            "Stop immediately on opt-out language",
        ],
        platform_surfaces=[
            {"surface": "Operator console", "purpose": "Manage sessions, personas, traces, and compliance."},
            {"surface": "Twilio voice webhook", "purpose": "Return `<Connect><Stream>` TwiML for live phone calls."},
            {"surface": "OpenAI session template", "purpose": "Generate realtime configuration for live voice agents."},
            {"surface": "Media stream bridge", "purpose": "Normalize Twilio stream messages for realtime transport."},
        ],
    )


@app.post("/api/session-plan", response_model=SessionPlanResponse)
def session_plan(request: StartSessionRequest) -> SessionPlanResponse:
    try:
        contact = get_contact(request.contact_id)
        agent_profile = get_agent_profile(request.agent_profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    compliance = evaluate_compliance(contact, [])
    session_id = "preview"
    opening_line = orchestrator.build_opening_line(contact, agent_profile)
    websocket_path = orchestrator.build_websocket_path(session_id)

    return SessionPlanResponse(
        contact=contact,
        agent_profile=agent_profile,
        opening_line=opening_line,
        realtime_model=settings.openai_realtime_model,
        telephony_mode="twilio-media-stream",
        websocket_path=websocket_path,
        compliance=compliance,
        notes=[
            "Use Twilio `<Connect><Stream>` for bidirectional realtime audio.",
            "Feed OpenAI Realtime tools from your business workflows rather than hardcoding actions.",
            "Escalate to a human teammate when the caller explicitly asks for one.",
        ],
    )


@app.get("/api/realtime/session-template")
def realtime_session_template(contact_id: str, agent_profile_id: str = "agent-sales") -> dict[str, object]:
    try:
        contact = get_contact(contact_id)
        agent_profile = get_agent_profile(agent_profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return orchestrator.build_session_template(contact, agent_profile)


@app.post("/api/sessions", response_model=SessionView)
def start_session(request: StartSessionRequest) -> SessionView:
    try:
        contact = get_contact(request.contact_id)
        agent_profile = get_agent_profile(request.agent_profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    compliance = evaluate_compliance(contact, [])
    session = store.create(
        contact=contact,
        agent_profile=agent_profile,
        compliance=compliance,
        websocket_path=orchestrator.build_websocket_path("pending"),
    )

    session.websocket_path = orchestrator.build_websocket_path(session.session_id)
    opening_line = orchestrator.build_opening_line(contact, agent_profile)
    session.turns.append(ConversationTurn(speaker="agent", text=opening_line))
    session.started = True
    session.latest_reply = opening_line
    store.save(session)

    return SessionView(session=session, agent_reply=None)


@app.post("/api/sessions/{session_id}/respond", response_model=SessionView)
def respond(session_id: str, request: RespondRequest) -> SessionView:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session.turns.append(ConversationTurn(speaker="caller", text=request.caller_text))
    reply = orchestrator.next_turn(session, request.caller_text)

    session.turns.append(ConversationTurn(speaker="agent", text=reply.reply))
    session.state = reply.next_state
    session.trace = reply.trace
    session.latest_reply = reply.reply
    session.latest_disposition = reply.disposition
    session.summary_note = reply.tool_suggestion
    store.save(session)

    return SessionView(session=session, agent_reply=reply)


@app.post("/twilio/voice/{session_id}")
def twilio_voice(session_id: str) -> Response:
    try:
        session = store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stream_url = bridge.build_stream_url(session_id)
    twiml = build_stream_twiml(
        stream_url=stream_url,
        opening_line=session.latest_reply or orchestrator.build_opening_line(session.contact, session.agent_profile),
        session_id=session.session_id,
        agent_name=session.agent_profile.name,
    )
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/twilio/media-stream/{session_id}")
async def twilio_media_stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            normalized = bridge.normalize_twilio_message(message)
            if normalized["event"] == "stop":
                break
    except WebSocketDisconnect:
        return
    finally:
        await websocket.close()

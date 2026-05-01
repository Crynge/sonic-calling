from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .data import AGENT_PROFILES, SAMPLE_CONTACTS, get_agent_profile, get_contact
from .schemas import (
    ConversationTurn,
    DashboardMetric,
    DashboardSummary,
    RealtimeClientSecret,
    RealtimeClientSecretResponse,
    RespondRequest,
    SessionCollectionView,
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


def _resolve_contact_and_agent(request: StartSessionRequest):
    try:
        contact = get_contact(request.contact_id)
        agent_profile = get_agent_profile(request.agent_profile_id)
        return contact, agent_profile
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _resolve_session(session_id: str):
    try:
        return store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, object]:
    runtime = bridge.build_runtime_health()
    return {
        "status": "ok",
        "live_bridge_enabled": runtime.live_bridge_enabled,
        "openai_api_configured": runtime.openai_api_configured,
        "twilio_credentials_configured": runtime.twilio_credentials_configured,
    }


@app.get("/api/runtime/health", response_model=None)
def runtime_health() -> dict[str, object]:
    return bridge.build_runtime_health().model_dump()


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    runtime = bridge.build_runtime_health()
    return DashboardSummary(
        repo_name="sonic-calling",
        narrative=(
            "A realtime developer platform for AI telephony that bridges Twilio voice streams "
            "into OpenAI Realtime sessions with operator-visible traces, tool-ready agent profiles, "
            "and a simulator path that stays useful even when live credentials are absent."
        ),
        metrics=[
            DashboardMetric(label="Live voice brain", value=settings.openai_realtime_model, tone="primary"),
            DashboardMetric(label="Telephony edge", value="Twilio bidirectional stream", tone="primary"),
            DashboardMetric(
                label="Bridge mode",
                value="OpenAI Realtime live" if runtime.live_bridge_enabled else "Simulator fallback",
                tone="neutral",
            ),
            DashboardMetric(label="Session ledger", value=str(len(store.list())), tone="neutral"),
            DashboardMetric(label="Blocked contacts", value="1 / 3 demo contacts", tone="warning"),
        ],
        contacts=SAMPLE_CONTACTS,
        agent_profiles=AGENT_PROFILES,
        provider_defaults={
            "openai_realtime": settings.openai_realtime_model,
            "voice": settings.openai_voice,
            "input_audio_format": settings.openai_input_audio_format,
            "output_audio_format": settings.openai_output_audio_format,
            "turn_detection": settings.openai_turn_detection_mode,
            "transcription_model": settings.openai_transcription_model,
        },
        compliance_rules=[
            "Block do-not-call and revoked-consent contacts",
            "Block local quiet-hour violations",
            "Require an opening disclosure for recorded calls",
            "Stop immediately on opt-out language",
            "Escalate risky claims or ambiguous consent to a human workflow",
        ],
        platform_surfaces=[
            {"surface": "Operator console", "purpose": "Inspect sessions, traces, runtime health, and agent personas."},
            {"surface": "Twilio voice webhook", "purpose": "Return `<Connect><Stream>` TwiML for live phone calls."},
            {"surface": "OpenAI session template", "purpose": "Generate realtime configuration for server or browser clients."},
            {"surface": "Realtime client secret endpoint", "purpose": "Mint short-lived client secrets for browser or WebRTC flows."},
            {"surface": "Media stream bridge", "purpose": "Translate Twilio media frames into OpenAI Realtime audio events."},
            {"surface": "Session ledger API", "purpose": "Poll active or recent sessions for operator oversight."},
        ],
        runtime_health=runtime,
    )


@app.get("/api/sessions", response_model=SessionCollectionView)
def list_sessions() -> SessionCollectionView:
    return SessionCollectionView(sessions=store.list())


@app.get("/api/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: str) -> SessionView:
    session = _resolve_session(session_id)
    return SessionView(session=session, agent_reply=None)


@app.post("/api/session-plan", response_model=SessionPlanResponse)
def session_plan(request: StartSessionRequest) -> SessionPlanResponse:
    contact, agent_profile = _resolve_contact_and_agent(request)
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
            "Sonic Calling now emits session ledger telemetry so operators can inspect runtime state after each turn.",
            "Browser clients can request a short-lived OpenAI Realtime client secret from `/api/realtime/client-secret`.",
            "Direct Twilio bridging uses g711 u-law end to end, so no local transcoding step is required.",
        ],
    )


@app.get("/api/realtime/session-template")
def realtime_session_template(contact_id: str, agent_profile_id: str = "agent-sales") -> dict[str, object]:
    contact = get_contact(contact_id)
    agent_profile = get_agent_profile(agent_profile_id)
    return orchestrator.build_session_template(contact, agent_profile)


@app.post("/api/realtime/client-secret", response_model=RealtimeClientSecretResponse)
async def realtime_client_secret(request: StartSessionRequest) -> RealtimeClientSecretResponse:
    contact, agent_profile = _resolve_contact_and_agent(request)
    compliance = evaluate_compliance(contact, [])
    session = store.create(
        contact=contact,
        agent_profile=agent_profile,
        compliance=compliance,
        websocket_path=orchestrator.build_websocket_path("pending"),
    )
    session.websocket_path = orchestrator.build_websocket_path(session.session_id)
    store.save(session)

    session_template = orchestrator.build_session_template(contact, agent_profile)
    if not bridge.live_bridge_enabled:
        bridge.append_event(
            session,
            "system",
            "client_secret.preview",
            "Generated a preview response because OPENAI_API_KEY is not configured.",
        )
        store.save(session)
        return RealtimeClientSecretResponse(
            enabled=False,
            session_id=session.session_id,
            session=session_template["session"],
            client_secret=None,
            preview_reason="OPENAI_API_KEY is not configured for live client secret minting.",
        )

    payload = await bridge.transport.create_client_secret(session_template)
    client_secret_payload = payload.get("client_secret")
    bridge.append_event(session, "system", "client_secret.created", "Minted a realtime client secret for a browser client.")
    store.save(session)
    return RealtimeClientSecretResponse(
        enabled=True,
        session_id=session.session_id,
        session=payload,
        client_secret=RealtimeClientSecret(
            value=client_secret_payload["value"],
            expires_at=client_secret_payload["expires_at"],
        ),
        preview_reason=None,
    )


@app.post("/api/sessions", response_model=SessionView)
def start_session(request: StartSessionRequest) -> SessionView:
    contact, agent_profile = _resolve_contact_and_agent(request)

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
    bridge.append_event(session, "system", "session.created", "Started a simulator session and generated the opening line.")
    store.save(session)

    return SessionView(session=session, agent_reply=None)


@app.post("/api/sessions/{session_id}/respond", response_model=SessionView)
def respond(session_id: str, request: RespondRequest) -> SessionView:
    session = _resolve_session(session_id)

    session.turns.append(ConversationTurn(speaker="caller", text=request.caller_text))
    bridge.append_event(session, "system", "simulator.caller_text", "Simulator caller utterance submitted.")
    reply = orchestrator.next_turn(session, request.caller_text)

    session.turns.append(ConversationTurn(speaker="agent", text=reply.reply))
    session.state = reply.next_state
    session.trace = reply.trace
    session.latest_reply = reply.reply
    session.latest_disposition = reply.disposition
    session.summary_note = reply.tool_suggestion
    session.runtime.bridge_mode = "simulated"
    store.save(session)

    return SessionView(session=session, agent_reply=reply)


@app.post("/twilio/voice/{session_id}")
def twilio_voice(session_id: str) -> Response:
    session = _resolve_session(session_id)

    stream_url = bridge.build_stream_url(session_id)
    twiml = build_stream_twiml(
        stream_url=stream_url,
        opening_line=session.latest_reply or orchestrator.build_opening_line(session.contact, session.agent_profile),
        session_id=session.session_id,
        agent_name=session.agent_profile.name,
    )
    bridge.append_event(session, "system", "twilio.twiml", "Generated TwiML stream instructions for Twilio Voice.")
    store.save(session)
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/twilio/media-stream/{session_id}")
async def twilio_media_stream(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    try:
        session = store.get(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    try:
        if bridge.live_bridge_enabled:
            await bridge.bridge_live_audio(
                websocket,
                session,
                orchestrator.build_session_template(session.contact, session.agent_profile),
            )
        else:
            await bridge.run_simulated_capture(websocket, session)
    except WebSocketDisconnect:
        bridge.append_event(session, "system", "bridge.disconnect", "Twilio websocket disconnected.")
    except Exception as exc:  # pragma: no cover - live websocket failures are integration-time paths
        session.runtime.bridge_status = "error"
        session.runtime.last_error = str(exc)
        bridge.append_event(session, "system", "bridge.exception", "Bridge raised an exception.", {"error": str(exc)})
    finally:
        store.save(session)
        try:
            await websocket.close()
        except RuntimeError:
            return

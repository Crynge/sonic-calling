from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .data import AGENT_PROFILES, SAMPLE_CONTACTS, get_agent_profile, get_contact
from .schemas import (
    ConversationTurn,
    DashboardMetric,
    DashboardSummary,
    ProviderProfile,
    ProviderProfileInput,
    ProviderSelectionRequest,
    ProviderSurface,
    RealtimeClientSecret,
    RealtimeClientSecretResponse,
    RespondRequest,
    RuntimeConfigurationView,
    SessionCollectionView,
    SessionPlanResponse,
    SessionView,
    StartSessionRequest,
    ToolExecutionRecord,
    ToolExecutionRequest,
    ToolIntegration,
    ToolIntegrationInput,
)
from .services.compliance import evaluate_compliance
from .services.realtime import RealtimeOrchestrator
from .services.realtime_bridge import TwilioRealtimeBridge
from .services.runtime_config import RuntimeConfigStore
from .services.store import SessionStore
from .services.tool_registry import ToolRegistry
from .services.twilio_adapter import build_stream_twiml

app = FastAPI(title="Sonic Calling")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runtime_config = RuntimeConfigStore()
tools = ToolRegistry(runtime_config)
store = SessionStore()
orchestrator = RealtimeOrchestrator()
bridge = TwilioRealtimeBridge(runtime_config, tools)


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


def _resolve_realtime_profile(profile_id: str | None = None) -> ProviderProfile | None:
    try:
        return runtime_config.resolve_provider_profile(ProviderSurface.REALTIME, profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _resolve_telephony_profile(profile_id: str | None = None) -> ProviderProfile | None:
    try:
        return runtime_config.resolve_provider_profile(ProviderSurface.TELEPHONY, profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _build_runtime_configuration_view() -> RuntimeConfigurationView:
    return RuntimeConfigurationView(
        provider_profiles=runtime_config.list_provider_profiles(),
        tool_integrations=tools.list_integrations(),
        active_realtime_profile_id=runtime_config.get_active_profile_id(ProviderSurface.REALTIME),
        active_telephony_profile_id=runtime_config.get_active_profile_id(ProviderSurface.TELEPHONY),
    )


def _build_session_template(contact, agent_profile, provider_profile_id: str | None = None) -> dict[str, object]:
    credentials = runtime_config.resolve_credentials(ProviderSurface.REALTIME, provider_profile_id)
    return orchestrator.build_session_template(
        contact,
        agent_profile,
        model=bridge.transport.resolve_model(credentials),
        tool_catalog=tools.list_integrations(),
    )


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


@app.get("/api/runtime/config", response_model=RuntimeConfigurationView)
def runtime_configuration() -> RuntimeConfigurationView:
    return _build_runtime_configuration_view()


@app.post("/api/runtime/providers", response_model=ProviderProfile)
def create_provider_profile(request: ProviderProfileInput) -> ProviderProfile:
    return runtime_config.create_provider_profile(request)


@app.post("/api/runtime/providers/{surface}/select", response_model=ProviderProfile)
def select_provider_profile(surface: ProviderSurface, request: ProviderSelectionRequest) -> ProviderProfile:
    try:
        return runtime_config.select_active_profile(surface, request.profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tools", response_model=list[ToolIntegration])
def list_tools() -> list[ToolIntegration]:
    return tools.list_integrations()


@app.get("/api/tools/executions", response_model=list[ToolExecutionRecord])
def list_tool_executions() -> list[ToolExecutionRecord]:
    return tools.list_history()


@app.post("/api/tools", response_model=ToolIntegration)
def create_tool(request: ToolIntegrationInput) -> ToolIntegration:
    return tools.create_integration(request)


@app.post("/api/tools/{tool_id}/execute", response_model=ToolExecutionRecord)
def execute_tool(tool_id: str, request: ToolExecutionRequest) -> ToolExecutionRecord:
    try:
        integration = tools.get_integration(tool_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = _resolve_session(request.session_id) if request.session_id else None
    function_name = request.arguments.get("function_name") or (
        integration.mapped_functions[0] if integration.mapped_functions else integration.name.lower().replace(" ", "_")
    )
    record = tools.execute(
        function_name,
        request.reason,
        request.arguments,
        session=session,
    )
    if session:
        bridge.append_event(
            session,
            "tool",
            "tool.execution",
            f"Operator executed {function_name} through {integration.name}.",
            {"status": record.status.value},
        )
        session.summary_note = record.output_payload.get("summary", session.summary_note)
        store.save(session)
    return record


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    runtime = bridge.build_runtime_health()
    runtime_config_view = _build_runtime_configuration_view()
    return DashboardSummary(
        repo_name="sonic-calling",
        narrative=(
            "A realtime developer platform for AI telephony that bridges Twilio voice streams "
            "into OpenAI Realtime sessions with operator-visible traces, bring-your-own API profiles, "
            "and a tool execution mesh that supports simulator mode, custom webhooks, and live function-call outputs."
        ),
        metrics=[
            DashboardMetric(label="Live voice brain", value=settings.openai_realtime_model, tone="primary"),
            DashboardMetric(label="Telephony edge", value="Twilio bidirectional stream", tone="primary"),
            DashboardMetric(
                label="Bridge mode",
                value="OpenAI Realtime live" if runtime.live_bridge_enabled else "Simulator fallback",
                tone="neutral",
            ),
            DashboardMetric(label="BYO provider vault", value=str(len(runtime_config_view.provider_profiles)), tone="neutral"),
            DashboardMetric(label="Tool mesh", value=str(sum(1 for item in runtime_config_view.tool_integrations if item.enabled)), tone="neutral"),
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
            "active_realtime_profile": runtime.active_realtime_profile or "none",
            "active_telephony_profile": runtime.active_telephony_profile or "none",
        },
        compliance_rules=[
            "Block do-not-call and revoked-consent contacts",
            "Block local quiet-hour violations",
            "Require an opening disclosure for recorded calls",
            "Stop immediately on opt-out language",
            "Escalate risky claims or ambiguous consent to a human workflow",
        ],
        platform_surfaces=[
            {"surface": "Operator console", "purpose": "Inspect sessions, traces, runtime health, BYO providers, and tool integrations."},
            {"surface": "BYO API vault", "purpose": "Store masked OpenAI, Twilio, and sidecar provider profiles."},
            {"surface": "Tool mesh", "purpose": "Map agent functions to CRM, scheduling, messaging, and webhook actions."},
            {"surface": "Twilio voice webhook", "purpose": "Return `<Connect><Stream>` TwiML for live phone calls."},
            {"surface": "OpenAI session template", "purpose": "Generate realtime configuration for server or browser clients."},
            {"surface": "Realtime client secret endpoint", "purpose": "Mint short-lived client secrets for browser or WebRTC flows."},
            {"surface": "Media stream bridge", "purpose": "Translate Twilio media frames into OpenAI Realtime audio and tool events."},
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
    realtime_profile = _resolve_realtime_profile(request.provider_profile_id)
    telephony_profile = _resolve_telephony_profile(request.telephony_profile_id)
    model = bridge.transport.resolve_model(
        runtime_config.resolve_credentials(ProviderSurface.REALTIME, request.provider_profile_id)
    )

    return SessionPlanResponse(
        contact=contact,
        agent_profile=agent_profile,
        opening_line=opening_line,
        realtime_model=model,
        telephony_mode="twilio-media-stream",
        websocket_path=websocket_path,
        compliance=compliance,
        notes=[
            "Use Twilio `<Connect><Stream>` for bidirectional realtime audio.",
            f"Active Realtime profile: {realtime_profile.name if realtime_profile else 'none'}",
            f"Active telephony profile: {telephony_profile.name if telephony_profile else 'none'}",
            "Sonic Calling now emits session ledger telemetry plus tool execution history so operators can inspect runtime state after each turn.",
            "Browser clients can request a short-lived OpenAI Realtime client secret from `/api/realtime/client-secret`.",
            "Direct Twilio bridging uses g711 u-law end to end, so no local transcoding step is required.",
        ],
    )


@app.get("/api/realtime/session-template")
def realtime_session_template(contact_id: str, agent_profile_id: str = "agent-sales", provider_profile_id: str | None = None) -> dict[str, object]:
    contact = get_contact(contact_id)
    agent_profile = get_agent_profile(agent_profile_id)
    return _build_session_template(contact, agent_profile, provider_profile_id)


@app.post("/api/realtime/client-secret", response_model=RealtimeClientSecretResponse)
async def realtime_client_secret(request: StartSessionRequest) -> RealtimeClientSecretResponse:
    contact, agent_profile = _resolve_contact_and_agent(request)
    compliance = evaluate_compliance(contact, [])
    provider_profile = _resolve_realtime_profile(request.provider_profile_id)
    telephony_profile = _resolve_telephony_profile(request.telephony_profile_id)
    session = store.create(
        contact=contact,
        agent_profile=agent_profile,
        compliance=compliance,
        websocket_path=orchestrator.build_websocket_path("pending"),
        provider_profile_id=provider_profile.profile_id if provider_profile else None,
        telephony_profile_id=telephony_profile.profile_id if telephony_profile else None,
        live_bridge_enabled=bool(provider_profile and provider_profile.ready),
    )
    session.websocket_path = orchestrator.build_websocket_path(session.session_id)
    store.save(session)

    session_template = _build_session_template(contact, agent_profile, request.provider_profile_id)
    credentials = runtime_config.resolve_credentials(ProviderSurface.REALTIME, request.provider_profile_id)
    if not bridge.transport.enabled_for(credentials):
        bridge.append_event(
            session,
            "system",
            "client_secret.preview",
            "Generated a preview response because no ready OpenAI Realtime BYO profile is active.",
        )
        store.save(session)
        return RealtimeClientSecretResponse(
            enabled=False,
            session_id=session.session_id,
            session=session_template["session"],
            client_secret=None,
            preview_reason="No ready OpenAI Realtime profile is active for live client-secret minting.",
        )

    payload = await bridge.transport.create_client_secret(session_template, credentials=credentials)
    bridge.append_event(session, "system", "client_secret.created", "Minted a realtime client secret for a browser client.")
    store.save(session)
    return RealtimeClientSecretResponse(
        enabled=True,
        session_id=session.session_id,
        session=payload.get("session", payload),
        client_secret=RealtimeClientSecret(
            value=payload["value"],
            expires_at=payload["expires_at"],
        ),
        preview_reason=None,
    )


@app.post("/api/sessions", response_model=SessionView)
def start_session(request: StartSessionRequest) -> SessionView:
    contact, agent_profile = _resolve_contact_and_agent(request)
    realtime_profile = _resolve_realtime_profile(request.provider_profile_id)
    telephony_profile = _resolve_telephony_profile(request.telephony_profile_id)

    compliance = evaluate_compliance(contact, [])
    session = store.create(
        contact=contact,
        agent_profile=agent_profile,
        compliance=compliance,
        websocket_path=orchestrator.build_websocket_path("pending"),
        provider_profile_id=realtime_profile.profile_id if realtime_profile else None,
        telephony_profile_id=telephony_profile.profile_id if telephony_profile else None,
        live_bridge_enabled=bool(realtime_profile and realtime_profile.ready),
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
    session.runtime.bridge_mode = "simulated"

    if reply.tool_suggestion:
        tool_record = tools.execute(
            reply.tool_suggestion,
            reason=request.caller_text,
            arguments={
                "reason": request.caller_text,
                "contact_id": session.contact.id,
                "time_window": "tomorrow afternoon" if "tomorrow" in request.caller_text.lower() else "",
            },
            session=session,
        )
        session.summary_note = tool_record.output_payload.get("summary", reply.tool_suggestion)
        bridge.append_event(
            session,
            "tool",
            "tool.execution",
            f"Simulator executed {reply.tool_suggestion}.",
            {"status": tool_record.status.value},
        )
    else:
        session.summary_note = reply.tool_suggestion

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
        if bridge.transport.enabled_for(runtime_config.resolve_credentials(ProviderSurface.REALTIME, session.provider_profile_id)):
            await bridge.bridge_live_audio(
                websocket,
                session,
                _build_session_template(session.contact, session.agent_profile, session.provider_profile_id),
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

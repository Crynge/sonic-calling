from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProviderName(str, Enum):
    OPENAI = "openai"
    LOCAL = "local"


class SessionState(str, Enum):
    READY = "ready"
    LIVE = "live"
    FOLLOW_UP = "follow_up"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ContactProfile(BaseModel):
    id: str
    full_name: str
    local_hour: int
    phone: str
    city: str
    state: str
    use_case: str
    organization: str
    consent_status: Literal["consented", "unknown", "revoked"]
    do_not_call: bool = False
    persona: str
    notes: str = ""


class AgentProfile(BaseModel):
    id: str
    name: str
    vertical: str
    voice: str
    goal: str
    tool_stack: list[str]
    notes: str = ""


class ConversationTurn(BaseModel):
    speaker: Literal["agent", "caller", "system"]
    text: str


class ComplianceResult(BaseModel):
    allowed: bool
    risk_level: Literal["low", "medium", "high", "blocked"]
    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class RealtimeTrace(BaseModel):
    provider: ProviderName
    model: str
    event: str
    confidence: float
    detail: str
    used_fallback: bool = False


class StreamEvent(BaseModel):
    source: Literal["twilio", "openai", "system"]
    event: str
    detail: str
    timestamp: str = Field(default_factory=utc_now)
    payload_preview: dict[str, Any] = Field(default_factory=dict)


class SessionRuntime(BaseModel):
    bridge_mode: Literal["simulated", "openai_realtime"] = "simulated"
    bridge_status: Literal["idle", "connecting", "streaming", "closed", "error"] = "idle"
    input_audio_format: str = "g711_ulaw"
    output_audio_format: str = "g711_ulaw"
    stream_sid: str | None = None
    call_sid: str | None = None
    openai_response_id: str | None = None
    twilio_event_count: int = 0
    openai_event_count: int = 0
    latest_mark: str | None = None
    last_input_transcript: str = ""
    last_output_transcript: str = ""
    last_tool_name: str | None = None
    last_tool_arguments: str | None = None
    last_error: str | None = None


class AgentReply(BaseModel):
    reply: str
    next_state: SessionState
    disposition: Literal["continue", "schedule", "handoff", "stop"]
    confidence: float
    tool_suggestion: str
    trace: list[RealtimeTrace]


class RealtimeSession(BaseModel):
    session_id: str
    contact: ContactProfile
    agent_profile: AgentProfile
    state: SessionState
    created_at: str = Field(default_factory=utc_now)
    started: bool = False
    turns: list[ConversationTurn] = Field(default_factory=list)
    trace: list[RealtimeTrace] = Field(default_factory=list)
    events: list[StreamEvent] = Field(default_factory=list)
    runtime: SessionRuntime = Field(default_factory=SessionRuntime)
    compliance: ComplianceResult
    latest_reply: str = ""
    latest_disposition: str = "continue"
    summary_note: str = ""
    websocket_path: str = ""


class StartSessionRequest(BaseModel):
    contact_id: str
    agent_profile_id: str = "agent-sales"


class RespondRequest(BaseModel):
    caller_text: str


class SessionView(BaseModel):
    session: RealtimeSession
    agent_reply: AgentReply | None = None


class SessionCollectionView(BaseModel):
    sessions: list[RealtimeSession]


class DashboardMetric(BaseModel):
    label: str
    value: str
    tone: Literal["primary", "neutral", "warning"]


class RuntimeHealth(BaseModel):
    openai_api_configured: bool
    twilio_credentials_configured: bool
    live_bridge_enabled: bool
    client_secret_enabled: bool
    public_base_url: str
    public_websocket_base: str
    openai_websocket_url: str
    input_audio_format: str
    output_audio_format: str
    transcription_model: str
    turn_detection_mode: str


class DashboardSummary(BaseModel):
    repo_name: str
    narrative: str
    metrics: list[DashboardMetric]
    contacts: list[ContactProfile]
    agent_profiles: list[AgentProfile]
    provider_defaults: dict[str, str]
    compliance_rules: list[str]
    platform_surfaces: list[dict[str, str]]
    runtime_health: RuntimeHealth


class SessionPlanResponse(BaseModel):
    contact: ContactProfile
    agent_profile: AgentProfile
    opening_line: str
    realtime_model: str
    telephony_mode: str
    websocket_path: str
    compliance: ComplianceResult
    notes: list[str]


class RealtimeClientSecret(BaseModel):
    value: str
    expires_at: int


class RealtimeClientSecretResponse(BaseModel):
    enabled: bool
    session_id: str
    session: dict[str, Any]
    client_secret: RealtimeClientSecret | None = None
    preview_reason: str | None = None

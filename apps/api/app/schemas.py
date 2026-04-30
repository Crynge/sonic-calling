from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


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
    started: bool = False
    turns: list[ConversationTurn] = Field(default_factory=list)
    trace: list[RealtimeTrace] = Field(default_factory=list)
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


class DashboardMetric(BaseModel):
    label: str
    value: str
    tone: Literal["primary", "neutral", "warning"]


class DashboardSummary(BaseModel):
    repo_name: str
    narrative: str
    metrics: list[DashboardMetric]
    contacts: list[ContactProfile]
    agent_profiles: list[AgentProfile]
    provider_defaults: dict[str, str]
    compliance_rules: list[str]
    platform_surfaces: list[dict[str, str]]


class SessionPlanResponse(BaseModel):
    contact: ContactProfile
    agent_profile: AgentProfile
    opening_line: str
    realtime_model: str
    telephony_mode: str
    websocket_path: str
    compliance: ComplianceResult
    notes: list[str]

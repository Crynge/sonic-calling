from __future__ import annotations

from ..config import settings
from ..schemas import (
    AgentProfile,
    AgentReply,
    ContactProfile,
    ProviderName,
    RealtimeSession,
    RealtimeTrace,
    SessionState,
)
from .compliance import evaluate_compliance


class RealtimeOrchestrator:
    def build_websocket_path(self, session_id: str) -> str:
        return f"/twilio/media-stream/{session_id}"

    def build_opening_line(self, contact: ContactProfile, agent_profile: AgentProfile) -> str:
        return (
            f"Hi {contact.full_name.split()[0]}, this is the {agent_profile.name} recorded voice assistant for "
            f"{contact.organization}. I'm calling about {contact.use_case}. Is now an okay time for a quick update?"
        )

    def build_session_template(self, contact: ContactProfile, agent_profile: AgentProfile) -> dict[str, object]:
        return {
            "type": "session.update",
            "session": {
                "model": settings.openai_realtime_model,
                "instructions": (
                    f"You are {agent_profile.name}, a realtime phone agent for {contact.organization}. "
                    f"Goal: {agent_profile.goal} "
                    "Keep turns short, confirm understanding, and call tools instead of hallucinating actions."
                ),
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": settings.openai_input_sample_rate,
                        },
                        "turn_detection": {
                            "type": "semantic_vad",
                        },
                    },
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                        },
                        "voice": agent_profile.voice,
                    },
                },
                "tools": [
                    {
                        "type": "function",
                        "name": tool_name,
                        "description": f"Invoke the {tool_name} business workflow.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string"},
                            },
                            "required": ["reason"],
                            "additionalProperties": False,
                        },
                    }
                    for tool_name in agent_profile.tool_stack
                ],
            },
        }

    def next_turn(self, session: RealtimeSession, caller_text: str) -> AgentReply:
        transcript = [turn.model_dump() for turn in session.turns]
        compliance = evaluate_compliance(session.contact, transcript, caller_text)
        session.compliance = compliance

        if not compliance.allowed:
            return AgentReply(
                reply="Understood. I will stop the call and mark this contact accordingly.",
                next_state=SessionState.BLOCKED,
                disposition="stop",
                confidence=1.0,
                tool_suggestion="create_crm_note",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.LOCAL,
                        model="local-policy-engine",
                        event="policy.blocked",
                        confidence=1.0,
                        detail=", ".join(compliance.reasons) or "Policy engine blocked the turn.",
                        used_fallback=False,
                    )
                ],
            )

        normalized = caller_text.lower().strip()
        first_name = session.contact.full_name.split()[0]

        if any(token in normalized for token in ["schedule", "book", "callback", "tomorrow", "later"]):
            return AgentReply(
                reply=(
                    f"Absolutely. I can queue a callback or booking flow for {first_name}. "
                    "What time window should I hold for you?"
                ),
                next_state=SessionState.FOLLOW_UP,
                disposition="schedule",
                confidence=0.88,
                tool_suggestion="book_callback",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="response.create",
                        confidence=0.88,
                        detail="Realtime agent detected explicit scheduling intent.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        if any(token in normalized for token in ["human", "agent", "person", "representative"]):
            return AgentReply(
                reply="I can hand this over to a human teammate and attach a summary so you do not need to repeat yourself.",
                next_state=SessionState.HANDOFF,
                disposition="handoff",
                confidence=0.94,
                tool_suggestion="escalate_human",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="tool.plan",
                        confidence=0.94,
                        detail="Realtime agent prepared a human handoff.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        if any(token in normalized for token in ["yes", "okay", "sure", "go ahead", "interested"]):
            return AgentReply(
                reply=(
                    f"Great. For {session.contact.use_case}, is your priority speed, cost, or a better long-term experience?"
                ),
                next_state=SessionState.LIVE,
                disposition="continue",
                confidence=0.83,
                tool_suggestion="lookup_contact",
                trace=[
                    RealtimeTrace(
                        provider=ProviderName.OPENAI,
                        model=settings.openai_realtime_model,
                        event="response.create",
                        confidence=0.83,
                        detail="Realtime follow-up question generated from positive engagement.",
                        used_fallback=not bool(settings.openai_api_key),
                    )
                ],
            )

        return AgentReply(
            reply=(
                "No problem. I can keep it to a 15-second summary, schedule a better time, "
                "or stop here if that is better for you."
            ),
            next_state=SessionState.LIVE,
            disposition="continue",
            confidence=0.74,
            tool_suggestion="create_crm_note",
            trace=[
                RealtimeTrace(
                    provider=ProviderName.OPENAI,
                    model=settings.openai_realtime_model,
                    event="response.create",
                    confidence=0.74,
                    detail="Realtime assistant generated a low-pressure clarification turn.",
                    used_fallback=not bool(settings.openai_api_key),
                )
            ],
        )

from __future__ import annotations

from ..config import settings
from ..schemas import ComplianceResult, ContactProfile


OPT_OUT_PHRASES = ["stop", "do not call", "remove me", "unsubscribe", "don't call"]
HIGH_RISK_PHRASES = ["guaranteed return", "government approved", "act now or lose", "risk free forever"]


def evaluate_compliance(
    contact: ContactProfile,
    transcript: list[dict[str, str]],
    caller_text: str = "",
) -> ComplianceResult:
    reasons: list[str] = []
    missing_requirements: list[str] = []

    if contact.do_not_call or contact.consent_status == "revoked":
        reasons.append("Contact is flagged as do-not-call or revoked consent.")
        return ComplianceResult(
            allowed=False,
            risk_level="blocked",
            reasons=reasons,
            missing_requirements=[],
        )

    if contact.local_hour < settings.quiet_hours_start or contact.local_hour >= settings.quiet_hours_end:
        reasons.append("Contact is outside the allowed local calling window.")
        return ComplianceResult(
            allowed=False,
            risk_level="blocked",
            reasons=reasons,
            missing_requirements=[],
        )

    normalized_text = caller_text.lower()
    if any(phrase in normalized_text for phrase in OPT_OUT_PHRASES):
        reasons.append("Customer asked to opt out or end contact.")
        return ComplianceResult(
            allowed=False,
            risk_level="blocked",
            reasons=reasons,
            missing_requirements=[],
        )

    if transcript:
        first_agent_turn = next(
            (turn["text"] for turn in transcript if turn["speaker"] == "agent"),
            "",
        ).lower()
        if "recorded call" not in first_agent_turn and "recorded voice assistant" not in first_agent_turn:
            missing_requirements.append("Opening disclosure must identify the assistant and mention the recorded call.")

    if any(phrase in normalized_text for phrase in HIGH_RISK_PHRASES):
        reasons.append("High-risk claim language detected.")

    risk_level = "medium" if reasons or missing_requirements else "low"
    return ComplianceResult(
        allowed=True,
        risk_level=risk_level,
        reasons=reasons,
        missing_requirements=missing_requirements,
    )

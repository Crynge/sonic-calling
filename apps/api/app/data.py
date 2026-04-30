from .schemas import AgentProfile, ContactProfile


SAMPLE_CONTACTS = [
    ContactProfile(
        id="contact-001",
        full_name="Rhea Mehta",
        local_hour=11,
        phone="+1-415-555-0101",
        city="San Jose",
        state="CA",
        use_case="dental appointment reminder",
        organization="BrightSmile Dental",
        consent_status="consented",
        do_not_call=False,
        persona="Busy parent who prefers short, clear reminders and fast rescheduling.",
        notes="Often answers calls during mid-morning only.",
    ),
    ContactProfile(
        id="contact-002",
        full_name="Marcus Hill",
        local_hour=16,
        phone="+1-206-555-0132",
        city="Tacoma",
        state="WA",
        use_case="solar consultation qualification",
        organization="SunSwitch Energy",
        consent_status="unknown",
        do_not_call=False,
        persona="Research-heavy buyer who asks ROI questions and wants honest tradeoffs.",
        notes="Good candidate for live AI qualification followed by human callback.",
    ),
    ContactProfile(
        id="contact-003",
        full_name="Anita Rao",
        local_hour=21,
        phone="+1-512-555-0177",
        city="Austin",
        state="TX",
        use_case="policy renewal reminder",
        organization="Northline Insurance",
        consent_status="revoked",
        do_not_call=True,
        persona="Previously asked to be removed from automated outreach.",
        notes="Must remain blocked because of DNC and revoked consent.",
    ),
]


AGENT_PROFILES = [
    AgentProfile(
        id="agent-sales",
        name="Astra SDR",
        vertical="sales qualification",
        voice="marin",
        goal="Qualify inbound or outbound prospects and book the best next step.",
        tool_stack=["lookup_contact", "book_callback", "create_crm_note", "escalate_human"],
        notes="Designed for short qualifying calls with follow-up scheduling.",
    ),
    AgentProfile(
        id="agent-reminder",
        name="Pulse Concierge",
        vertical="reminders and rescheduling",
        voice="sage",
        goal="Confirm, reschedule, or gracefully cancel appointments while keeping the caller informed.",
        tool_stack=["reschedule_appointment", "confirm_booking", "send_sms_summary"],
        notes="Optimized for healthcare and service reminders.",
    ),
]


def get_contact(contact_id: str) -> ContactProfile:
    for contact in SAMPLE_CONTACTS:
        if contact.id == contact_id:
            return contact
    raise KeyError(f"Unknown contact_id: {contact_id}")


def get_agent_profile(agent_profile_id: str) -> AgentProfile:
    for profile in AGENT_PROFILES:
        if profile.id == agent_profile_id:
            return profile
    raise KeyError(f"Unknown agent_profile_id: {agent_profile_id}")

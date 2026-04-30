from fastapi.testclient import TestClient

from apps.api.app.main import app


client = TestClient(app)


def test_dashboard_summary() -> None:
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["repo_name"] == "sonic-calling"
    assert len(payload["contacts"]) >= 3
    assert len(payload["agent_profiles"]) >= 2


def test_session_flow() -> None:
    start = client.post("/api/sessions", json={"contact_id": "contact-001", "agent_profile_id": "agent-reminder"})
    assert start.status_code == 200
    session_id = start.json()["session"]["session_id"]

    reply = client.post(
        f"/api/sessions/{session_id}/respond",
        json={"caller_text": "Please schedule me for tomorrow afternoon."},
    )
    assert reply.status_code == 200
    payload = reply.json()
    assert payload["agent_reply"]["reply"]
    assert payload["session"]["latest_reply"]


def test_session_template_endpoint() -> None:
    response = client.get("/api/realtime/session-template?contact_id=contact-001&agent_profile_id=agent-sales")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "session.update"
    assert payload["session"]["model"]


def test_blocked_plan_for_dnc_contact() -> None:
    response = client.post("/api/session-plan", json={"contact_id": "contact-003", "agent_profile_id": "agent-sales"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance"]["allowed"] is False

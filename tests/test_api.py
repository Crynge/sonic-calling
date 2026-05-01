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
    assert payload["runtime_health"]["input_audio_format"] == "g711_ulaw"


def test_runtime_health_endpoint() -> None:
    response = client.get("/api/runtime/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["turn_detection_mode"] in {"server_vad", "semantic_vad"}
    assert payload["client_secret_enabled"] is False
    assert payload["tool_integrations_enabled"] >= 1


def test_runtime_config_endpoint_and_provider_creation() -> None:
    response = client.get("/api/runtime/config")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["provider_profiles"]) >= 2
    assert len(payload["tool_integrations"]) >= 4

    created = client.post(
        "/api/runtime/providers",
        json={
            "name": "Customer OpenAI Vault",
            "provider": "openai",
            "surface": "realtime",
            "api_key": "sk-test-12345678",
            "model": "gpt-realtime",
            "endpoint": "https://api.openai.com/v1/realtime",
            "notes": "test profile",
            "metadata": {},
        },
    )
    assert created.status_code == 200
    assert created.json()["auth_source"] == "vault"

    selected = client.post(
        "/api/runtime/providers/realtime/select",
        json={"profile_id": "provider-openai-managed"},
    )
    assert selected.status_code == 200
    assert selected.json()["surface"] == "realtime"


def test_session_flow_and_ledger() -> None:
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
    assert payload["session"]["runtime"]["bridge_mode"] == "simulated"
    assert payload["session"]["runtime"]["tool_execution_count"] >= 1
    assert len(payload["session"]["tool_executions"]) >= 1

    ledger = client.get("/api/sessions")
    assert ledger.status_code == 200
    assert any(item["session_id"] == session_id for item in ledger.json()["sessions"])

    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["session"]["session_id"] == session_id


def test_session_template_endpoint() -> None:
    response = client.get("/api/realtime/session-template?contact_id=contact-001&agent_profile_id=agent-sales")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "session.update"
    assert payload["session"]["model"]
    assert payload["session"]["audio"]["input"]["format"] == "g711_ulaw"
    assert payload["session"]["audio"]["output"]["voice"]


def test_client_secret_preview_without_key() -> None:
    response = client.post("/api/realtime/client-secret", json={"contact_id": "contact-001", "agent_profile_id": "agent-sales"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["preview_reason"]


def test_tool_execution_endpoint() -> None:
    start = client.post("/api/sessions", json={"contact_id": "contact-002", "agent_profile_id": "agent-sales"})
    assert start.status_code == 200
    session_id = start.json()["session"]["session_id"]

    response = client.post(
        "/api/tools/tool-handoff-desk/execute",
        json={
            "session_id": session_id,
            "reason": "Customer requested a human follow-up.",
            "arguments": {
                "function_name": "escalate_human",
                "reason": "Customer requested a human follow-up.",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "escalate_human"
    assert payload["status"] in {"simulated", "completed"}


def test_blocked_plan_for_dnc_contact() -> None:
    response = client.post("/api/session-plan", json={"contact_id": "contact-003", "agent_profile_id": "agent-sales"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance"]["allowed"] is False

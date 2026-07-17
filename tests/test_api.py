import io

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_signup_and_login_flow(client: TestClient):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "new.user@example.com", "password": "SuperSecret1", "full_name": "New User"},
    )
    assert signup.status_code == 201

    login = client.post(
        "/api/v1/auth/login", params={"email": "new.user@example.com", "password": "SuperSecret1"}
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_login_rejects_wrong_password(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        params={"email": "admin@enterprise-ai.demo", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client: TestClient):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_profile(client: TestClient, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "analyst@enterprise-ai.demo"


def test_chat_requires_auth(client: TestClient):
    resp = client.post("/api/v1/chat", json={"message": "hello"})
    assert resp.status_code == 401


def test_chat_knowledge_base_roundtrip(client: TestClient, auth_headers):
    resp = client.post(
        "/api/v1/chat", json={"message": "What's our vacation policy?"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_used"] == "knowledge_base"
    assert "conversation_id" in body


def test_chat_history_persists_across_turns(client: TestClient, auth_headers):
    first = client.post(
        "/api/v1/chat", json={"message": "Give me a weekly summary report"}, headers=auth_headers
    ).json()
    conv_id = first["conversation_id"]
    client.post(
        "/api/v1/chat",
        json={"conversation_id": conv_id, "message": "Anything else?"},
        headers=auth_headers,
    )
    history = client.get(f"/api/v1/chat/{conv_id}/history", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 4  # 2 user + 2 assistant turns


def test_chat_stream_emits_sse_events(client: TestClient, auth_headers):
    resp = client.post(
        "/api/v1/chat/stream", json={"message": "Review this Python function for bugs"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert "data:" in resp.text


def test_document_upload_and_search(client: TestClient, auth_headers):
    content = b"Our refund policy allows returns within 30 days for standard customers."
    files = {"file": ("policy.txt", io.BytesIO(content), "text/plain")}
    upload = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert upload.status_code == 201
    assert upload.json()["chunk_count"] >= 1

    search = client.post(
        "/api/v1/documents/search", json={"query": "refund policy", "top_k": 3}, headers=auth_headers
    )
    assert search.status_code == 200
    assert len(search.json()) >= 1


def test_document_upload_rejects_unsupported_type(client: TestClient, auth_headers):
    files = {"file": ("virus.exe", io.BytesIO(b"binary"), "application/octet-stream")}
    resp = client.post("/api/v1/documents/upload", files=files, headers=auth_headers)
    assert resp.status_code == 415


def test_list_agents_returns_six(client: TestClient, auth_headers):
    resp = client.get("/api/v1/agents", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 6


def test_invoke_code_agent_directly(client: TestClient, auth_headers):
    resp = client.post(
        "/api/v1/agents/code/invoke",
        json={"query": "review", "context": {"code": "def f():\n    return 1\n"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["agent"] == "code"


def test_invoke_unknown_agent_returns_404(client: TestClient, auth_headers):
    resp = client.post(
        "/api/v1/agents/not-a-real-agent/invoke", json={"query": "hi"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_admin_analytics_forbidden_for_regular_user(client: TestClient, auth_headers):
    resp = client.get("/api/v1/admin/analytics", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_analytics_allowed_for_admin(client: TestClient, admin_headers):
    resp = client.get("/api/v1/admin/analytics", headers=admin_headers)
    assert resp.status_code == 200
    assert "ai_requests_total" in resp.json()

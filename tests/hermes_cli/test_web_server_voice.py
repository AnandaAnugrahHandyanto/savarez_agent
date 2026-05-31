"""Tests for dashboard voice-call prototype endpoints."""

import pytest


@pytest.fixture()
def voice_client(monkeypatch, _isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_cli.web_server as web_server

    client = TestClient(web_server.app)
    client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    return client, web_server


def test_voice_session_requires_dashboard_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli.web_server import app

    client = TestClient(app)
    resp = client.post("/api/voice/session", json={})
    assert resp.status_code == 401


def test_voice_session_returns_ephemeral_session(voice_client, monkeypatch):
    client, web_server = voice_client

    monkeypatch.setattr(
        web_server,
        "_create_openai_realtime_session",
        lambda user: {
            "client_secret": "ek_test",
            "endpoint": "https://api.openai.com/v1/realtime",
            "model": "gpt-realtime",
            "voice": "alloy",
            "expires_at": 123,
        },
    )

    resp = client.post("/api/voice/session", json={})
    assert resp.status_code == 200
    assert resp.json()["client_secret"] == "ek_test"
    assert resp.json()["model"] == "gpt-realtime"


def test_voice_tool_rejects_unknown_tool(voice_client):
    client, _web_server = voice_client

    resp = client.post("/api/voice/tool", json={"name": "shell", "arguments": {}})
    assert resp.status_code == 400


def test_voice_tool_runs_research_bridge(voice_client, monkeypatch):
    client, web_server = voice_client

    monkeypatch.setattr(
        web_server,
        "_run_voice_research",
        lambda question, user: f"answered: {question}",
    )

    resp = client.post(
        "/api/voice/tool",
        json={"name": "research", "arguments": {"question": "what is Rolly Voice?"}},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "result": "answered: what is Rolly Voice?",
        "error": None,
    }

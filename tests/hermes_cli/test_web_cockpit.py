from fastapi.testclient import TestClient

from hermes_cli import web_server
from hermes_cli.web_server import _SESSION_TOKEN, app


HEADERS = {"X-Hermes-Session-Token": _SESSION_TOKEN}


def test_cockpit_status_reports_api_server_config_and_capabilities(monkeypatch):
    monkeypatch.setattr(
        web_server,
        "load_config",
        lambda: {
            "gateway": {
                "platforms": {
                    "api_server": {
                        "enabled": True,
                        "extra": {
                            "host": "127.0.0.1",
                            "port": 8765,
                            "key": "secret-key",
                        },
                    }
                }
            }
        },
    )
    monkeypatch.setattr(
        web_server,
        "_cockpit_probe_capabilities",
        lambda base_url, key: (True, {"features": {"agui_run_streaming": True}}),
    )

    client = TestClient(app)
    response = client.get("/api/cockpit/status", headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["api_server"]["configured"] is True
    assert body["api_server"]["reachable"] is True
    assert body["api_server"]["base_url"] == "http://127.0.0.1:8765"
    assert body["api_server"]["auth_configured"] is True
    assert body["api_server"]["key_preview"] == "sec…key"
    assert body["capabilities"] == {"features": {"agui_run_streaming": True}}
    assert "secret-key" not in response.text


def test_cockpit_agui_run_proxy_streams_gateway_sse(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_server,
        "_cockpit_api_server_settings",
        lambda: {
            "configured": True,
            "enabled": True,
            "base_url": "http://127.0.0.1:8765",
            "key": "secret-key",
            "host": "127.0.0.1",
            "port": 8765,
            "auth_configured": True,
            "key_preview": "sec…key",
        },
    )

    def fake_stream(path, payload):
        calls.append((path, payload))
        yield b"event: RUN_STARTED\n"
        yield b"data: {\"type\":\"RUN_STARTED\"}\n\n"

    monkeypatch.setattr(web_server, "_cockpit_stream_agui_run", fake_stream)

    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/cockpit/agui/runs",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"threadId": "dash", "messages": [{"role": "user", "content": "hi"}]},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "RUN_STARTED" in body
    assert calls == [
        (
            "/v1/agui/runs",
            {"threadId": "dash", "messages": [{"role": "user", "content": "hi"}]},
        )
    ]


def test_cockpit_agui_run_proxy_requires_configured_api_server(monkeypatch):
    monkeypatch.setattr(
        web_server,
        "_cockpit_api_server_settings",
        lambda: {"configured": False, "enabled": False, "base_url": "", "key": ""},
    )

    client = TestClient(app)
    response = client.post(
        "/api/cockpit/agui/runs",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 409
    assert "API Server" in response.json()["detail"]

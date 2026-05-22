from __future__ import annotations

import argparse
import importlib
from unittest.mock import patch

from fastapi.testclient import TestClient


def _reset_state(ws):
    for name in (
        "bound_host",
        "bound_port",
        "public_mode",
        "legacy_token_auth_enabled",
        "allowed_hosts",
        "secure_cookies",
        "trust_proxy_headers",
    ):
        if hasattr(ws.app.state, name):
            delattr(ws.app.state, name)


def test_public_mode_spa_does_not_inject_legacy_session_token(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    ws = importlib.import_module("hermes_cli.web_server")
    _reset_state(ws)
    ws.app.state.public_mode = True
    ws.app.state.legacy_token_auth_enabled = False
    html = "<html><head></head><body></body></html>"
    index = tmp_path / "index.html"
    index.write_text(html)
    (tmp_path / "assets").mkdir()
    monkeypatch.setattr(ws, "WEB_DIST", tmp_path)
    app = ws.FastAPI()
    ws.mount_spa(app)
    client = TestClient(app)
    resp = client.get("/", headers={"Host": "agents.lan"})
    assert resp.status_code == 200
    assert "__HERMES_SESSION_TOKEN__" not in resp.text
    assert "__HERMES_DASHBOARD_EMBEDDED_CHAT__" in resp.text


def test_public_mode_rejects_legacy_token_and_allows_cookie_login(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    ws = importlib.reload(importlib.import_module("hermes_cli.web_server"))
    _reset_state(ws)
    ws.app.state.public_mode = True
    ws.app.state.legacy_token_auth_enabled = False
    ws.app.state.allowed_hosts = {"agents.lan"}
    client = TestClient(ws.app)

    legacy = {"Host": "agents.lan", ws._SESSION_HEADER_NAME: ws._SESSION_TOKEN}
    assert client.get("/api/config", headers=legacy).status_code == 401

    setup = client.post(
        "/api/auth/setup",
        headers={"Host": "agents.lan"},
        json={"username": "admin", "password": "correct horse battery staple"},
    )
    assert setup.status_code == 200, setup.text
    csrf = setup.json()["csrf_token"]
    assert client.get("/api/config", headers={"Host": "agents.lan"}).status_code == 200
    assert client.put(
        "/api/config",
        headers={"Host": "agents.lan"},
        json={"config": {}},
    ).status_code == 403
    assert client.put(
        "/api/config",
        headers={"Host": "agents.lan", "X-Hermes-CSRF-Token": csrf},
        json={"config": {}},
    ).status_code != 403
    assert client.post("/api/auth/logout", headers={"Host": "agents.lan"}).status_code == 403
    assert client.post(
        "/api/auth/logout",
        headers={"Host": "agents.lan", "X-Hermes-CSRF-Token": csrf},
    ).status_code == 200


def test_legacy_token_still_works_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    ws = importlib.reload(importlib.import_module("hermes_cli.web_server"))
    _reset_state(ws)
    client = TestClient(ws.app)
    resp = client.get(
        "/api/config",
        headers={ws._SESSION_HEADER_NAME: ws._SESSION_TOKEN},
    )
    assert resp.status_code != 401


def test_allowed_host_required_for_all_interface_public_bind():
    ws = importlib.import_module("hermes_cli.web_server")
    assert ws._is_accepted_host("agents.lan:9119", "0.0.0.0", {"agents.lan"})
    assert not ws._is_accepted_host("evil.test:9119", "0.0.0.0", {"agents.lan"})


def test_start_server_records_public_state(monkeypatch):
    ws = importlib.import_module("hermes_cli.web_server")
    _reset_state(ws)
    called = {}

    class FakeUvicorn:
        @staticmethod
        def run(app, **kwargs):
            called.update(kwargs)

    monkeypatch.setitem(importlib.import_module("sys").modules, "uvicorn", FakeUvicorn)
    ws.start_server(
        host="0.0.0.0",
        port=9131,
        open_browser=False,
        public=True,
        allowed_hosts=["agents.lan"],
        secure_cookies=True,
        trust_proxy_headers=True,
    )
    assert ws.app.state.public_mode is True
    assert ws.app.state.legacy_token_auth_enabled is False
    assert ws.app.state.allowed_hosts == {"agents.lan"}
    assert ws.app.state.secure_cookies is True
    assert called["host"] == "0.0.0.0"


def test_cmd_dashboard_forwards_public_flags(monkeypatch):
    import hermes_cli.main as main

    captured = {}
    fake_ws = type("FakeWS", (), {"start_server": staticmethod(lambda **kw: captured.update(kw))})
    monkeypatch.setitem(importlib.import_module("sys").modules, "hermes_cli.web_server", fake_ws)
    monkeypatch.setattr(main, "_build_web_ui", lambda *a, **kw: True)
    args = argparse.Namespace(
        host="0.0.0.0",
        port=9131,
        no_open=True,
        insecure=False,
        public=True,
        allowed_host=["agents.lan"],
        secure_cookies=True,
        no_trust_proxy=False,
        tui=False,
        stop=False,
        status=False,
        skip_build=True,
    )
    main.cmd_dashboard(args)
    assert captured["public"] is True
    assert captured["allowed_hosts"] == ["agents.lan"]
    assert captured["secure_cookies"] is True
    assert captured["trust_proxy_headers"] is True

"""Regression tests for Desktop-token compatibility under dashboard auth gate.

Self-hosted browser auth enables the dashboard gate on non-loopback binds.
Hermes Desktop still authenticates with the legacy session token header and
``?token=`` WebSocket parameter, so gated mode must accept that token as an
additional credential alongside browser cookies/tickets.
"""

from types import SimpleNamespace

import pytest


@pytest.fixture
def web_server_state(_isolate_hermes_home):
    try:
        import hermes_state
        from hermes_constants import get_hermes_home
        from hermes_cli import web_server
    except ImportError as exc:
        pytest.skip(f"dashboard dependencies unavailable: {exc}")

    prev_required = getattr(web_server.app.state, "auth_required", None)
    prev_bound_host = getattr(web_server.app.state, "bound_host", None)
    prev_bound_port = getattr(web_server.app.state, "bound_port", None)
    hermes_state.DEFAULT_DB_PATH = get_hermes_home() / "state.db"
    web_server.app.state.auth_required = True
    web_server.app.state.bound_host = "0.0.0.0"
    web_server.app.state.bound_port = 9119
    try:
        yield web_server
    finally:
        web_server.app.state.auth_required = prev_required
        web_server.app.state.bound_host = prev_bound_host
        web_server.app.state.bound_port = prev_bound_port


def test_gated_dashboard_accepts_desktop_session_token_header(web_server_state):
    """Desktop HTTP API calls must still work in browser-auth mode."""
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    ws = web_server_state
    client = TestClient(ws.app)

    response = client.get(
        "/api/config",
        headers={ws._SESSION_HEADER_NAME: ws._SESSION_TOKEN},
    )

    assert response.status_code == 200, response.text


def test_gated_dashboard_accepts_desktop_session_token_websocket(web_server_state):
    """Desktop WebSocket URL still uses ?token=, even when the gate is active."""
    ws = web_server_state
    fake_ws = SimpleNamespace(
        query_params={"token": ws._SESSION_TOKEN},
        client=SimpleNamespace(host="192.168.23.42"),
        url=SimpleNamespace(path="/api/ws"),
    )

    reason, credential = ws._ws_auth_reason(fake_ws)

    assert reason is None
    assert credential == "token"

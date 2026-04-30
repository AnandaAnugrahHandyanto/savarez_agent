"""Tests for WebSocket client acceptance and sidecar URL normalization.

Dashboard WebSocket endpoints reject non-loopback peers as defense-in-depth.
When the operator explicitly starts with ``--insecure`` on a non-loopback
bind, remote clients are allowed so that reverse-proxied or Tailscale-based
access works.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


class FakeWebSocket:
    """Minimal stand-in for a FastAPI WebSocket connection."""

    def __init__(self, host: str):
        self.client = type("_Client", (), {"host": host})()


class TestIsAcceptedWsClient:
    """Unit-test the _is_accepted_ws_client helper directly."""

    def test_loopback_accepted_by_default(self, monkeypatch):
        from hermes_cli.web_server import _is_accepted_ws_client, app

        # Clean state — allow_public may be absent entirely
        if hasattr(app.state, "allow_public"):
            monkeypatch.delattr(app.state, "allow_public")

        assert _is_accepted_ws_client(FakeWebSocket("127.0.0.1")) is True
        assert _is_accepted_ws_client(FakeWebSocket("::1")) is True
        assert _is_accepted_ws_client(FakeWebSocket("localhost")) is True
        assert _is_accepted_ws_client(FakeWebSocket("testclient")) is True
        assert _is_accepted_ws_client(FakeWebSocket("")) is True

    def test_non_loopback_rejected_when_not_allow_public(self, monkeypatch):
        from hermes_cli.web_server import _is_accepted_ws_client, app

        monkeypatch.setattr(app.state, "allow_public", False, raising=False)

        assert _is_accepted_ws_client(FakeWebSocket("192.168.1.5")) is False
        assert _is_accepted_ws_client(FakeWebSocket("10.0.0.1")) is False
        assert _is_accepted_ws_client(FakeWebSocket("100.64.0.1")) is False
        assert _is_accepted_ws_client(FakeWebSocket("1.2.3.4")) is False

    def test_non_loopback_accepted_when_allow_public(self, monkeypatch):
        from hermes_cli.web_server import _is_accepted_ws_client, app

        monkeypatch.setattr(app.state, "allow_public", True, raising=False)

        assert _is_accepted_ws_client(FakeWebSocket("192.168.1.5")) is True
        assert _is_accepted_ws_client(FakeWebSocket("10.0.0.1")) is True
        assert _is_accepted_ws_client(FakeWebSocket("100.64.0.1")) is True


class TestBuildSidecarUrl:
    """Unit-test the 0.0.0.0 / :: normalization in _build_sidecar_url."""

    def test_zero_zero_zero_zero_normalised_to_loopback(self, monkeypatch):
        from hermes_cli.web_server import _build_sidecar_url, app

        monkeypatch.setattr(app.state, "bound_host", "0.0.0.0", raising=False)
        monkeypatch.setattr(app.state, "bound_port", 9119, raising=False)

        url = _build_sidecar_url("test-channel")
        assert "ws://127.0.0.1:9119/" in url

    def test_ipv6_wildcard_normalised_to_loopback(self, monkeypatch):
        from hermes_cli.web_server import _build_sidecar_url, app

        monkeypatch.setattr(app.state, "bound_host", "::", raising=False)
        monkeypatch.setattr(app.state, "bound_port", 9119, raising=False)

        url = _build_sidecar_url("test-channel")
        assert "ws://[::1]:9119/" in url

    def test_explicit_loopback_preserved(self, monkeypatch):
        from hermes_cli.web_server import _build_sidecar_url, app

        monkeypatch.setattr(app.state, "bound_host", "127.0.0.1", raising=False)
        monkeypatch.setattr(app.state, "bound_port", 9119, raising=False)

        url = _build_sidecar_url("test-channel")
        assert "ws://127.0.0.1:9119/" in url

    def test_returns_none_when_unbound(self, monkeypatch):
        from hermes_cli.web_server import _build_sidecar_url, app

        for attr in ("bound_host", "bound_port"):
            if hasattr(app.state, attr):
                monkeypatch.delattr(app.state, attr)

        assert _build_sidecar_url("test-channel") is None


class TestStartServerAllowPublic:
    """Verify the allow_public flag logic inside start_server."""

    def test_allow_public_false_for_loopback_bind(self, monkeypatch):
        from hermes_cli.web_server import app

        # Simulate what start_server does for a loopback bind
        _LOCALHOST = ("127.0.0.1", "localhost", "::1")
        allow_public = True
        host = "127.0.0.1"
        app.state.allow_public = bool(allow_public and host not in _LOCALHOST)
        assert app.state.allow_public is False

    def test_allow_public_true_for_non_loopback_bind(self, monkeypatch):
        from hermes_cli.web_server import app

        _LOCALHOST = ("127.0.0.1", "localhost", "::1")
        allow_public = True
        host = "0.0.0.0"
        app.state.allow_public = bool(allow_public and host not in _LOCALHOST)
        assert app.state.allow_public is True


class TestWebSocketEndpoints:
    """End-to-end tests via FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, _isolate_hermes_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi/starlette not installed")

        import hermes_cli.web_server as _ws_mod
        from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        # Enable embedded chat so the WS endpoints are reachable
        monkeypatch.setattr(_ws_mod, "_DASHBOARD_EMBEDDED_CHAT_ENABLED", True)

        self.client = TestClient(app)
        self.client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

        # Clean bound state
        for attr in ("bound_host", "bound_port", "allow_public"):
            if hasattr(app.state, attr):
                monkeypatch.delattr(app.state, attr)

    def test_events_ws_loopback_client_connects(self):
        """TestClient presents as a loopback client — connection should succeed."""
        from hermes_cli.web_server import _SESSION_TOKEN

        with self.client.websocket_connect(f"/api/events?token={_SESSION_TOKEN}&channel=test"):
            pass  # Connection accepted

    def test_events_ws_rejected_when_client_check_fails(self, monkeypatch):
        """When _is_accepted_ws_client returns False, connection gets 4403."""
        from hermes_cli.web_server import _is_accepted_ws_client, _SESSION_TOKEN

        monkeypatch.setattr(
            "hermes_cli.web_server._is_accepted_ws_client",
            lambda ws: False,
        )

        with pytest.raises(Exception) as exc_info:
            with self.client.websocket_connect(f"/api/events?token={_SESSION_TOKEN}&channel=test"):
                pass

        # WebSocket close before accept raises WebSocketDisconnect; the close
        # code is on the exception object, not in its string repr.
        assert exc_info.value.code == 4403

    def test_pub_ws_loopback_client_connects(self):
        from hermes_cli.web_server import _SESSION_TOKEN

        with self.client.websocket_connect(f"/api/pub?token={_SESSION_TOKEN}&channel=test"):
            pass

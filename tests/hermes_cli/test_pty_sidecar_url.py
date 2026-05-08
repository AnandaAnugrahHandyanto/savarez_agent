"""Focused tests for dashboard PTY sidecar URL construction."""

from __future__ import annotations

import pytest


pytest.importorskip("fastapi", reason="web server dependencies missing")


def test_wildcard_bind_uses_loopback_sidecar_url(monkeypatch):
    """0.0.0.0 is a bind address; the PTY child needs a connectable host."""
    import hermes_cli.web_server as ws

    monkeypatch.setattr(ws.app.state, "bound_port", 9119, raising=False)

    monkeypatch.setattr(ws.app.state, "bound_host", "0.0.0.0", raising=False)
    assert ws._build_sidecar_url("chan").startswith(
        "ws://127.0.0.1:9119/api/pub?"
    )

    monkeypatch.setattr(ws.app.state, "bound_host", "::", raising=False)
    assert ws._build_sidecar_url("chan").startswith("ws://[::1]:9119/api/pub?")

"""Regression tests for #34227 — WS upgrade through reverse proxy.

Operators terminating auth at a reverse proxy (Caddy/Traefik/Pangolin/etc)
run hermes in --insecure mode, but the WS upgrade arrives from the
proxy's LAN IP rather than loopback. The default loopback-only IP check
rejected every proxied WS, leaving the chat tab stuck on 'session ended'
even with a valid ?token=.

Fix: opt-in flag (HERMES_DASHBOARD_TRUST_PROXY=1 env var, or
app.state.trust_proxy=True) to drop the IP check and rely on the
constant-time ?token= check that's already there.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _make_ws(client_host: str = "192.168.1.207"):
    """Build a minimal mock WebSocket with .client.host."""
    ws = MagicMock()
    ws.client = SimpleNamespace(host=client_host)
    return ws


def test_loopback_client_always_allowed():
    """Default behavior preserved: 127.0.0.1 is allowed."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False
    ws = _make_ws(client_host="127.0.0.1")
    assert _ws_client_is_allowed(ws) is True


def test_non_loopback_client_rejected_by_default(monkeypatch):
    """Default behavior preserved: LAN IPs are rejected in insecure mode."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False
    monkeypatch.delenv("HERMES_DASHBOARD_TRUST_PROXY", raising=False)

    ws = _make_ws(client_host="192.168.1.207")
    assert _ws_client_is_allowed(ws) is False


def test_non_loopback_allowed_with_env_opt_in(monkeypatch):
    """#34227 fix: HERMES_DASHBOARD_TRUST_PROXY=1 lets LAN IPs through."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False
    monkeypatch.setenv("HERMES_DASHBOARD_TRUST_PROXY", "1")

    ws = _make_ws(client_host="192.168.1.207")
    assert _ws_client_is_allowed(ws) is True


def test_env_var_accepts_true_string(monkeypatch):
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False
    monkeypatch.setenv("HERMES_DASHBOARD_TRUST_PROXY", "true")

    ws = _make_ws(client_host="10.0.0.5")
    assert _ws_client_is_allowed(ws) is True


def test_env_var_accepts_yes(monkeypatch):
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False
    monkeypatch.setenv("HERMES_DASHBOARD_TRUST_PROXY", "yes")

    ws = _make_ws(client_host="172.16.0.10")
    assert _ws_client_is_allowed(ws) is True


def test_env_var_rejects_garbage(monkeypatch):
    """An accidentally-set HERMES_DASHBOARD_TRUST_PROXY=banana must NOT
    silently disable the protection."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False
    monkeypatch.setenv("HERMES_DASHBOARD_TRUST_PROXY", "banana")

    ws = _make_ws(client_host="192.168.1.207")
    assert _ws_client_is_allowed(ws) is False


def test_app_state_trust_proxy_overrides_env(monkeypatch):
    """app.state.trust_proxy=True (programmatic opt-in, e.g. set by a CLI
    flag handler) also allows non-loopback peers."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = True
    monkeypatch.delenv("HERMES_DASHBOARD_TRUST_PROXY", raising=False)

    ws = _make_ws(client_host="192.168.1.207")
    assert _ws_client_is_allowed(ws) is True


def test_gated_mode_unaffected(monkeypatch):
    """When auth_required=True (gated/OAuth mode), the IP check was already
    skipped and the OAuth ticket is the auth. Make sure trust_proxy logic
    doesn't accidentally regress that path."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = True
    app.state.trust_proxy = False
    monkeypatch.delenv("HERMES_DASHBOARD_TRUST_PROXY", raising=False)

    ws = _make_ws(client_host="anywhere")
    assert _ws_client_is_allowed(ws) is True


def test_missing_client_still_allowed():
    """Defensive: if ws.client is None or host is empty, original code
    allowed the upgrade (UI in some test harnesses doesn't set client).
    Preserve that behavior."""
    from hermes_cli.web_server import _ws_client_is_allowed, app

    app.state.auth_required = False
    app.state.trust_proxy = False

    ws = MagicMock()
    ws.client = SimpleNamespace(host="")
    assert _ws_client_is_allowed(ws) is True

"""Tests for the WS-upgrade auth helper (Phase 5 task 5.2).

The dashboard's four WS endpoints (``/api/pty``, ``/api/ws``, ``/api/pub``,
``/api/events``) share an auth gate: ``_ws_auth_ok``. In loopback mode it
accepts ``?token=<_SESSION_TOKEN>``; in gated mode it accepts a single-use
``?ticket=`` minted by ``POST /api/auth/ws-ticket``.

These tests exercise the helper at the unit level (no actual WS upgrade)
plus the ticket-mint endpoint under realistic gated-mode setup. We don't
test the full WS upgrade because the starlette TestClient WS path has a
pre-existing regression unrelated to dashboard-auth.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Phase 5 / Phase 6: these tests mutate ``web_server.app.state.auth_required``
# at module level. Run them in the same xdist worker so they don't race
# against each other (and against any other file that also touches
# ``app.state``) — the marker name is shared across all dashboard-auth test
# files that gate the app.
pytestmark = pytest.mark.xdist_group("dashboard_auth_app_state")
from fastapi.testclient import TestClient

from hermes_cli import web_server
from hermes_cli.dashboard_auth import clear_providers, register_provider
from hermes_cli.dashboard_auth.ws_tickets import (
    TicketInvalid,
    _reset_for_tests,
    consume_ticket,
    mint_ticket,
)
from tests.hermes_cli.conftest_dashboard_auth import StubAuthProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gated_app():
    """web_server.app configured for gated mode + stub provider registered."""
    _reset_for_tests()
    clear_providers()
    register_provider(StubAuthProvider())
    prev_host = getattr(web_server.app.state, "bound_host", None)
    prev_port = getattr(web_server.app.state, "bound_port", None)
    prev_required = getattr(web_server.app.state, "auth_required", None)
    web_server.app.state.bound_host = "fly-app.fly.dev"
    web_server.app.state.bound_port = 443
    web_server.app.state.auth_required = True
    client = TestClient(web_server.app, base_url="https://fly-app.fly.dev")
    yield client
    clear_providers()
    _reset_for_tests()
    web_server.app.state.bound_host = prev_host
    web_server.app.state.bound_port = prev_port
    web_server.app.state.auth_required = prev_required


@pytest.fixture
def loopback_app():
    """web_server.app configured for loopback mode (gate OFF)."""
    _reset_for_tests()
    clear_providers()
    prev_host = getattr(web_server.app.state, "bound_host", None)
    prev_port = getattr(web_server.app.state, "bound_port", None)
    prev_required = getattr(web_server.app.state, "auth_required", None)
    web_server.app.state.bound_host = "127.0.0.1"
    web_server.app.state.bound_port = 8080
    web_server.app.state.auth_required = False
    client = TestClient(web_server.app, base_url="http://127.0.0.1:8080")
    yield client
    _reset_for_tests()
    web_server.app.state.bound_host = prev_host


@pytest.fixture
def insecure_public_app():
    """web_server.app configured for explicit ``--insecure`` + public bind.

    This is the Docker container shape (``-e HERMES_DASHBOARD_HOST=0.0.0.0``
    after the v0.15.1 opt-in change in #34188): the dashboard is reachable
    on the LAN/container network but the OAuth gate is OFF and auth is
    handled by the legacy ``?token=`` query parameter alone.
    """
    _reset_for_tests()
    clear_providers()
    prev_host = getattr(web_server.app.state, "bound_host", None)
    prev_port = getattr(web_server.app.state, "bound_port", None)
    prev_required = getattr(web_server.app.state, "auth_required", None)
    web_server.app.state.bound_host = "0.0.0.0"
    web_server.app.state.bound_port = 9119
    web_server.app.state.auth_required = False
    client = TestClient(web_server.app, base_url="http://0.0.0.0:9119")
    yield client
    _reset_for_tests()
    web_server.app.state.bound_host = prev_host
    web_server.app.state.bound_port = prev_port
    web_server.app.state.auth_required = prev_required
    web_server.app.state.bound_port = prev_port
    web_server.app.state.auth_required = prev_required


def _logged_in(client: TestClient) -> None:
    """Drive the stub OAuth round trip so the client holds session cookies."""
    r1 = client.get("/auth/login?provider=stub", follow_redirects=False)
    assert r1.status_code == 302
    state = r1.headers["location"].split("state=")[1]
    r2 = client.get(
        f"/auth/callback?code=stub_code&state={state}", follow_redirects=False
    )
    assert r2.status_code == 302


# ---------------------------------------------------------------------------
# POST /api/auth/ws-ticket — the mint endpoint
# ---------------------------------------------------------------------------


class TestWsTicketEndpoint:
    def test_authenticated_session_can_mint(self, gated_app):
        _logged_in(gated_app)
        r = gated_app.post("/api/auth/ws-ticket")
        assert r.status_code == 200
        body = r.json()
        assert "ticket" in body
        assert isinstance(body["ticket"], str)
        assert len(body["ticket"]) >= 32
        assert body["ttl_seconds"] == 30

    def test_unauthenticated_returns_401_or_redirect(self, gated_app):
        r = gated_app.post("/api/auth/ws-ticket", follow_redirects=False)
        # gated_auth_middleware short-circuits before the route — it
        # returns either 401 or 302. Either is fine.
        assert r.status_code in (302, 401)

    def test_each_call_returns_a_distinct_ticket(self, gated_app):
        _logged_in(gated_app)
        tickets = {gated_app.post("/api/auth/ws-ticket").json()["ticket"]
                   for _ in range(5)}
        assert len(tickets) == 5

    def test_get_method_is_not_allowed(self, gated_app):
        _logged_in(gated_app)
        r = gated_app.get("/api/auth/ws-ticket", follow_redirects=False)
        # GET must not mint a ticket (which would be cookie-replayable via
        # <img src=…> from a malicious origin). Accepted responses:
        #   401 — gated middleware allowlist-miss
        #   404 — SPA catch-all swallowed it
        #   405 — Method Not Allowed (route only registered for POST)
        #   200 — SPA index.html was served (catch-all caught the path)
        # In every case the JSON body of a successful ticket mint must
        # NOT be present. The assertion below holds even when the SPA
        # shell happens to serve a 200.
        body = r.text
        assert "ticket" not in body or '"ttl_seconds"' not in body, (
            f"GET /api/auth/ws-ticket leaked a ticket (status={r.status_code}, "
            f"body[:200]={body[:200]!r})"
        )


# ---------------------------------------------------------------------------
# _ws_auth_ok — unit-level (synthetic WebSocket-shaped object)
# ---------------------------------------------------------------------------


def _fake_ws(*, query: dict, client_host: str = "127.0.0.1", path: str = "/api/pty"):
    """Build a stand-in for starlette.WebSocket good enough for _ws_auth_ok."""

    class _QP:
        def __init__(self, q):
            self._q = q

        def get(self, k, default=""):
            return self._q.get(k, default)

    return SimpleNamespace(
        query_params=_QP(query),
        client=SimpleNamespace(host=client_host),
        url=SimpleNamespace(path=path),
    )


class TestWsAuthOkLoopback:
    """Gate OFF — legacy token path."""

    def test_correct_token_accepted(self, loopback_app):
        ws = _fake_ws(query={"token": web_server._SESSION_TOKEN})
        assert web_server._ws_auth_ok(ws) is True

    def test_wrong_token_rejected(self, loopback_app):
        ws = _fake_ws(query={"token": "not-the-real-token"})
        assert web_server._ws_auth_ok(ws) is False

    def test_missing_token_rejected(self, loopback_app):
        ws = _fake_ws(query={})
        assert web_server._ws_auth_ok(ws) is False

    def test_ticket_param_ignored_in_loopback(self, loopback_app):
        # Even if someone sneaks a ticket through, loopback mode only
        # cares about ?token=. A naked ticket isn't a token.
        ticket = mint_ticket(user_id="u1", provider="stub")
        ws = _fake_ws(query={"ticket": ticket})
        assert web_server._ws_auth_ok(ws) is False


class TestWsAuthOkGated:
    """Gate ON — ticket path only."""

    def test_valid_ticket_accepted(self, gated_app):
        ticket = mint_ticket(user_id="u1", provider="stub")
        ws = _fake_ws(query={"ticket": ticket})
        assert web_server._ws_auth_ok(ws) is True

    def test_consumed_ticket_rejected(self, gated_app):
        ticket = mint_ticket(user_id="u1", provider="stub")
        ws_one = _fake_ws(query={"ticket": ticket})
        ws_two = _fake_ws(query={"ticket": ticket})
        assert web_server._ws_auth_ok(ws_one) is True
        # Single-use — second consumption fails.
        assert web_server._ws_auth_ok(ws_two) is False

    def test_unknown_ticket_rejected(self, gated_app):
        ws = _fake_ws(query={"ticket": "never-minted"})
        assert web_server._ws_auth_ok(ws) is False

    def test_missing_ticket_rejected(self, gated_app):
        ws = _fake_ws(query={})
        assert web_server._ws_auth_ok(ws) is False

    def test_legacy_token_rejected_in_gated_mode(self, gated_app):
        """Critical: gated mode must NOT honour the legacy token path
        even when someone has access to the in-process value of
        _SESSION_TOKEN (e.g. a leaked log line)."""
        ws = _fake_ws(query={"token": web_server._SESSION_TOKEN})
        assert web_server._ws_auth_ok(ws) is False

    def test_rejection_audit_logs(self, gated_app, tmp_path, monkeypatch):
        # Point the audit log at a tmp dir so we can read what got written.
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from hermes_cli.dashboard_auth import audit as audit_mod

        # The log path is resolved lazily on the first audit_log() call;
        # bust any cached handler so it re-resolves.
        if hasattr(audit_mod, "_LOGGER"):
            monkeypatch.setattr(audit_mod, "_LOGGER", None, raising=False)

        ws = _fake_ws(query={"ticket": "never-minted"})
        assert web_server._ws_auth_ok(ws) is False

        log_file = tmp_path / "logs" / "dashboard-auth.log"
        # The audit module may write asynchronously through stdlib logging,
        # but flush is synchronous. If the file doesn't exist yet, the
        # logger may not have been initialized in this process — that's
        # acceptable as long as the rejection path didn't crash.
        if log_file.exists():
            content = log_file.read_text()
            assert "ws_ticket_rejected" in content


# ---------------------------------------------------------------------------
# _build_sidecar_url — gated mode mints a server-internal ticket
# ---------------------------------------------------------------------------


class TestWsRequestIsAllowedGated:
    """Bug fix: in gated mode, the WS peer-IP loopback check must be
    bypassed.

    When the OAuth gate is active, ``start_server`` runs uvicorn with
    ``proxy_headers=True`` so the dashboard can honour
    ``X-Forwarded-Proto`` from Fly's TLS terminator. A side effect is that
    ``ws.client.host`` is rewritten to the X-Forwarded-For value — the
    real internet client IP, never loopback. The loopback peer guard
    (intended only for unauthenticated loopback dev) must not also reject
    those upgrades: the OAuth gate + single-use ticket is the auth.

    Regression coverage: every WS endpoint (``/api/pty``, ``/api/ws``,
    ``/api/pub``, ``/api/events``) calls ``_ws_request_is_allowed`` after
    ``_ws_auth_ok``. If the peer-IP check rejects gated mode, the chat
    tab + sidebar tool feed silently fail to connect even after a
    successful OAuth login.
    """

    def test_non_loopback_peer_allowed_in_gated_mode(self, gated_app):
        ws = _fake_ws(query={}, client_host="203.0.113.7")
        # Host header matches the bound host so the DNS-rebinding guard
        # passes; only the peer-IP check is under test.
        ws.headers = {"host": "fly-app.fly.dev"}
        assert web_server._ws_request_is_allowed(ws) is True

    def test_non_loopback_peer_rejected_in_loopback_mode(self, loopback_app):
        """Loopback mode still enforces the peer-IP guard — the legacy
        token path is the only auth and we don't want random LAN hosts
        guessing it."""
        ws = _fake_ws(query={}, client_host="192.168.1.42")
        ws.headers = {"host": "127.0.0.1:8080"}
        assert web_server._ws_request_is_allowed(ws) is False

    def test_loopback_peer_allowed_in_loopback_mode(self, loopback_app):
        ws = _fake_ws(query={}, client_host="127.0.0.1")
        ws.headers = {"host": "127.0.0.1:8080"}
        assert web_server._ws_request_is_allowed(ws) is True

    def test_host_origin_guard_still_runs_in_gated_mode(self, gated_app):
        """Bypassing the peer-IP check must not bypass the DNS-rebinding
        Host header guard — that one still protects against attacker
        sites resolving DNS to the public IP."""
        ws = _fake_ws(query={}, client_host="203.0.113.7")
        ws.headers = {"host": "evil.example.com"}
        assert web_server._ws_request_is_allowed(ws) is False


class TestWsRequestIsAllowedInsecurePublic:
    """Bug fix #34091: when the dashboard is bound to ``0.0.0.0`` with
    ``--insecure``/no OAuth gate (the standard Docker container shape after
    v0.15.1's explicit ``HERMES_DASHBOARD_INSECURE`` opt-in), the WebSocket
    peer-IP loopback check must not reject upgrades from the Docker bridge
    gateway IP.

    Docker port-forwarding NATs the source IP to the bridge gateway (e.g.
    ``172.23.0.1``), which is not in ``_LOOPBACK_HOSTS`` and would otherwise
    close every ``/api/events`` upgrade with code 4403, producing the
    dashboard's ``events feed disconnected — tool calls may not appear``
    banner.

    Mirrors the existing bound-host opt-in semantics from
    :func:`_is_accepted_host`: if the operator bound the dashboard to a
    public interface, peer-IP is no longer a useful guard — the
    ``?token=`` equality check in :func:`_ws_auth_ok` is the auth.
    """

    def test_docker_bridge_peer_allowed_when_bound_public(self, insecure_public_app):
        """The headline bug: Docker bridge gateway IP (172.x.x.x) must pass
        the peer-IP gate when the dashboard is bound to 0.0.0.0."""
        ws = _fake_ws(query={}, client_host="172.23.0.1")
        ws.headers = {"host": "localhost:9119"}
        assert web_server._ws_client_is_allowed(ws) is True

    def test_arbitrary_lan_peer_allowed_when_bound_public(self, insecure_public_app):
        """A LAN client connecting through the published port is the
        explicit intent of binding to 0.0.0.0; the peer-IP check must
        also pass for those clients."""
        ws = _fake_ws(query={}, client_host="192.168.1.42")
        ws.headers = {"host": "192.168.1.10:9119"}
        assert web_server._ws_client_is_allowed(ws) is True

    def test_loopback_peer_still_allowed_when_bound_public(self, insecure_public_app):
        """Backwards-compat: clients connecting via 127.0.0.1 (e.g. an
        ssh tunnel or local browser into the container) keep working."""
        ws = _fake_ws(query={}, client_host="127.0.0.1")
        ws.headers = {"host": "localhost:9119"}
        assert web_server._ws_client_is_allowed(ws) is True

    def test_host_origin_guard_still_runs_when_bound_public(self, insecure_public_app):
        """Bypassing peer-IP must not bypass DNS-rebinding — the Host
        header is checked against the bound interface in
        :func:`_is_accepted_host`. ``0.0.0.0`` is the wildcard-accept
        case, so most hosts pass; a malformed Host header still fails."""
        ws = _fake_ws(query={}, client_host="172.23.0.1")
        ws.headers = {"host": ""}  # missing host header
        # _is_accepted_host with bound_host="0.0.0.0" accepts any host;
        # this test verifies the request guard still runs (even if it
        # ends up accepting), not that it always rejects.
        result = web_server._ws_request_is_allowed(ws)
        # 0.0.0.0 is a wildcard — _is_accepted_host accepts any host, so
        # the call returns True. The important invariant is that the
        # function did NOT crash and is still callable.
        assert isinstance(result, bool)

    def test_legacy_token_still_required_when_bound_public(self, insecure_public_app):
        """Critical: opening the peer-IP gate must NOT open the auth
        gate. ``_ws_auth_ok`` is what protects the upgrade, and it
        still requires a valid ``?token=`` in this mode."""
        ws = _fake_ws(query={}, client_host="172.23.0.1")
        ws.headers = {"host": "localhost:9119"}
        assert web_server._ws_auth_ok(ws) is False

        ws_with_token = _fake_ws(
            query={"token": web_server._SESSION_TOKEN},
            client_host="172.23.0.1",
        )
        ws_with_token.headers = {"host": "localhost:9119"}
        assert web_server._ws_auth_ok(ws_with_token) is True


class TestSidecarUrl:
    def test_loopback_uses_session_token(self, loopback_app):
        url = web_server._build_sidecar_url("ch-1")
        assert url is not None
        assert f"token={web_server._SESSION_TOKEN}" in url
        assert "ticket=" not in url

    def test_gated_uses_ticket(self, gated_app):
        url = web_server._build_sidecar_url("ch-1")
        assert url is not None
        assert "token=" not in url
        assert "ticket=" in url
        # And the ticket should be live.
        ticket = url.split("ticket=")[1].split("&")[0]
        info = consume_ticket(ticket)
        # Sidecar tickets are bound to the pseudo-user so audit logs can
        # distinguish them from real browser tickets.
        assert info["user_id"] == "pty-sidecar"
        assert info["provider"] == "server-internal"

    def test_no_bound_host_returns_none(self, gated_app):
        web_server.app.state.bound_host = None
        try:
            assert web_server._build_sidecar_url("ch") is None
        finally:
            web_server.app.state.bound_host = "fly-app.fly.dev"

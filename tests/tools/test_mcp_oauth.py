"""Tests for tools/mcp_oauth.py — OAuth 2.1 PKCE support for MCP servers."""

import json
import os
import stat
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

import asyncio

from tools.mcp_oauth import (
    HermesTokenStorage,
    OAuthNonInteractiveError,
    build_oauth_auth,
    remove_oauth_tokens,
    _find_free_port,
    _can_open_browser,
    _is_interactive,
    _wait_for_callback,
    _make_callback_handler,
    _make_redirect_handler,
    _redirect_handler,
)


# ---------------------------------------------------------------------------
# HermesTokenStorage
# ---------------------------------------------------------------------------

class TestHermesTokenStorage:
    def test_roundtrip_tokens(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("test-server")

        import asyncio

        # Initially empty
        assert asyncio.run(storage.get_tokens()) is None

        # Save and retrieve
        mock_token = MagicMock()
        mock_token.model_dump.return_value = {
            "access_token": "abc123",
            "token_type": "Bearer",
            "refresh_token": "ref456",
        }
        asyncio.run(storage.set_tokens(mock_token))

        # File exists with correct permissions
        token_path = tmp_path / "mcp-tokens" / "test-server.json"
        assert token_path.exists()
        data = json.loads(token_path.read_text())
        assert data["access_token"] == "abc123"

    @pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX mode bits not enforced on Windows")
    def test_token_file_created_with_0o600(self, tmp_path, monkeypatch):
        """Tokens must land on disk at 0o600 with no umask-default exposure window.

        Regression for the TOCTOU race where ``write_text`` + post-write
        ``chmod`` briefly left credentials at the process umask (commonly
        0o644 = world-readable) before tightening to owner-only. Mirrors
        the fix shipped for ``agent/google_oauth.py`` in #19673.
        """
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("perm-test-server")

        import asyncio
        mock_token = MagicMock()
        mock_token.model_dump.return_value = {
            "access_token": "secret-abc",
            "token_type": "Bearer",
            "refresh_token": "secret-ref",
        }
        asyncio.run(storage.set_tokens(mock_token))

        token_path = tmp_path / "mcp-tokens" / "perm-test-server.json"
        assert token_path.exists()
        mode = stat.S_IMODE(token_path.stat().st_mode)
        assert mode == 0o600, f"token file mode {oct(mode)} != 0o600 — TOCTOU race regressed"

        parent_mode = stat.S_IMODE(token_path.parent.stat().st_mode)
        assert parent_mode == 0o700, (
            f"token parent dir mode {oct(parent_mode)} != 0o700 — siblings can traverse"
        )

    def test_roundtrip_client_info(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("test-server")
        import asyncio

        assert asyncio.run(storage.get_client_info()) is None

        mock_client = MagicMock()
        mock_client.model_dump.return_value = {
            "client_id": "hermes-123",
            "client_secret": "secret",
        }
        asyncio.run(storage.set_client_info(mock_client))

        client_path = tmp_path / "mcp-tokens" / "test-server.client.json"
        assert client_path.exists()

    def test_remove_cleans_up(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("test-server")

        # Create files
        d = tmp_path / "mcp-tokens"
        d.mkdir(parents=True)
        (d / "test-server.json").write_text("{}")
        (d / "test-server.client.json").write_text("{}")

        storage.remove()
        assert not (d / "test-server.json").exists()
        assert not (d / "test-server.client.json").exists()

    def test_has_cached_tokens(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("my-server")

        assert not storage.has_cached_tokens()

        d = tmp_path / "mcp-tokens"
        d.mkdir(parents=True)
        (d / "my-server.json").write_text('{"access_token": "x", "token_type": "Bearer"}')

        assert storage.has_cached_tokens()

    def test_corrupt_tokens_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("bad-server")

        d = tmp_path / "mcp-tokens"
        d.mkdir(parents=True)
        (d / "bad-server.json").write_text("NOT VALID JSON{{{")

        import asyncio
        assert asyncio.run(storage.get_tokens()) is None

    def test_corrupt_client_info_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("bad-server")

        d = tmp_path / "mcp-tokens"
        d.mkdir(parents=True)
        (d / "bad-server.client.json").write_text("GARBAGE")

        import asyncio
        assert asyncio.run(storage.get_client_info()) is None


# ---------------------------------------------------------------------------
# build_oauth_auth
# ---------------------------------------------------------------------------

class TestBuildOAuthAuth:
    def test_returns_oauth_provider(self, tmp_path, monkeypatch):
        try:
            from mcp.client.auth import OAuthClientProvider
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        auth = build_oauth_auth("test", "https://example.com/mcp")
        assert isinstance(auth, OAuthClientProvider)

    def test_returns_none_without_sdk(self, monkeypatch):
        import tools.mcp_oauth as mod
        monkeypatch.setattr(mod, "_OAUTH_AVAILABLE", False)
        result = build_oauth_auth("test", "https://example.com")
        assert result is None

    def test_pre_registered_client_id_stored(self, tmp_path, monkeypatch):
        try:
            from mcp.client.auth import OAuthClientProvider
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        build_oauth_auth("slack", "https://slack.example.com/mcp", {
            "client_id": "my-app-id",
            "client_secret": "my-secret",
            "scope": "channels:read",
        })

        client_path = tmp_path / "mcp-tokens" / "slack.client.json"
        assert client_path.exists()
        data = json.loads(client_path.read_text())
        assert data["client_id"] == "my-app-id"
        assert data["client_secret"] == "my-secret"

    def test_scope_passed_through(self, tmp_path, monkeypatch):
        try:
            from mcp.client.auth import OAuthClientProvider
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        provider = build_oauth_auth("scoped", "https://example.com/mcp", {
            "scope": "read write admin",
        })
        assert provider is not None
        assert provider.context.client_metadata.scope == "read write admin"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

class TestUtilities:
    def test_find_free_port_returns_int(self):
        port = _find_free_port()
        assert isinstance(port, int)
        assert 1024 <= port <= 65535

    def test_find_free_port_unique(self):
        """Two consecutive calls should return different ports (usually)."""
        ports = {_find_free_port() for _ in range(5)}
        # At least 2 different ports out of 5 attempts
        assert len(ports) >= 2

    def test_can_open_browser_false_in_ssh(self, monkeypatch):
        monkeypatch.setenv("SSH_CLIENT", "1.2.3.4 1234 22")
        assert _can_open_browser() is False

    def test_can_open_browser_false_without_display(self, monkeypatch):
        monkeypatch.delenv("SSH_CLIENT", raising=False)
        monkeypatch.delenv("SSH_TTY", raising=False)
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        # Mock os.name and uname for non-macOS, non-Windows
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(os, "uname", lambda: type("", (), {"sysname": "Linux"})())
        assert _can_open_browser() is False

    def test_can_open_browser_true_with_display(self, monkeypatch):
        monkeypatch.delenv("SSH_CLIENT", raising=False)
        monkeypatch.delenv("SSH_TTY", raising=False)
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(os, "name", "posix")
        assert _can_open_browser() is True


class TestRedirectHandlerSshHint:
    """_redirect_handler must print an SSH tunnel hint on remote sessions."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_ssh_hint_shown_on_ssh_session(self, monkeypatch, capsys):
        import tools.mcp_oauth as mco
        monkeypatch.setattr(mco, "_oauth_port", 49200)
        monkeypatch.setenv("SSH_CLIENT", "1.2.3.4 1234 22")
        monkeypatch.delenv("SSH_TTY", raising=False)
        monkeypatch.setattr(mco, "_can_open_browser", lambda: False)

        self._run(_redirect_handler("https://example.com/auth?foo=bar"))

        err = capsys.readouterr().err
        assert "49200" in err
        assert "ssh -N -L" in err
        assert "Remote session detected" in err

    def test_ssh_hint_shown_via_ssh_tty(self, monkeypatch, capsys):
        import tools.mcp_oauth as mco
        monkeypatch.setattr(mco, "_oauth_port", 49201)
        monkeypatch.delenv("SSH_CLIENT", raising=False)
        monkeypatch.setenv("SSH_TTY", "/dev/pts/1")
        monkeypatch.setattr(mco, "_can_open_browser", lambda: False)

        self._run(_redirect_handler("https://example.com/auth"))

        err = capsys.readouterr().err
        assert "49201" in err
        assert "ssh -N -L" in err

    def test_no_ssh_hint_on_local_session(self, monkeypatch, capsys):
        import tools.mcp_oauth as mco
        monkeypatch.setattr(mco, "_oauth_port", 49202)
        monkeypatch.delenv("SSH_CLIENT", raising=False)
        monkeypatch.delenv("SSH_TTY", raising=False)
        monkeypatch.setattr(mco, "_can_open_browser", lambda: True)
        monkeypatch.setattr("webbrowser.open", lambda url, **kw: True)

        self._run(_redirect_handler("https://example.com/auth"))

        err = capsys.readouterr().err
        assert "ssh -N -L" not in err

    def test_no_ssh_hint_when_port_not_set(self, monkeypatch, capsys):
        import tools.mcp_oauth as mco
        monkeypatch.setattr(mco, "_oauth_port", None)
        monkeypatch.setenv("SSH_CLIENT", "1.2.3.4 1234 22")
        monkeypatch.setattr(mco, "_can_open_browser", lambda: False)

        self._run(_redirect_handler("https://example.com/auth"))

        err = capsys.readouterr().err
        assert "ssh -N -L" not in err

    def test_bound_redirect_handler_uses_captured_port_for_ssh_hint(self, monkeypatch, capsys):
        import tools.mcp_oauth as mco

        monkeypatch.setattr(mco, "_oauth_port", 49299)
        monkeypatch.setenv("SSH_CLIENT", "1.2.3.4 1234 22")
        monkeypatch.setattr(mco, "_can_open_browser", lambda: False)
        mco._oauth_active_flow_claims.clear()
        mco._oauth_results_by_port.clear()
        mco._oauth_pending_ports.clear()

        handler = _make_redirect_handler(49203, ("server-a", "https://example.com/mcp"))
        self._run(handler("https://example.com/auth"))

        err = capsys.readouterr().err
        assert "49203" in err
        assert "49299" not in err
        assert "ssh -N -L 49203:127.0.0.1:49203" in err


# ---------------------------------------------------------------------------
# Path traversal protection
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """Verify server_name is sanitized to prevent path traversal."""

    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("../../.ssh/config")
        path = storage._tokens_path()
        # Should stay within mcp-tokens directory
        assert "mcp-tokens" in str(path)
        assert ".ssh" not in str(path.resolve())

    def test_dots_and_slashes_sanitized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("../../../etc/passwd")
        path = storage._tokens_path()
        resolved = path.resolve()
        assert resolved.is_relative_to((tmp_path / "mcp-tokens").resolve())

    def test_normal_name_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("my-mcp-server")
        assert "my-mcp-server.json" in str(storage._tokens_path())

    def test_special_chars_sanitized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        storage = HermesTokenStorage("server@host:8080/path")
        path = storage._tokens_path()
        assert "@" not in path.name
        assert ":" not in path.name
        assert "/" not in path.stem


# ---------------------------------------------------------------------------
# Callback handler isolation
# ---------------------------------------------------------------------------

class TestCallbackHandlerIsolation:
    """Verify concurrent OAuth flows don't share state."""

    def test_independent_result_dicts(self):
        _, result_a = _make_callback_handler()
        _, result_b = _make_callback_handler()

        result_a["auth_code"] = "code_A"
        result_b["auth_code"] = "code_B"

        assert result_a["auth_code"] == "code_A"
        assert result_b["auth_code"] == "code_B"

    def test_handler_writes_to_own_result(self):
        HandlerClass, result = _make_callback_handler()
        assert result["auth_code"] is None

        # Simulate a GET request
        handler = HandlerClass.__new__(HandlerClass)
        handler.path = "/callback?code=test123&state=mystate"
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_GET()

        assert result["auth_code"] == "test123"
        assert result["state"] == "mystate"

    def test_handler_captures_error(self):
        HandlerClass, result = _make_callback_handler()

        handler = HandlerClass.__new__(HandlerClass)
        handler.path = "/callback?error=access_denied"
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_GET()

        assert result["auth_code"] is None
        assert result["error"] == "access_denied"


# ---------------------------------------------------------------------------
# Port sharing
# ---------------------------------------------------------------------------

class TestOAuthPortSharing:
    """Verify build_oauth_auth and _wait_for_callback use the same port."""

    def test_port_stored_globally(self, tmp_path, monkeypatch):
        import tools.mcp_oauth as mod
        mod._oauth_port = None

        try:
            from mcp.client.auth import OAuthClientProvider
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        build_oauth_auth("test-port", "https://example.com/mcp")
        assert mod._oauth_port is not None
        assert isinstance(mod._oauth_port, int)
        assert 1024 <= mod._oauth_port <= 65535


# ---------------------------------------------------------------------------
# remove_oauth_tokens
# ---------------------------------------------------------------------------

class TestRemoveOAuthTokens:
    def test_removes_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        d = tmp_path / "mcp-tokens"
        d.mkdir()
        (d / "myserver.json").write_text("{}")
        (d / "myserver.client.json").write_text("{}")

        remove_oauth_tokens("myserver")

        assert not (d / "myserver.json").exists()
        assert not (d / "myserver.client.json").exists()

    def test_no_error_when_files_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        remove_oauth_tokens("nonexistent")  # should not raise


# ---------------------------------------------------------------------------
# Non-interactive / startup-safety tests
# ---------------------------------------------------------------------------

class TestIsInteractive:
    """_is_interactive() detects headless/daemon/container environments."""

    def test_false_when_stdin_not_tty(self, monkeypatch):
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = False
        monkeypatch.setattr("tools.mcp_oauth.sys.stdin", mock_stdin)
        assert _is_interactive() is False

    def test_true_when_stdin_is_tty(self, monkeypatch):
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = True
        monkeypatch.setattr("tools.mcp_oauth.sys.stdin", mock_stdin)
        assert _is_interactive() is True

    def test_false_when_stdin_has_no_isatty(self, monkeypatch):
        """Some environments replace stdin with an object without isatty()."""
        mock_stdin = object()  # no isatty attribute
        monkeypatch.setattr("tools.mcp_oauth.sys.stdin", mock_stdin)
        assert _is_interactive() is False


class TestWaitForCallbackNoBlocking:
    """_wait_for_callback() must never call input() — it raises instead."""

    def test_raises_on_timeout_instead_of_input(self):
        """When no auth code arrives, raises OAuthNonInteractiveError."""
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        async def instant_sleep(_seconds):
            pass

        with patch.object(mod.asyncio, "sleep", instant_sleep):
            with patch("builtins.input", side_effect=AssertionError("input() must not be called")):
                with pytest.raises(OAuthNonInteractiveError, match="callback timed out"):
                    asyncio.run(_wait_for_callback())


class TestSharedCallbackResultCleanup:
    """``_oauth_result`` must not leak across login attempts.

    If a prior flow exited (success, error, or timeout) and left a stale
    auth_code/state/error in the shared slot, a subsequent
    ``_wait_for_callback`` would wrongly accept it without ever seeing a
    real browser callback.
    """

    def _instant_sleep_patch(self):
        async def instant_sleep(_seconds):
            pass
        import tools.mcp_oauth as mod
        return patch.object(mod.asyncio, "sleep", instant_sleep)

    def test_timeout_clears_shared_result(self):
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        with self._instant_sleep_patch():
            with pytest.raises(OAuthNonInteractiveError):
                asyncio.run(_wait_for_callback())

        assert mod._oauth_result is None, (
            "timed-out callback must clear _oauth_result so the next login "
            "attempt cannot reuse stale state"
        )

    def test_error_clears_shared_result(self):
        """When the owner-waiter's callback returns ?error=…, the shared
        slot must be cleared so the next attempt starts fresh."""
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        async def push_error_then_sleep(_seconds):
            if mod._oauth_result is not None and mod._oauth_result["error"] is None:
                mod._oauth_result["error"] = "server_error"

        with patch.object(mod.asyncio, "sleep", push_error_then_sleep):
            with pytest.raises(RuntimeError, match="server_error"):
                asyncio.run(_wait_for_callback())

        assert mod._oauth_result is None, (
            "errored callback must clear _oauth_result so the next login "
            "attempt does not raise the prior flow's error"
        )

    def test_success_clears_shared_result(self):
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        async def push_code_then_sleep(_seconds):
            if mod._oauth_result is not None and mod._oauth_result["auth_code"] is None:
                mod._oauth_result["auth_code"] = "fresh-code"
                mod._oauth_result["state"] = "fresh-state"

        with patch.object(mod.asyncio, "sleep", push_code_then_sleep):
            code, state = asyncio.run(_wait_for_callback())

        assert code == "fresh-code"
        assert state == "fresh-state"
        assert mod._oauth_result is None, (
            "successful callback must clear _oauth_result so the next login "
            "attempt does not reuse the previous code"
        )

    def test_owner_bind_failure_raises_noninteractive_error(self):
        """Owner-branch bind failure must surface immediately.

        The owner waiter is the only candidate to populate the shared
        result dict, so a bind failure that is silently downgraded to
        "fall through to polling" leaves the waiter blocked until the
        5-minute timeout. Surface the failure as
        ``OAuthNonInteractiveError`` (the existing user-friendly
        callback-port message) and chain the underlying ``OSError`` via
        ``__cause__`` so debugging info is preserved without leaking the
        raw errno through the public API.
        """
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        underlying = OSError("address already in use")
        with patch.object(mod, "HTTPServer", side_effect=underlying):
            with pytest.raises(OAuthNonInteractiveError) as excinfo:
                asyncio.run(_wait_for_callback())

        assert isinstance(excinfo.value.__cause__, OSError)
        assert excinfo.value.__cause__ is underlying

        # Owner must roll back the shared slot it installed so the next
        # waiter doesn't poll a never-filled buffer.
        assert mod._oauth_result is None

    def test_build_oauth_auth_clears_stale_result(self, tmp_path, monkeypatch):
        """``build_oauth_auth`` must drop any stale shared result before the
        new flow begins, even if the previous flow leaked state."""
        try:
            from mcp.client.auth import OAuthClientProvider  # noqa: F401
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        import tools.mcp_oauth as mod

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # Simulate stale state from a crashed previous flow.
        mod._oauth_result = {
            "auth_code": "stale-code",
            "state": "stale-state",
            "error": None,
        }
        mod._oauth_result_active = False
        mod._oauth_results_by_port[mod._callback_result_key(12345)] = {
            "auth_code": "stale-map-code",
            "state": "stale-map-state",
            "error": None,
        }

        build_oauth_auth("fresh-flow", "https://example.com/mcp")

        assert mod._oauth_result is None
        assert mod._oauth_result_active is False
        assert mod._oauth_results_by_port == {}

    def test_concurrent_waiter_reuses_shared_result(self):
        """A second waiter on the same flow shares the first's result dict.

        It must not try to bind a fresh server (port is already taken) and
        must observe the auth_code the first waiter's handler captured.
        """
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        # First waiter installs the shared slot. Push a code so it returns
        # quickly; we capture the dict identity before cleanup runs.
        captured = {}

        async def push_and_capture(_seconds):
            if mod._oauth_result is not None and mod._oauth_result["auth_code"] is None:
                captured["slot"] = mod._oauth_result
                mod._oauth_result["auth_code"] = "shared-code"

        with patch.object(mod.asyncio, "sleep", push_and_capture):
            code1, _ = asyncio.run(_wait_for_callback())

        assert code1 == "shared-code"
        assert mod._oauth_result is None  # cleared by owner on exit

        # Now seed a fresh shared slot as if a sibling waiter had set it
        # up first. The new waiter should NOT own it and should NOT clear
        # it on its own exit (only the installer cleans up). It should,
        # however, observe the code already in the dict.
        sibling_slot = {"auth_code": "sibling-code", "state": "sibling-state", "error": None}
        mod._oauth_result = sibling_slot
        mod._oauth_result_active = True
        mod._oauth_result_port = mod._oauth_port
        sibling_key = mod._callback_result_key(mod._oauth_port)
        mod._oauth_results_by_port[sibling_key] = sibling_slot

        async def noop(_seconds):
            pass

        with patch.object(mod.asyncio, "sleep", noop):
            code2, state2 = asyncio.run(_wait_for_callback())

        assert code2 == "sibling-code"
        assert state2 == "sibling-state"
        # Non-owner does not clear the slot — sibling waiter still owns it.
        assert mod._oauth_result is sibling_slot
        # Cleanup for the next test.
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

    def test_provider_build_does_not_clear_active_shared_result(self, tmp_path, monkeypatch):
        """Provider construction must not erase a live listener's result slot."""
        try:
            from mcp.client.auth import OAuthClientProvider  # noqa: F401
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        import tools.mcp_oauth as mod

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        active_slot = {"auth_code": None, "state": None, "error": None}
        active_port = 12345
        mod._oauth_result = active_slot
        mod._oauth_result_active = True
        mod._oauth_result_port = active_port
        active_key = mod._callback_result_key(active_port)
        mod._oauth_results_by_port[active_key] = active_slot

        build_oauth_auth("fresh-flow", "https://example.com/mcp")

        assert mod._oauth_result is active_slot
        assert mod._oauth_result_active is True
        assert mod._oauth_results_by_port[active_key] is active_slot
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

    def test_reset_preserves_claim_before_listener_publish(self):
        """Provider reset must not drop a claim made before listener publish.

        OAuthClientProvider invokes the redirect handler (which shows the auth
        URL) before it invokes the callback waiter (which publishes
        _oauth_results_by_port and flips _oauth_result_active). In that gap the
        active-flow claim is the only guard preventing a different flow on the
        same explicit callback port from emitting a competing URL.
        """
        import tools.mcp_oauth as mod

        port = _find_free_port()
        flow_a = ("server-a", "https://a.example/mcp", (("client_id", '"a"'),))
        flow_b = ("server-b", "https://b.example/mcp", (("client_id", '"b"'),))
        flow_a_key = mod._callback_result_key(port, flow_a)
        stale_key = mod._callback_result_key(port + 1, flow_a)

        mod._oauth_result = {"auth_code": "stale", "state": None, "error": None}
        mod._oauth_result_active = False
        mod._oauth_result_port = port + 1
        mod._oauth_results_by_port.clear()
        mod._oauth_results_by_port[stale_key] = mod._oauth_result
        mod._oauth_pending_ports.clear()
        mod._oauth_active_flow_claims.clear()
        mod._oauth_active_flow_claims.add(flow_a_key)

        mod._reset_shared_callback_result()

        assert mod._oauth_result is None
        assert mod._oauth_result_port is None
        assert mod._oauth_results_by_port == {}
        assert flow_a_key in mod._oauth_active_flow_claims
        with pytest.raises(
            OAuthNonInteractiveError,
            match="already in use by another active OAuth flow",
        ):
            mod._claim_callback_flow(port, flow_b)

        mod._oauth_active_flow_claims.clear()

    def test_bind_failure_does_not_publish_unbacked_shared_result(self):
        """A failed owner bind must not expose a result dict for siblings to poll."""
        import tools.mcp_oauth as mod
        import asyncio

        mod._oauth_port = _find_free_port()
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

        with patch.object(mod, "HTTPServer", side_effect=OSError("address already in use")):
            with pytest.raises(OAuthNonInteractiveError):
                asyncio.run(_wait_for_callback())

        assert mod._oauth_result is None
        assert mod._oauth_result_active is False
        assert mod._oauth_result_port is None
        assert mod._oauth_results_by_port == {}

    def test_active_slot_reuse_is_scoped_to_callback_port(self):
        """A new flow on a different port must not poll another flow's result."""
        import tools.mcp_oauth as mod
        import asyncio

        active_slot = {"auth_code": "flow-a-code", "state": "flow-a-state", "error": None}
        flow_a_port = _find_free_port()
        flow_b_port = _find_free_port()
        while flow_b_port == flow_a_port:
            flow_b_port = _find_free_port()

        mod._oauth_port = flow_b_port
        mod._oauth_result = active_slot
        mod._oauth_result_active = True
        mod._oauth_result_port = flow_a_port
        mod._oauth_results_by_port.clear()
        flow_a_key = mod._callback_result_key(flow_a_port)
        flow_b_key = mod._callback_result_key(flow_b_port)
        mod._oauth_results_by_port[flow_a_key] = active_slot

        async def push_flow_b_code(_seconds):
            flow_b_slot = mod._oauth_results_by_port.get(flow_b_key)
            if flow_b_slot is not None and flow_b_slot["auth_code"] is None:
                flow_b_slot["auth_code"] = "flow-b-code"
                flow_b_slot["state"] = "flow-b-state"

        with patch.object(mod.asyncio, "sleep", push_flow_b_code):
            code, state = asyncio.run(_wait_for_callback())

        assert (code, state) == ("flow-b-code", "flow-b-state")
        assert mod._oauth_results_by_port[flow_a_key] is active_slot
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()

    def test_different_flow_on_active_same_port_is_rejected(self):
        """Two different OAuth flows sharing a live port must fail closed.

        The callback server is bound to one handler/result buffer. Until Hermes
        has a state-aware demux listener, a second flow on the same explicit
        port would either fail to bind or risk consuming the wrong code/state.
        """
        import tools.mcp_oauth as mod
        import asyncio

        port = _find_free_port()
        flow_a = ("server-a", "https://a.example/mcp", (("client_id", '"a"'),))
        flow_b = ("server-b", "https://b.example/mcp", (("client_id", '"b"'),))
        flow_a_slot = {"auth_code": "flow-a-code", "state": "flow-a-state", "error": None}
        flow_a_key = mod._callback_result_key(port, flow_a)

        mod._oauth_port = port
        mod._oauth_result = flow_a_slot
        mod._oauth_result_active = True
        mod._oauth_result_port = port
        mod._oauth_results_by_port.clear()
        mod._oauth_pending_ports.clear()
        mod._oauth_active_flow_claims.clear()
        mod._oauth_results_by_port[flow_a_key] = flow_a_slot

        with pytest.raises(
            OAuthNonInteractiveError,
            match="already in use by another active OAuth flow",
        ):
            asyncio.run(_wait_for_callback(port=port, flow_key=flow_b))

        assert mod._oauth_results_by_port[flow_a_key] is flow_a_slot
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()
        mod._oauth_pending_ports.clear()
        mod._oauth_active_flow_claims.clear()

    def test_sibling_waiters_for_same_flow_reuse_same_port_result(self):
        """Sibling waiters for the same flow still reuse listener/result."""
        import tools.mcp_oauth as mod
        import asyncio

        port = _find_free_port()
        flow_key = ("same-server", "https://same.example/mcp", (("client_id", '"same"'),))
        slot = {"auth_code": "same-flow-code", "state": "same-flow-state", "error": None}
        slot_key = mod._callback_result_key(port, flow_key)

        mod._oauth_port = port
        mod._oauth_result = slot
        mod._oauth_result_active = True
        mod._oauth_result_port = port
        mod._oauth_results_by_port.clear()
        mod._oauth_results_by_port[slot_key] = slot

        async def noop(_seconds):
            pass

        with patch.object(mod.asyncio, "sleep", noop):
            code, state = asyncio.run(_wait_for_callback(port=port, flow_key=flow_key))

        assert (code, state) == ("same-flow-code", "same-flow-state")
        assert mod._oauth_results_by_port[slot_key] is slot
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()


class TestBuildOAuthAuthNonInteractive:
    """build_oauth_auth() in non-interactive mode."""

    def test_noninteractive_without_cached_tokens_warns(self, tmp_path, monkeypatch, caplog):
        """Without cached tokens, non-interactive mode logs a clear warning."""
        try:
            from mcp.client.auth import OAuthClientProvider
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = False
        monkeypatch.setattr("tools.mcp_oauth.sys.stdin", mock_stdin)

        import logging
        with caplog.at_level(logging.WARNING, logger="tools.mcp_oauth"):
            auth = build_oauth_auth("atlassian", "https://mcp.atlassian.com/v1/mcp")

        assert auth is not None
        assert "no cached tokens found" in caplog.text.lower()
        assert "non-interactive" in caplog.text.lower()

    def test_noninteractive_with_cached_tokens_no_warning(self, tmp_path, monkeypatch, caplog):
        """With cached tokens, non-interactive mode logs no 'no cached tokens' warning."""
        try:
            from mcp.client.auth import OAuthClientProvider
        except ImportError:
            pytest.skip("MCP SDK auth not available")

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = False
        monkeypatch.setattr("tools.mcp_oauth.sys.stdin", mock_stdin)

        # Pre-populate cached tokens
        d = tmp_path / "mcp-tokens"
        d.mkdir(parents=True)
        (d / "atlassian.json").write_text(json.dumps({
            "access_token": "cached",
            "token_type": "Bearer",
        }))

        import logging
        with caplog.at_level(logging.WARNING, logger="tools.mcp_oauth"):
            auth = build_oauth_auth("atlassian", "https://mcp.atlassian.com/v1/mcp")

        assert auth is not None
        assert "no cached tokens found" not in caplog.text.lower()


# ---------------------------------------------------------------------------
# Extracted helper tests (Task 3 of MCP OAuth consolidation)
# ---------------------------------------------------------------------------


def test_build_client_metadata_basic():
    """_build_client_metadata returns metadata with expected defaults."""
    pytest.importorskip("mcp")
    from tools.mcp_oauth import _build_client_metadata, _configure_callback_port

    cfg = {"client_name": "Test Client"}
    _configure_callback_port(cfg)
    md = _build_client_metadata(cfg)

    assert md.client_name == "Test Client"
    assert "authorization_code" in md.grant_types
    assert "refresh_token" in md.grant_types


def test_build_client_metadata_without_secret_is_public():
    """Without client_secret, token endpoint auth is 'none' (public client)."""
    pytest.importorskip("mcp")
    from tools.mcp_oauth import _build_client_metadata, _configure_callback_port

    cfg = {}
    _configure_callback_port(cfg)
    md = _build_client_metadata(cfg)
    assert md.token_endpoint_auth_method == "none"


def test_build_client_metadata_with_secret_is_confidential():
    """With client_secret, token endpoint auth is 'client_secret_post'."""
    pytest.importorskip("mcp")
    from tools.mcp_oauth import _build_client_metadata, _configure_callback_port

    cfg = {"client_secret": "shh"}
    _configure_callback_port(cfg)
    md = _build_client_metadata(cfg)
    assert md.token_endpoint_auth_method == "client_secret_post"


def test_configure_callback_port_picks_free_port():
    """_configure_callback_port(0) picks a free port in the ephemeral range."""
    from tools.mcp_oauth import _configure_callback_port

    cfg = {"redirect_port": 0}
    port = _configure_callback_port(cfg)
    assert 1024 < port < 65536
    assert cfg["_resolved_port"] == port


def test_configure_callback_port_uses_explicit_port():
    """An explicit redirect_port is preserved."""
    from tools.mcp_oauth import _configure_callback_port

    cfg = {"redirect_port": 54321}
    port = _configure_callback_port(cfg)
    assert port == 54321
    assert cfg["_resolved_port"] == 54321


def test_manager_build_provider_clears_stale_result(tmp_path, monkeypatch):
    """The manager's provider-construction path must also reset the shared
    ``_oauth_result`` slot.

    ``build_oauth_auth`` already drops stale callback state before the new
    flow begins; ``MCPOAuthManager._build_provider`` bypasses
    ``build_oauth_auth`` entirely and constructs the provider directly,
    so without an explicit reset a crashed prior flow's auth_code/state/
    error could leak into the next ``_wait_for_callback``.
    """
    pytest.importorskip("mcp")

    import tools.mcp_oauth as mod
    from tools.mcp_oauth_manager import MCPOAuthManager

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    mod._oauth_result = {
        "auth_code": "stale-code",
        "state": "stale-state",
        "error": None,
    }

    manager = MCPOAuthManager()
    provider = manager.get_or_build_provider(
        "manager-fresh-flow",
        "https://example.com/mcp",
        None,
    )

    assert provider is not None
    assert mod._oauth_result is None


class TestConcurrentBindRace:
    """Regression for the bind/publish race in ``_wait_for_callback``.

    After one waiter's ``HTTPServer`` bind succeeds but before it publishes
    ``_oauth_results_by_port``, a concurrent waiter used to bind the same
    port, fail (port taken), see no published result, and raise
    ``OAuthNonInteractiveError`` — even though the first waiter was about to
    publish a live listener. The fix reserves an in-progress marker
    (``_oauth_pending_ports``) atomically with the decision to bind, so a
    concurrent waiter waits for that bind to resolve instead of racing it.
    """

    def _reset(self, mod, port):
        mod._oauth_port = port
        mod._oauth_result = None
        mod._oauth_result_active = False
        mod._oauth_result_port = None
        mod._oauth_results_by_port.clear()
        mod._oauth_pending_ports.clear()
        mod._oauth_active_flow_claims.clear()

    def test_waiter_waits_for_pending_binder_then_reuses_listener(self):
        """A waiter that finds the port mid-bind must wait for the binding
        sibling to publish, then reuse its listener — not bind and raise."""
        import tools.mcp_oauth as mod
        import asyncio

        port = _find_free_port()
        self._reset(mod, port)
        # Simulate a sibling that has committed to binding this flow: the
        # in-progress marker is set but no result is published yet.
        slot_key = mod._callback_result_key(port)
        mod._oauth_pending_ports.add(slot_key)

        published = {"auth_code": "raced-code", "state": "raced-state", "error": None}

        async def publish_during_poll(_seconds):
            # The binding sibling finishes: it publishes a live listener and
            # drops the in-progress marker.
            if slot_key in mod._oauth_pending_ports:
                mod._oauth_results_by_port[slot_key] = published
                mod._oauth_pending_ports.discard(slot_key)

        with patch.object(mod.asyncio, "sleep", publish_during_poll):
            code, state = asyncio.run(_wait_for_callback())

        assert (code, state) == ("raced-code", "raced-state")
        # The waiting sibling never owned the slot; it must leave it intact.
        assert mod._oauth_results_by_port[slot_key] is published
        self._reset(mod, port)

    def test_waiter_raises_when_pending_binder_fails_to_bind(self):
        """If the binding sibling abandons its bind (marker dropped, nothing
        published), the waiting sibling surfaces the bind failure."""
        import tools.mcp_oauth as mod
        import asyncio

        port = _find_free_port()
        self._reset(mod, port)
        slot_key = mod._callback_result_key(port)
        mod._oauth_pending_ports.add(slot_key)

        async def binder_fails_during_poll(_seconds):
            mod._oauth_pending_ports.discard(slot_key)

        with patch.object(mod.asyncio, "sleep", binder_fails_during_poll):
            with pytest.raises(OAuthNonInteractiveError, match="failed to bind"):
                asyncio.run(_wait_for_callback())

        self._reset(mod, port)

    def test_binder_clears_in_progress_marker_on_success(self):
        """The waiter that binds must publish a listener and drop its
        in-progress marker so siblings switch from waiting to reusing."""
        import tools.mcp_oauth as mod
        import asyncio

        port = _find_free_port()
        self._reset(mod, port)

        async def push_code_then_sleep(_seconds):
            if mod._oauth_result is not None and mod._oauth_result["auth_code"] is None:
                # While the listener is live, the marker must already be gone.
                assert mod._callback_result_key(port) not in mod._oauth_pending_ports
                mod._oauth_result["auth_code"] = "ok-code"

        with patch.object(mod.asyncio, "sleep", push_code_then_sleep):
            code, _ = asyncio.run(_wait_for_callback())

        assert code == "ok-code"
        assert mod._oauth_pending_ports == set()
        self._reset(mod, port)

    def test_binder_clears_in_progress_marker_on_bind_failure(self):
        """A failed bind must drop the in-progress marker so a waiting
        sibling stops waiting instead of hanging until the pending timeout."""
        import tools.mcp_oauth as mod
        import asyncio

        port = _find_free_port()
        self._reset(mod, port)

        with patch.object(mod, "HTTPServer", side_effect=OSError("address already in use")):
            with pytest.raises(OAuthNonInteractiveError):
                asyncio.run(_wait_for_callback())

        assert mod._oauth_pending_ports == set()
        assert mod._oauth_results_by_port == {}
        self._reset(mod, port)


class TestCallbackLogRedaction:
    """``log_message`` must not leak OAuth secrets into the debug log.

    ``BaseHTTPRequestHandler`` log lines embed the raw request line, which
    for the callback is ``GET /callback?code=...&state=...``. Logging that
    verbatim leaks the authorization code and CSRF state.
    """

    def test_log_message_redacts_code_and_state(self, caplog):
        import logging

        HandlerClass, _ = _make_callback_handler()
        handler = HandlerClass.__new__(HandlerClass)

        with caplog.at_level(logging.DEBUG, logger="tools.mcp_oauth"):
            handler.log_message(
                '"%s" %s %s',
                "GET /callback?code=secret-auth-code&state=secret-csrf HTTP/1.1",
                "200",
                "-",
            )

        assert "secret-auth-code" not in caplog.text
        assert "secret-csrf" not in caplog.text
        assert "code=REDACTED" in caplog.text
        assert "state=REDACTED" in caplog.text

    def test_log_message_redacts_error(self, caplog):
        import logging

        HandlerClass, _ = _make_callback_handler()
        handler = HandlerClass.__new__(HandlerClass)

        with caplog.at_level(logging.DEBUG, logger="tools.mcp_oauth"):
            handler.log_message(
                '"%s" %s %s',
                "GET /callback?error=access_denied_with_detail HTTP/1.1",
                "200",
                "-",
            )

        assert "access_denied_with_detail" not in caplog.text
        assert "error=REDACTED" in caplog.text

    def test_redact_helper_preserves_non_secret_text(self):
        from tools.mcp_oauth import _redact_callback_log

        msg = '"GET /callback?code=abc123&state=xyz789&scope=channels:read HTTP/1.1" 200 -'
        out = _redact_callback_log(msg)

        assert "abc123" not in out
        assert "xyz789" not in out
        assert "code=REDACTED" in out
        assert "state=REDACTED" in out
        # Non-secret query params and the rest of the line are untouched.
        assert "scope=channels:read" in out
        assert out.endswith('HTTP/1.1" 200 -')

    def test_redact_helper_noop_without_secrets(self):
        from tools.mcp_oauth import _redact_callback_log

        msg = '"GET /favicon.ico HTTP/1.1" 404 -'
        assert _redact_callback_log(msg) == msg


def test_build_oauth_auth_preserves_server_url_path():
    """server_url with path is forwarded to OAuthClientProvider unmodified.

    Regression for #16015: previously ``_parse_base_url`` stripped the path,
    collapsing ``https://mcp.notion.com/mcp`` to ``https://mcp.notion.com`` and
    breaking RFC 9728 protected-resource validation against servers whose PRM
    advertises a path-scoped resource (Notion). The MCP SDK strips the path
    itself for authorization-server discovery via
    ``OAuthContext.get_authorization_base_url``; Hermes must not pre-strip.
    """
    from tools import mcp_oauth

    captured: dict = {}

    class _FakeProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with patch.object(mcp_oauth, "_OAUTH_AVAILABLE", True), \
         patch.object(mcp_oauth, "OAuthClientProvider", _FakeProvider), \
         patch.object(mcp_oauth, "_is_interactive", return_value=True), \
         patch.object(mcp_oauth, "_maybe_preregister_client"), \
         patch.object(mcp_oauth, "HermesTokenStorage") as mock_storage_cls:
        mock_storage_cls.return_value = MagicMock(has_cached_tokens=lambda: True)
        build_oauth_auth(
            server_name="notion",
            server_url="https://mcp.notion.com/mcp",
            oauth_config={},
        )

    assert captured["server_url"] == "https://mcp.notion.com/mcp"


def test_redirect_handler_rejects_same_port_other_flow_before_emitting_url(monkeypatch):
    """Conflicting flows must fail before the second authorization URL is shown."""
    import asyncio
    import tools.mcp_oauth as mod

    port = _find_free_port()
    flow_a = ("server-a", "https://example.com/a", ())
    flow_b = ("server-b", "https://example.com/b", ())
    mod._oauth_active_flow_claims.clear()
    mod._oauth_results_by_port.clear()
    mod._oauth_pending_ports.clear()

    emitted: list[str] = []

    async def fake_redirect(url, callback_port=None):
        emitted.append(url)

    monkeypatch.setattr(mod, "_redirect_handler", fake_redirect)

    asyncio.run(mod._make_redirect_handler(port, flow_a)("https://auth.example/a"))
    with pytest.raises(OAuthNonInteractiveError, match="already in use"):
        asyncio.run(mod._make_redirect_handler(port, flow_b)("https://auth.example/b"))

    assert emitted == ["https://auth.example/a"]
    mod._oauth_active_flow_claims.clear()



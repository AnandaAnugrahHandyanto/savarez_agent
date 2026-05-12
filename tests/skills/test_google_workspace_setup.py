"""RED file-mode tests for the google-workspace OAuth setup script.

Background
==========
``skills/productivity/google-workspace/scripts/setup.py`` persists three
secret-bearing files under ``$HERMES_HOME``:

  * ``CLIENT_SECRET_PATH``     — the Google OAuth client_secret.json
  * ``TOKEN_PATH``             — the long-lived refresh token
  * ``PENDING_AUTH_PATH``      — PKCE code_verifier + state mid-flow

All three are written today with ``Path.write_text`` and never chmod'd
afterward, so under the typical ``umask 0o022`` they land at ``0o644``
— readable by every local user. This is the exact failure mode
addressed by #19673 (``agent/google_oauth.py``) and #21148
(``tools/mcp_oauth.py``). The Google Workspace skill is the last big
write-site still leaking.

These tests assert the writers land all three files at ``0o600``. They
will stay RED until the GREEN commit migrates the writers to the
``write_secret_json`` helper (or an inline ``os.open(O_EXCL, 0o600)``
+ ``os.fsync`` + ``atomic_replace`` pattern).

POSIX-only — Windows does not enforce POSIX mode bits.

We mock the OAuth ``Flow`` (no network), and isolate every file path
under ``tmp_path`` (no real ``~/.hermes`` access).
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX mode bits not enforced on Windows",
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills/productivity/google-workspace/scripts/setup.py"
)


# ---------------------------------------------------------------------------
# Fake OAuth Flow (avoids network/token exchange)
# ---------------------------------------------------------------------------


class _FakeCredentials:
    def __init__(self):
        self._payload = {
            "token": "access-token",
            "refresh_token": "refresh-token-XXX",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake-client-id",
            "client_secret": "fake-client-secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        }

    def to_json(self):
        return json.dumps(self._payload)


class _FakeFlow:
    """Minimal stand-in for ``google_auth_oauthlib.flow.Flow``."""

    last_instance: "_FakeFlow | None" = None

    def __init__(self, client_secrets_file, scopes, *,
                 redirect_uri=None, state=None, code_verifier=None,
                 autogenerate_code_verifier=False):
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes
        self.redirect_uri = redirect_uri
        self.state = state or "fake-state"
        self.code_verifier = code_verifier or "fake-code-verifier"
        self.autogenerate_code_verifier = autogenerate_code_verifier
        self.credentials = _FakeCredentials()
        _FakeFlow.last_instance = self

    @classmethod
    def from_client_secrets_file(cls, client_secrets_file, scopes, **kwargs):
        return cls(client_secrets_file, scopes, **kwargs)

    def authorization_url(self, **kwargs):
        return (
            f"https://auth.example/authorize?state={self.state}",
            self.state,
        )

    def fetch_token(self, **kwargs):
        # No network. Pretend success.
        return None


@pytest.fixture
def setup_module_fx(monkeypatch, tmp_path):
    """Load the setup script in isolation, with file paths pinned to tmp_path."""
    google_auth_module = types.ModuleType("google_auth_oauthlib")
    flow_module = types.ModuleType("google_auth_oauthlib.flow")
    flow_module.Flow = _FakeFlow
    google_auth_module.flow = flow_module
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib", google_auth_module)
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib.flow", flow_module)

    spec = importlib.util.spec_from_file_location(
        "google_workspace_setup_red_mode_test", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # Avoid pip / dep install side effects.
    monkeypatch.setattr(module, "_ensure_deps", lambda: None)

    # Pin every secret-bearing path under tmp_path so we never touch the
    # real ~/.hermes layout.
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setattr(module, "CLIENT_SECRET_PATH", hermes_home / "google_client_secret.json")
    monkeypatch.setattr(module, "TOKEN_PATH", hermes_home / "google_token.json")
    monkeypatch.setattr(
        module, "PENDING_AUTH_PATH", hermes_home / "google_oauth_pending.json",
        raising=False,
    )
    return module


@pytest.fixture
def client_secret_file(tmp_path):
    """A valid client_secret.json on disk that store_client_secret will accept."""
    src = tmp_path / "src_client_secret.json"
    src.write_text(json.dumps({
        "installed": {
            "client_id": "fake-client-id",
            "client_secret": "fake-client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }))
    return src


# ---------------------------------------------------------------------------
# store_client_secret → CLIENT_SECRET_PATH must be 0o600
# ---------------------------------------------------------------------------


def test_store_client_secret_writes_0o600_under_umask_0o022(
    setup_module_fx, client_secret_file
):
    """``store_client_secret`` must land CLIENT_SECRET_PATH at 0o600."""
    old_umask = os.umask(0o022)
    try:
        setup_module_fx.store_client_secret(str(client_secret_file))
    finally:
        os.umask(old_umask)

    target = setup_module_fx.CLIENT_SECRET_PATH
    assert target.exists(), "store_client_secret did not write CLIENT_SECRET_PATH"
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600, (
        f"CLIENT_SECRET_PATH mode 0o{mode:o} != 0o600 — "
        f"umask leaked client secret to other local users"
    )


# ---------------------------------------------------------------------------
# exchange_auth_code → TOKEN_PATH must be 0o600
# ---------------------------------------------------------------------------


def test_exchange_auth_code_writes_token_path_at_0o600(
    setup_module_fx, client_secret_file
):
    """``exchange_auth_code`` must land TOKEN_PATH at 0o600.

    The refresh token inside is a long-lived secret; ``umask 0o022``
    would otherwise leave it at 0o644 (world-readable).
    """
    # Pre-stage the client secret and a pending PKCE state file so
    # exchange_auth_code can proceed.
    setup_module_fx.CLIENT_SECRET_PATH.write_text(client_secret_file.read_text())
    setup_module_fx.PENDING_AUTH_PATH.write_text(
        json.dumps({"state": "fake-state", "code_verifier": "fake-code-verifier"})
    )

    old_umask = os.umask(0o022)
    try:
        setup_module_fx.exchange_auth_code("4/test-auth-code")
    finally:
        os.umask(old_umask)

    token_path = setup_module_fx.TOKEN_PATH
    assert token_path.exists(), "exchange_auth_code did not write TOKEN_PATH"
    mode = stat.S_IMODE(token_path.stat().st_mode)
    assert mode == 0o600, (
        f"TOKEN_PATH mode 0o{mode:o} != 0o600 — "
        f"umask leaked the refresh token to other local users"
    )


# ---------------------------------------------------------------------------
# get_auth_url → PENDING_AUTH_PATH must be 0o600 while it exists
# ---------------------------------------------------------------------------


def test_get_auth_url_writes_pending_auth_at_0o600(setup_module_fx, client_secret_file):
    """``get_auth_url`` must land PENDING_AUTH_PATH at 0o600.

    The pending file holds the PKCE ``code_verifier`` for the in-flight
    OAuth exchange. With ``umask 0o022`` and the current writer that
    file lands at 0o644 — another local user can read the code_verifier
    and (if they can intercept the auth code in transit) finish the
    OAuth dance themselves.
    """
    # Pre-stage the client secret so get_auth_url can proceed.
    setup_module_fx.CLIENT_SECRET_PATH.write_text(client_secret_file.read_text())

    old_umask = os.umask(0o022)
    try:
        setup_module_fx.get_auth_url()
    finally:
        os.umask(old_umask)

    pending = setup_module_fx.PENDING_AUTH_PATH
    assert pending.exists(), "get_auth_url did not write PENDING_AUTH_PATH"
    mode = stat.S_IMODE(pending.stat().st_mode)
    assert mode == 0o600, (
        f"PENDING_AUTH_PATH mode 0o{mode:o} != 0o600 — "
        f"umask leaked the PKCE code_verifier to other local users"
    )


# ---------------------------------------------------------------------------
# Parent dir of every credential path must be 0o700
# ---------------------------------------------------------------------------


def test_token_and_secret_parent_dir_is_0o700(setup_module_fx, client_secret_file):
    """All three credential paths share a parent dir; it must be 0o700.

    Loose parent dir (typical 0o755 from ``Path.mkdir`` under umask 0o022)
    lets other users ``cd`` into ``~/.hermes`` and ``ls`` the contents,
    leaking the existence and names of OAuth credential files even when
    those files themselves are 0o600.
    """
    # Stage the prerequisite state so all three writers run.
    setup_module_fx.CLIENT_SECRET_PATH.write_text(client_secret_file.read_text())
    setup_module_fx.PENDING_AUTH_PATH.write_text(
        json.dumps({"state": "fake-state", "code_verifier": "fake-code-verifier"})
    )

    old_umask = os.umask(0o022)
    try:
        setup_module_fx.store_client_secret(str(client_secret_file))
        setup_module_fx.exchange_auth_code("4/test-auth-code")
    finally:
        os.umask(old_umask)

    parent = setup_module_fx.CLIENT_SECRET_PATH.parent
    mode = stat.S_IMODE(parent.stat().st_mode)
    assert mode == 0o700, (
        f"credentials parent dir mode 0o{mode:o} != 0o700 — "
        f"other users can list OAuth credential filenames"
    )

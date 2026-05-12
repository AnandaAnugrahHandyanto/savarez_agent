"""RED file-mode tests for ``plugins/platforms/google_chat/oauth.py``.

Background
==========
The Google Chat user-OAuth helper persists three secret-bearing files
under ``$HERMES_HOME``:

  * ``_client_secret_path()``  → ``google_chat_user_client_secret.json``
  * ``_token_path(email)``     → per-user OAuth refresh token JSON
  * ``_pending_auth_path()``   → PKCE state + code_verifier for in-flight
                                  ``/setup-files`` exchanges

Today all three are written with ``Path.write_text``, which inherits
the process ``umask`` (typically ``0o022``) and never chmods the file
afterward. On shared hosts that leaves long-lived OAuth refresh tokens
at ``0o644`` — readable by every local user. Same TOCTOU class as
#19673 (``agent/google_oauth.py``) and #21148 (``tools/mcp_oauth.py``);
this helper is the last big writer that hasn't been migrated.

The matching GREEN commit will route all three writes through
``agent.secure_file_io.write_secret_json`` (or an inline
``os.open(O_EXCL, 0o600) + fsync + atomic_replace`` pattern).

POSIX-only — Windows does not enforce POSIX mode bits.

Everything is local to ``tmp_path``: ``HERMES_HOME`` is redirected via
monkeypatch and the ``hermes_constants.get_hermes_home`` import is
shadowed so no real OAuth dance and no real ``~/.hermes`` writes can
happen.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX mode bits not enforced on Windows",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_hermes_home(tmp_path, monkeypatch):
    """Redirect HERMES_HOME to a tmp dir and reset module cache.

    Both ``get_hermes_home`` (resolved at call time inside oauth.py) and
    ``HERMES_HOME`` env var are routed at ``tmp_path``, so no real
    ``~/.hermes`` writes can leak.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    # The module reads HERMES_HOME late (via _hermes_home() → get_hermes_home())
    # so just setting the env var is enough. Force-reload to be safe in case
    # an earlier test imported the module with a different env.
    if "plugins.platforms.google_chat.oauth" in sys.modules:
        del sys.modules["plugins.platforms.google_chat.oauth"]
    return home


@pytest.fixture
def client_secret_src(tmp_path):
    """A valid client_secret.json on disk that ``store_client_secret`` will accept."""
    src = tmp_path / "src_client_secret.json"
    src.write_text(json.dumps({
        "installed": {
            "client_id": "fake-chat-client-id",
            "client_secret": "fake-chat-client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }))
    return src


class _FakeChatCredentials:
    """Stand-in for ``google.oauth2.credentials.Credentials`` (just ``.to_json``)."""

    def to_json(self):
        return json.dumps({
            "token": "chat-access-token",
            "refresh_token": "chat-refresh-token-XXX",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake-chat-client-id",
            "client_secret": "fake-chat-client-secret",
            "scopes": ["https://www.googleapis.com/auth/chat.messages.create"],
        })


# ---------------------------------------------------------------------------
# _persist_credentials → token file 0o600 / parent dir 0o700
# ---------------------------------------------------------------------------


def test_persist_credentials_writes_token_at_0o600_with_0o700_parent(
    isolated_hermes_home, monkeypatch
):
    """``_persist_credentials`` must land the per-user token at 0o600 / parent 0o700."""
    from plugins.platforms.google_chat import oauth as oauth_mod

    target = oauth_mod._token_path("user@example.com")
    creds = _FakeChatCredentials()

    old_umask = os.umask(0o022)
    try:
        oauth_mod._persist_credentials(creds, target)
    finally:
        os.umask(old_umask)

    assert target.exists(), "_persist_credentials did not write the token file"

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600, (
        f"per-user token file mode 0o{mode:o} != 0o600 — "
        f"umask leaked refresh token to other local users"
    )

    parent_mode = stat.S_IMODE(target.parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"per-user tokens dir mode 0o{parent_mode:o} != 0o700 — "
        f"other users can list per-user token filenames (PII leak)"
    )

    # Content survived.
    data = json.loads(target.read_text())
    assert data["refresh_token"] == "chat-refresh-token-XXX"


def test_persist_credentials_legacy_path_is_0o600(
    isolated_hermes_home, monkeypatch
):
    """The legacy single-user token path must also land at 0o600."""
    from plugins.platforms.google_chat import oauth as oauth_mod

    legacy = oauth_mod._legacy_token_path()
    creds = _FakeChatCredentials()

    old_umask = os.umask(0o022)
    try:
        oauth_mod._persist_credentials(creds, legacy)
    finally:
        os.umask(old_umask)

    assert legacy.exists(), "_persist_credentials did not write the legacy token"

    mode = stat.S_IMODE(legacy.stat().st_mode)
    assert mode == 0o600, (
        f"legacy token mode 0o{mode:o} != 0o600 — "
        f"umask leaked refresh token to other local users"
    )

    parent_mode = stat.S_IMODE(legacy.parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"HERMES_HOME mode 0o{parent_mode:o} != 0o700"
    )


# ---------------------------------------------------------------------------
# store_client_secret → client secret 0o600 / parent dir 0o700
# ---------------------------------------------------------------------------


def test_store_client_secret_writes_0o600_with_0o700_parent(
    isolated_hermes_home, client_secret_src, monkeypatch
):
    """``store_client_secret`` must land the client_secret.json at 0o600."""
    from plugins.platforms.google_chat import oauth as oauth_mod

    old_umask = os.umask(0o022)
    try:
        oauth_mod.store_client_secret(str(client_secret_src))
    finally:
        os.umask(old_umask)

    target = oauth_mod._client_secret_path()
    assert target.exists(), "store_client_secret did not write the client_secret.json"

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600, (
        f"client_secret.json mode 0o{mode:o} != 0o600 — "
        f"umask leaked Google OAuth client_secret to other local users"
    )

    parent_mode = stat.S_IMODE(target.parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"client_secret parent dir mode 0o{parent_mode:o} != 0o700"
    )


# ---------------------------------------------------------------------------
# _save_pending_auth → pending file 0o600 / parent dir 0o700
# ---------------------------------------------------------------------------


def test_save_pending_auth_writes_0o600_with_0o700_parent_per_user(
    isolated_hermes_home, monkeypatch
):
    """Per-user pending OAuth state must land at 0o600 / parent 0o700.

    The pending file holds the PKCE ``code_verifier``; with umask 0o022
    the current writer leaves it at 0o644, exposing the verifier to
    every local user mid-flow.
    """
    from plugins.platforms.google_chat import oauth as oauth_mod

    old_umask = os.umask(0o022)
    try:
        oauth_mod._save_pending_auth(
            state="fake-chat-state",
            code_verifier="fake-chat-code-verifier",
            email="user@example.com",
        )
    finally:
        os.umask(old_umask)

    pending = oauth_mod._pending_auth_path("user@example.com")
    assert pending.exists(), "_save_pending_auth did not write the pending file"

    mode = stat.S_IMODE(pending.stat().st_mode)
    assert mode == 0o600, (
        f"per-user pending OAuth file mode 0o{mode:o} != 0o600 — "
        f"umask leaked the PKCE code_verifier to other local users"
    )

    parent_mode = stat.S_IMODE(pending.parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"per-user pending OAuth dir mode 0o{parent_mode:o} != 0o700"
    )


def test_save_pending_auth_writes_0o600_legacy_single_user(
    isolated_hermes_home, monkeypatch
):
    """Legacy (no-email) pending file path must also land at 0o600."""
    from plugins.platforms.google_chat import oauth as oauth_mod

    old_umask = os.umask(0o022)
    try:
        oauth_mod._save_pending_auth(
            state="fake-chat-state",
            code_verifier="fake-chat-code-verifier",
            email=None,
        )
    finally:
        os.umask(old_umask)

    pending = oauth_mod._legacy_pending_path()
    assert pending.exists(), "_save_pending_auth did not write the legacy pending file"

    mode = stat.S_IMODE(pending.stat().st_mode)
    assert mode == 0o600, (
        f"legacy pending OAuth file mode 0o{mode:o} != 0o600 — "
        f"umask leaked the PKCE code_verifier to other local users"
    )

    parent_mode = stat.S_IMODE(pending.parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"HERMES_HOME mode 0o{parent_mode:o} != 0o700"
    )

"""Regression guard: pairing-approved users must pass ``_is_allowed_user``.

Before this fix, ``DiscordAdapter._is_allowed_user`` only consulted the
``DISCORD_ALLOWED_USERS`` and ``DISCORD_ALLOWED_ROLES`` env-var allowlists.
The pairing store (the data file behind ``hermes pairing approve discord
<code>``) was never checked. Result: any deployment that set
``DISCORD_ALLOWED_USERS`` to lock the bot down by default dropped messages
from paired users at ``gateway/platforms/discord.py:765-771``, long before
the pairing-aware authorizer in ``gateway/run.py:_is_user_authorized``
ever ran. The pairing flow was effectively dead config.

This module covers the three cases the fix promises:
  1. No allowlist set -> everyone passes (existing behavior).
  2. Allowlist set, user neither listed nor paired -> dropped.
  3. Allowlist set, user not listed but paired -> passes (new behavior).
"""

from types import SimpleNamespace

import pytest

from gateway.platforms.discord import DiscordAdapter


def _make_adapter(allowed_users=None, paired_users=None):
    """Build a minimal DiscordAdapter that skips ``__init__``.

    Follows the same ``object.__new__`` pattern documented at
    ``gateway/platforms/discord.py:2217-2219`` (AGENTS.md pitfall #17).
    """
    adapter = object.__new__(DiscordAdapter)
    adapter._allowed_user_ids = set(allowed_users or [])
    adapter._allowed_role_ids = set()

    approved = set(paired_users or [])

    class _FakeStore:
        def is_approved(self, platform, user_id):
            return platform == "discord" and user_id in approved

    adapter.gateway_runner = SimpleNamespace(pairing_store=_FakeStore())
    return adapter


def test_no_allowlist_set_allows_everyone():
    """Backwards-compatible default: empty allowlists -> trust everyone."""
    adapter = _make_adapter(allowed_users=None, paired_users=None)
    assert adapter._is_allowed_user("999", author=None, guild=None, is_dm=True) is True


def test_allowlist_miss_without_pairing_is_rejected():
    """Regression guard: env-var allowlist still gates unknown users."""
    adapter = _make_adapter(allowed_users={"111"}, paired_users=None)
    assert adapter._is_allowed_user("222", author=None, guild=None, is_dm=True) is False


def test_allowlist_miss_with_pairing_is_authorized():
    """New behavior: paired users pass even when not in DISCORD_ALLOWED_USERS."""
    adapter = _make_adapter(allowed_users={"111"}, paired_users={"222"})
    assert adapter._is_allowed_user("222", author=None, guild=None, is_dm=True) is True


def test_pairing_store_exception_falls_back_to_deny():
    """Defensive: if the pairing store raises, treat the user as unpaired."""

    class _BrokenStore:
        def is_approved(self, platform, user_id):
            raise RuntimeError("disk on fire")

    adapter = object.__new__(DiscordAdapter)
    adapter._allowed_user_ids = {"111"}
    adapter._allowed_role_ids = set()
    adapter.gateway_runner = SimpleNamespace(pairing_store=_BrokenStore())

    assert adapter._user_is_paired("222") is False
    assert adapter._is_allowed_user("222", author=None, guild=None, is_dm=True) is False


def test_user_is_paired_handles_missing_gateway_runner(monkeypatch):
    """Fallback path: when no runner is attached, create a local PairingStore."""
    adapter = object.__new__(DiscordAdapter)
    adapter._allowed_user_ids = set()
    adapter._allowed_role_ids = set()
    # No gateway_runner attribute at all -- the helper must not raise.

    calls = []

    class _StubStore:
        def __init__(self):
            calls.append("init")

        def is_approved(self, platform, user_id):
            return platform == "discord" and user_id == "approved-from-fallback"

    import gateway.pairing as pairing_mod
    monkeypatch.setattr(pairing_mod, "PairingStore", _StubStore)

    assert adapter._user_is_paired("approved-from-fallback") is True
    assert adapter._user_is_paired("someone-else") is False
    assert calls, "PairingStore fallback constructor should be called"

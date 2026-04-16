"""Regression tests for topic/channel skill auto-injection after /new or /reset.

Covers the fix in PR #6521 (Issue #6508):

Before the fix:
    1. User sends ``/new`` — ``reset_session`` creates a fresh SessionEntry
       with ``created_at == updated_at``.
    2. User sends the next message.
    3. ``get_or_create_session`` finds the entry and mutates
       ``entry.updated_at = now`` (microseconds after ``created_at``).
    4. ``run._handle_message_with_agent`` checks
       ``_is_new_session = (created_at == updated_at) or was_auto_reset``.
       Both are False → ``_is_new_session = False`` → topic/channel skills
       are silently skipped for the first message of a manually reset session.

After the fix:
    ``reset_session`` stamps the new entry with ``is_fresh_reset=True``.
    ``run._handle_message_with_agent`` ORs this into ``_is_new_session`` and
    consumes the flag immediately after the check, so subsequent messages are
    treated as continuing the session.
"""
from datetime import datetime, timedelta

import pytest

from gateway.config import GatewayConfig, Platform, SessionResetPolicy
from gateway.session import SessionSource, SessionStore, build_session_key


def _make_store(tmp_path, policy=None):
    config = GatewayConfig()
    if policy:
        config.default_reset_policy = policy
    return SessionStore(sessions_dir=tmp_path, config=config)


def _make_source(chat_id="123", user_id="u1"):
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=chat_id,
        user_id=user_id,
    )


def _is_new_session(entry) -> bool:
    """Mirror of the check in ``run._handle_message_with_agent``.

    Kept in-sync with the production predicate so this test fails loudly if
    the upstream logic regresses.
    """
    return (
        entry.created_at == entry.updated_at
        or getattr(entry, "was_auto_reset", False)
        or getattr(entry, "is_fresh_reset", False)
    )


class TestResetSessionSetsFreshFlag:
    def test_reset_session_sets_is_fresh_reset(self, tmp_path):
        store = _make_store(tmp_path)
        source = _make_source()

        original = store.get_or_create_session(source)
        reset_entry = store.reset_session(original.session_key)

        assert reset_entry is not None
        assert reset_entry.is_fresh_reset is True
        assert reset_entry.session_id != original.session_id

    def test_reset_session_returns_none_for_unknown_key(self, tmp_path):
        store = _make_store(tmp_path)

        assert store.reset_session("no-such-key") is None

    def test_fresh_flag_does_not_leak_to_auto_reset_path(self, tmp_path):
        store = _make_store(tmp_path)
        source = _make_source()

        entry = store.get_or_create_session(source)

        assert entry.is_fresh_reset is False
        assert entry.was_auto_reset is False


class TestIsNewSessionAfterManualReset:
    def test_fresh_flag_wins_even_after_updated_at_bump(self, tmp_path):
        store = _make_store(
            tmp_path,
            policy=SessionResetPolicy(mode="idle", idle_minutes=60),
        )
        source = _make_source()

        store.get_or_create_session(source)
        session_key = build_session_key(source)
        store.reset_session(session_key)

        entry = store.get_or_create_session(source)

        assert entry.updated_at >= entry.created_at
        assert entry.is_fresh_reset is True
        assert _is_new_session(entry) is True

    def test_flag_consumption_restores_normal_behavior(self, tmp_path):
        store = _make_store(tmp_path)
        source = _make_source()

        store.get_or_create_session(source)
        store.reset_session(build_session_key(source))

        first_after_reset = store.get_or_create_session(source)
        assert _is_new_session(first_after_reset) is True

        first_after_reset.is_fresh_reset = False

        import time
        time.sleep(0.001)

        second_after_reset = store.get_or_create_session(source)
        assert second_after_reset.is_fresh_reset is False
        assert _is_new_session(second_after_reset) is False

    def test_vanilla_session_is_not_treated_as_new_on_followup(self, tmp_path):
        store = _make_store(tmp_path)
        source = _make_source()

        first = store.get_or_create_session(source)
        assert _is_new_session(first) is True

        import time
        time.sleep(0.001)

        second = store.get_or_create_session(source)
        assert second.session_id == first.session_id
        assert second.is_fresh_reset is False
        assert _is_new_session(second) is False


class TestAutoResetPathsUnaffected:
    def test_idle_auto_reset_does_not_set_is_fresh_reset(self, tmp_path):
        store = _make_store(
            tmp_path,
            policy=SessionResetPolicy(mode="idle", idle_minutes=1),
        )
        source = _make_source()

        first = store.get_or_create_session(source)
        first.updated_at = datetime.now() - timedelta(minutes=5)
        store._save()

        second = store.get_or_create_session(source)
        assert second.session_id != first.session_id
        assert second.was_auto_reset is True
        assert second.is_fresh_reset is False

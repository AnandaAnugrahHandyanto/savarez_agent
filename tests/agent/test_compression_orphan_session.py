"""Regression tests for #33906 — compression split must not create orphan sessions.

When context compression triggers a session rotation, the old session is
ended in state.db and a new one is created.  If ``create_session()`` fails
(e.g. transient SQLite lock contention), the agent must roll back its
``session_id`` to the old value so it never runs with an orphan session that
has no state.db row.
"""

from __future__ import annotations

import sqlite3
import time as _time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(session_id: str = "20260101_120000_abc123"):
    """Build a minimal agent-like object for compress_context."""
    agent = MagicMock()
    # Use real attribute (not mock) so assignment sticks
    agent.session_id = session_id
    agent.platform = "test"
    agent.model = "test-model"
    agent._session_init_model_config = {}
    agent._session_db = MagicMock()
    agent._session_db.get_session_title.return_value = "Test Session"
    agent._session_db.create_session.return_value = session_id
    agent._session_db_created = True
    agent._cached_system_prompt = None
    agent._last_flushed_db_idx = 100
    agent._todo_store = MagicMock()
    agent._todo_store.format_for_injection.return_value = ""
    agent._invalidate_system_prompt = MagicMock()
    agent._build_system_prompt = MagicMock(return_value="system prompt")
    agent.commit_memory_session = MagicMock()
    agent.context_compressor = MagicMock()
    agent.context_compressor.compress = MagicMock(return_value=[{"role": "user", "content": "compressed"}])
    agent.context_compressor._last_compress_aborted = False
    agent.context_compressor.compression_count = 0
    agent._memory_manager = MagicMock()
    agent._gateway_session_key = None
    agent._emit_status = MagicMock()
    agent._emit_warning = MagicMock()
    agent._compression_feasibility_checked = True
    return agent


# ---------------------------------------------------------------------------
# Test 1: Normal compression — session_id rotates successfully
# ---------------------------------------------------------------------------

class TestCompressionSessionRotationSuccess:
    """Happy path: create_session succeeds, session_id rotates."""

    def test_session_id_rotates_on_success(self):
        from agent.conversation_compression import compress_context

        agent = _make_agent("old_session")
        old_sid = agent.session_id

        messages = [{"role": "user", "content": "hello"}] * 50

        with patch.dict("os.environ", {"HERMES_SESSION_SOURCE": "test"}):
            compress_context(agent, messages, system_message="sys")

        # session_id must have changed
        assert agent.session_id != old_sid
        # old session was ended
        agent._session_db.end_session.assert_called_once_with(old_sid, "compression")
        # new session was created with parent_session_id
        create_call = agent._session_db.create_session.call_args
        assert create_call.kwargs["parent_session_id"] == old_sid
        # flush cursor reset
        assert agent._last_flushed_db_idx == 0


# ---------------------------------------------------------------------------
# Test 2: Retry on sqlite3.OperationalError
# ---------------------------------------------------------------------------

class TestCompressionRetryOnLock:
    """create_session retries on transient SQLite lock errors."""

    def test_retries_on_operational_error(self):
        from agent.conversation_compression import compress_context

        agent = _make_agent("lock_session")

        # Fail first 2 attempts, succeed on 3rd
        call_count = [0]
        original_create = agent._session_db.create_session

        def _flaky_create(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise sqlite3.OperationalError("database is locked")
            return kwargs["session_id"]

        agent._session_db.create_session = _flaky_create

        messages = [{"role": "user", "content": "hello"}] * 50

        with patch.dict("os.environ", {"HERMES_SESSION_SOURCE": "test"}):
            compress_context(agent, messages, system_message="sys")

        # All 3 attempts used, session rotated
        assert call_count[0] == 3
        assert agent.session_id != "lock_session"

    def test_raises_after_3_retries_exhausted(self):
        from agent.conversation_compression import compress_context

        agent = _make_agent("exhaust_session")

        def _always_fail(**kwargs):
            raise sqlite3.OperationalError("database is locked")

        agent._session_db.create_session = _always_fail

        messages = [{"role": "user", "content": "hello"}] * 50

        with patch.dict("os.environ", {"HERMES_SESSION_SOURCE": "test"}):
            compress_context(agent, messages, system_message="sys")

        # After failure, session_id should be rolled back to original
        assert agent.session_id == "exhaust_session"
        # Old session should have been reopened
        agent._session_db.reopen_session.assert_called_once_with("exhaust_session")


# ---------------------------------------------------------------------------
# Test 3: Rollback session_id on non-SQLite exceptions
# ---------------------------------------------------------------------------

class TestCompressionRollbackOnFailure:
    """session_id rolls back when create_session fails for any reason."""

    def test_rollback_on_generic_exception(self):
        from agent.conversation_compression import compress_context

        agent = _make_agent("rollback_session")

        def _fail(**kwargs):
            raise IOError("disk full")

        agent._session_db.create_session = _fail

        messages = [{"role": "user", "content": "hello"}] * 50

        with patch.dict("os.environ", {"HERMES_SESSION_SOURCE": "test"}):
            compress_context(agent, messages, system_message="sys")

        # session_id must be rolled back
        assert agent.session_id == "rollback_session"
        # Old session reopened
        agent._session_db.reopen_session.assert_called_once_with("rollback_session")

    def test_no_rollback_when_old_session_id_not_set(self):
        """If end_session itself fails, old_session_id isn't in locals;
        rollback must not crash."""
        from agent.conversation_compression import compress_context

        agent = _make_agent("early_fail")
        # Make end_session fail so old_session_id is never assigned
        agent._session_db.end_session.side_effect = RuntimeError("boom")
        # create_session should never be called
        agent._session_db.create_session = MagicMock(
            side_effect=AssertionError("should not be called")
        )

        messages = [{"role": "user", "content": "hello"}] * 50

        # Should not raise — the outer try/except catches it
        with patch.dict("os.environ", {"HERMES_SESSION_SOURCE": "test"}):
            compress_context(agent, messages, system_message="sys")

        # session_id unchanged (no old_session_id was set to trigger rollback)
        assert agent.session_id == "early_fail"


# ---------------------------------------------------------------------------
# Test 4: Session_id is set AFTER successful create_session (not before)
# ---------------------------------------------------------------------------

class TestCompressionSessionIdOrdering:
    """Verify session_id is only mutated after state.db write succeeds."""

    def test_session_id_not_changed_if_create_fails(self):
        from agent.conversation_compression import compress_context

        agent = _make_agent("order_session")
        captured_sid = []

        def _failing_create(**kwargs):
            # Capture what session_id the agent has at create time
            captured_sid.append(agent.session_id)
            raise sqlite3.OperationalError("locked")

        agent._session_db.create_session = _failing_create

        messages = [{"role": "user", "content": "hello"}] * 50

        with patch.dict("os.environ", {"HERMES_SESSION_SOURCE": "test"}):
            compress_context(agent, messages, system_message="sys")

        # At the time create_session was called, session_id should still
        # be the old value (not the new generated one)
        assert captured_sid[0] == "order_session"
        # After failure, session_id is rolled back
        assert agent.session_id == "order_session"

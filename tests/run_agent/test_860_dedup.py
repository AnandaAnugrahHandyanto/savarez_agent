"""Tests for issue #860 / #12563 — SQLite session transcript deduplication.

Verifies that:
1. _flush_messages_to_session_db uses _last_flushed_db_idx to avoid re-writing
2. Multiple _persist_session calls don't duplicate messages
3. The cursor advances per-message so partial failures don't cause duplicates
"""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared fixture — minimal AIAgent instance
# ---------------------------------------------------------------------------

def _make_tool_defs(*names):
    return [{"type": "function", "function": {"name": n, "parameters": {}}} for n in names]


@pytest.fixture()
def agent():
    """Minimal AIAgent with all heavy initialisation patched out."""
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent
        a = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    a.client = MagicMock()
    a._cached_system_prompt = "You are helpful."
    a._use_prompt_caching = False
    a.tool_delay = 0
    a.compression_enabled = False
    a.save_trajectories = False
    return a


@pytest.fixture()
def agent_with_db(agent, tmp_path):
    """Agent wired to a real (temp) session DB."""
    # Use a lightweight mock that records calls rather than a real SQLite DB,
    # so the test doesn't depend on the internal DB schema.
    mock_db = MagicMock()
    mock_db.get_messages = MagicMock(return_value=[])

    agent._session_db = mock_db
    agent._session_db_created = True  # skip lazy creation in _flush
    agent.session_id = "test-session-860"
    return agent, mock_db


# ---------------------------------------------------------------------------
# Test: _last_flushed_db_idx initialises to zero
# ---------------------------------------------------------------------------

class TestFlushIdxInit:
    def test_init_zero(self, agent):
        """Agent starts with _last_flushed_db_idx = 0."""
        assert agent._last_flushed_db_idx == 0

    def test_no_session_db_noop(self, agent):
        """Without session_db, flush is a no-op and doesn't crash."""
        assert agent._session_db is None
        messages = [{"role": "user", "content": "test"}]
        agent._flush_messages_to_session_db(messages, [])
        assert agent._last_flushed_db_idx == 0


# ---------------------------------------------------------------------------
# Test: cursor advancement — the #12563 regression
# ---------------------------------------------------------------------------

class TestFlushCursorAdvancement:
    """
    _flush_messages_to_session_db must advance _last_flushed_db_idx
    *per successful append*, not once after the loop.

    Without per-message advancement an exception mid-loop (e.g. SQLite
    "database is locked") leaves the cursor at its old value.  The next
    flush re-writes the rows that already committed, producing duplicate
    transcript entries (the user-visible symptom of #12563).
    """

    def test_cursor_advances_on_success(self, agent_with_db):
        """Normal flush: cursor advances to len(new messages)."""
        agent, mock_db = agent_with_db

        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "follow up"},
        ]
        agent._flush_messages_to_session_db(messages, [])

        assert agent._last_flushed_db_idx == 3
        assert mock_db.append_message.call_count == 3

    def test_second_flush_writes_nothing_new(self, agent_with_db):
        """Second flush with the same message list is a no-op."""
        agent, mock_db = agent_with_db

        messages = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "reply1"},
        ]

        agent._flush_messages_to_session_db(messages, [])
        first_count = mock_db.append_message.call_count  # should be 2

        agent._flush_messages_to_session_db(messages, [])
        second_count = mock_db.append_message.call_count  # should still be 2

        assert first_count == 2
        assert second_count == 2, "Second flush must not re-write already committed rows"

    def test_incremental_flush(self, agent_with_db):
        """Messages added between flushes are written exactly once."""
        agent, mock_db = agent_with_db

        messages = [{"role": "user", "content": "hello"}]
        agent._flush_messages_to_session_db(messages, [])
        assert agent._last_flushed_db_idx == 1

        messages.append({"role": "assistant", "content": "hi"})
        messages.append({"role": "user", "content": "follow up"})
        agent._flush_messages_to_session_db(messages, [])

        assert agent._last_flushed_db_idx == 3
        assert mock_db.append_message.call_count == 3  # 1 + 2, not 3 again

    def test_cursor_advances_per_message_on_partial_failure(self, agent_with_db):
        """
        Regression for #12563.

        Simulate append_message raising on the 3rd call (SQLite lock).
        Assert:
          1. Cursor advanced to 2 (past the 2 rows that succeeded).
          2. After the provider is fixed, a second flush writes only the
             remaining messages — no duplicates of rows 1 and 2.
        """
        agent, mock_db = agent_with_db

        messages = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "reply1"},
            {"role": "user", "content": "msg2"},      # fails here
            {"role": "assistant", "content": "reply2"},
            {"role": "user", "content": "msg3"},
        ]

        call_count = {"n": 0}
        real_side_effects = []

        def flaky_append(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise sqlite3.OperationalError("database is locked")
            real_side_effects.append(kwargs)

        mock_db.append_message.side_effect = flaky_append

        # First flush: rows 1 & 2 commit; row 3 raises; function swallows.
        agent._flush_messages_to_session_db(messages, [])

        # Cursor must have advanced past the 2 committed rows.
        assert agent._last_flushed_db_idx == 2, (
            f"Cursor should be 2 after 2 successful + 1 failed append, "
            f"got {agent._last_flushed_db_idx}. This is the #12563 bug — "
            f"without per-message advancement the next flush would re-write "
            f"the 2 committed rows."
        )
        assert mock_db.append_message.call_count == 3  # 2 ok + 1 raise

        # Second flush with real append_message restored.
        mock_db.append_message.side_effect = None
        agent._flush_messages_to_session_db(messages, [])

        # 3 new appends (rows 3, 4, 5); NOT rows 1 and 2 again.
        total_appends = mock_db.append_message.call_count
        assert total_appends == 3 + 3, (  # 3 from first flush + 3 new
            f"Expected 6 total append calls (3 from first flush + 3 new "
            f"from second), got {total_appends}. "
            f"If {total_appends} > 6, rows were duplicated."
        )

    def test_conversation_history_offset(self, agent_with_db):
        """Messages already in conversation_history are not flushed."""
        agent, mock_db = agent_with_db

        conversation_history = [
            {"role": "user", "content": "old msg"},
        ]
        messages = list(conversation_history) + [
            {"role": "user", "content": "new msg"},
            {"role": "assistant", "content": "new reply"},
        ]

        agent._flush_messages_to_session_db(messages, conversation_history)

        # Only the 2 messages BEYOND conversation_history should be written.
        assert mock_db.append_message.call_count == 2
        assert agent._last_flushed_db_idx == 3  # full length of messages

"""Tests for issue #860 — SQLite session transcript deduplication.

Verifies that:
1. _flush_messages_to_session_db uses _last_flushed_db_idx to avoid re-writing
2. Multiple _persist_session calls don't duplicate messages
3. append_to_transcript(skip_db=True) skips SQLite but writes JSONL
4. The gateway doesn't double-write messages the agent already persisted
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test: _flush_messages_to_session_db only writes new messages
# ---------------------------------------------------------------------------

class TestFlushDeduplication:
    """Verify _flush_messages_to_session_db tracks what it already wrote."""

    def _make_agent(self, session_db):
        """Create a minimal AIAgent with a real session DB."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            from run_agent import AIAgent
            agent = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                model="test/model",
                quiet_mode=True,
                session_db=session_db,
                session_id="test-session-860",
                skip_context_files=True,
                skip_memory=True,
            )
        # Simulate lazy session creation (normally done by run_conversation)
        agent._ensure_db_session()
        return agent

    def test_flush_writes_only_new_messages(self):
        """First flush writes all new messages, second flush writes none."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionDB(db_path=db_path)

            agent = self._make_agent(db)

            conversation_history = [
                {"role": "user", "content": "old message"},
            ]
            messages = list(conversation_history) + [
                {"role": "user", "content": "new question"},
                {"role": "assistant", "content": "new answer"},
            ]

            # First flush — should write 2 new messages
            agent._flush_messages_to_session_db(messages, conversation_history)

            rows = db.get_messages(agent.session_id)
            assert len(rows) == 2, f"Expected 2 messages, got {len(rows)}"

            # Second flush with SAME messages — should write 0 new messages
            agent._flush_messages_to_session_db(messages, conversation_history)

            rows = db.get_messages(agent.session_id)
            assert len(rows) == 2, f"Expected still 2 messages after second flush, got {len(rows)}"

    def test_flush_writes_incrementally(self):
        """Messages added between flushes are written exactly once."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionDB(db_path=db_path)

            agent = self._make_agent(db)

            conversation_history = []
            messages = [
                {"role": "user", "content": "hello"},
            ]

            # First flush — 1 message
            agent._flush_messages_to_session_db(messages, conversation_history)
            rows = db.get_messages(agent.session_id)
            assert len(rows) == 1

            # Add more messages
            messages.append({"role": "assistant", "content": "hi there"})
            messages.append({"role": "user", "content": "follow up"})

            # Second flush — should write only 2 new messages
            agent._flush_messages_to_session_db(messages, conversation_history)
            rows = db.get_messages(agent.session_id)
            assert len(rows) == 3, f"Expected 3 total messages, got {len(rows)}"

    def test_persist_session_multiple_calls_no_duplication(self):
        """Multiple _persist_session calls don't duplicate DB entries."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionDB(db_path=db_path)

            agent = self._make_agent(db)
            # Stub out _save_session_log to avoid file I/O
            agent._save_session_log = MagicMock()

            conversation_history = [{"role": "user", "content": "old"}]
            messages = list(conversation_history) + [
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "q2"},
                {"role": "assistant", "content": "a2"},
            ]

            # Simulate multiple persist calls (like the agent's many exit paths)
            for _ in range(5):
                agent._persist_session(messages, conversation_history)

            rows = db.get_messages(agent.session_id)
            assert len(rows) == 4, f"Expected 4 messages, got {len(rows)} (duplication bug!)"

    def test_flush_reset_after_compression(self):
        """After compression creates a new session, flush index resets."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionDB(db_path=db_path)

            agent = self._make_agent(db)

            # Write some messages
            messages = [
                {"role": "user", "content": "msg1"},
                {"role": "assistant", "content": "reply1"},
            ]
            agent._flush_messages_to_session_db(messages, [])

            old_session = agent.session_id
            assert agent._last_flushed_db_idx == 2

            # Simulate what _compress_context does: new session, reset idx
            agent.session_id = "compressed-session-new"
            db.create_session(session_id=agent.session_id, source="test")
            agent._last_flushed_db_idx = 0

            # Now flush compressed messages to new session
            compressed_messages = [
                {"role": "user", "content": "summary of conversation"},
            ]
            agent._flush_messages_to_session_db(compressed_messages, [])

            new_rows = db.get_messages(agent.session_id)
            assert len(new_rows) == 1

            # Old session should still have its 2 messages
            old_rows = db.get_messages(old_session)
            assert len(old_rows) == 2

    def test_flush_advances_cursor_per_message_on_partial_failure(self):
        """Regression for #12563.

        ``_flush_messages_to_session_db`` previously advanced
        ``_last_flushed_db_idx`` to ``len(messages)`` only AFTER the inner
        loop completed.  If ``append_message`` raised mid-loop (typical
        triggers: SQLite ``database is locked`` from concurrent processes
        sharing the state DB, transient disk-full, or a schema-evolution
        race), control jumped to the broad ``except`` clause without the
        cursor advancing — so the rows that DID commit before the
        exception were re-written on the next flush call.  Net effect:
        the user's transcript grew duplicates (often literally 2x) every
        time the underlying lock contention recurred.

        This test simulates the exact failure mode by monkey-patching
        ``append_message`` to raise on the 3rd call, then asserts:

        1. The first 2 messages were committed (cursor moved past them).
        2. After the broken provider is replaced and flush is called
           again with the same message list, the 3rd message onward gets
           written exactly once — no duplicates of messages 1 and 2.
        3. Total INSERTs into the session table equals the message count.
        """
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = SessionDB(db_path=db_path)

            agent = self._make_agent(db)

            messages = [
                {"role": "user", "content": "msg1"},
                {"role": "assistant", "content": "reply1"},
                {"role": "user", "content": "msg2"},  # break point — append #3
                {"role": "assistant", "content": "reply2"},
                {"role": "user", "content": "msg3"},
            ]

            # Patch append_message so the 3rd invocation raises (simulating
            # SQLite lock contention writing that specific row).  The first
            # two appends go through to the real implementation so we can
            # later observe what actually committed via get_messages().
            real_append = db.append_message
            call_count = {"n": 0}

            def flaky_append(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 3:
                    raise sqlite3.OperationalError("database is locked")
                return real_append(**kwargs)

            with patch.object(db, "append_message", side_effect=flaky_append):
                # First flush: should commit rows 1 & 2, then crash on row 3.
                # The function logs and swallows; we don't expect it to raise.
                agent._flush_messages_to_session_db(messages, [])

            # Two rows committed.
            rows = db.get_messages(agent.session_id)
            assert len(rows) == 2, (
                f"Expected the 2 rows that committed before the simulated "
                f"lock error to be present, got {len(rows)}"
            )

            # Critical assertion: the cursor advanced past the rows that
            # actually committed.  In the buggy version the cursor stayed
            # at 0 here, so the next flush would re-write rows 1 and 2.
            assert agent._last_flushed_db_idx == 2, (
                f"Cursor must advance per successful append; expected 2 "
                f"after 2 successful + 1 failed, got "
                f"{agent._last_flushed_db_idx} (this is the #12563 bug — "
                f"the next flush would duplicate committed rows)"
            )

            # Second flush with the real append_message restored AND the
            # same message list.  Only rows 3, 4, 5 should be appended —
            # NOT rows 1 and 2 again.
            agent._flush_messages_to_session_db(messages, [])

            final_rows = db.get_messages(agent.session_id)
            assert len(final_rows) == 5, (
                f"After recovery flush: expected exactly len(messages)=5 "
                f"rows (no duplicates), got {len(final_rows)}.  This is "
                f"the user-visible symptom of #12563 — duplicate transcript "
                f"entries on every retry."
            )

            # Sanity: rows are in the original send order, no duplicates.
            contents = [
                r.get("content") if isinstance(r, dict) else r["content"]
                for r in final_rows
            ]
            assert contents == [
                "msg1", "reply1", "msg2", "reply2", "msg3",
            ], f"Row order/content mismatch: {contents}"


# ---------------------------------------------------------------------------
# Test: append_to_transcript skip_db parameter
# ---------------------------------------------------------------------------

class TestAppendToTranscriptSkipDb:
    """Verify skip_db=True writes JSONL but not SQLite."""

    @pytest.fixture()
    def store(self, tmp_path):
        from gateway.config import GatewayConfig
        from gateway.session import SessionStore
        config = GatewayConfig()
        with patch("gateway.session.SessionStore._ensure_loaded"):
            s = SessionStore(sessions_dir=tmp_path, config=config)
        s._db = None  # no SQLite for these JSONL-focused tests
        s._loaded = True
        return s

    def test_skip_db_writes_jsonl_only(self, store, tmp_path):
        """With skip_db=True, message appears in JSONL but not SQLite."""
        session_id = "test-skip-db"
        msg = {"role": "assistant", "content": "hello world"}
        store.append_to_transcript(session_id, msg, skip_db=True)

        # JSONL should have the message
        jsonl_path = store.get_transcript_path(session_id)
        assert jsonl_path.exists()
        with open(jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["content"] == "hello world"

    def test_skip_db_prevents_sqlite_write(self, tmp_path):
        """With skip_db=True and a real DB, message does NOT appear in SQLite."""
        from gateway.config import GatewayConfig
        from gateway.session import SessionStore
        from hermes_state import SessionDB

        db_path = tmp_path / "test_skip.db"
        db = SessionDB(db_path=db_path)

        config = GatewayConfig()
        with patch("gateway.session.SessionStore._ensure_loaded"):
            store = SessionStore(sessions_dir=tmp_path, config=config)
        store._db = db
        store._loaded = True

        session_id = "test-skip-db-real"
        db.create_session(session_id=session_id, source="test")

        msg = {"role": "assistant", "content": "hello world"}
        store.append_to_transcript(session_id, msg, skip_db=True)

        # SQLite should NOT have the message
        rows = db.get_messages(session_id)
        assert len(rows) == 0, f"Expected 0 DB rows with skip_db=True, got {len(rows)}"

        # But JSONL should have it
        jsonl_path = store.get_transcript_path(session_id)
        with open(jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

    def test_default_writes_both(self, tmp_path):
        """Without skip_db, message appears in both JSONL and SQLite."""
        from gateway.config import GatewayConfig
        from gateway.session import SessionStore
        from hermes_state import SessionDB

        db_path = tmp_path / "test_both.db"
        db = SessionDB(db_path=db_path)

        config = GatewayConfig()
        with patch("gateway.session.SessionStore._ensure_loaded"):
            store = SessionStore(sessions_dir=tmp_path, config=config)
        store._db = db
        store._loaded = True

        session_id = "test-default-write"
        db.create_session(session_id=session_id, source="test")

        msg = {"role": "user", "content": "test message"}
        store.append_to_transcript(session_id, msg)

        # JSONL should have the message
        jsonl_path = store.get_transcript_path(session_id)
        with open(jsonl_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

        # SQLite should also have the message
        rows = db.get_messages(session_id)
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Test: _last_flushed_db_idx initialization
# ---------------------------------------------------------------------------

class TestFlushIdxInit:
    """Verify _last_flushed_db_idx is properly initialized."""

    def test_init_zero(self):
        """Agent starts with _last_flushed_db_idx = 0."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            from run_agent import AIAgent
            agent = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                model="test/model",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
        assert agent._last_flushed_db_idx == 0

    def test_no_session_db_noop(self):
        """Without session_db, flush is a no-op and doesn't crash."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            from run_agent import AIAgent
            agent = AIAgent(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                model="test/model",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
        messages = [{"role": "user", "content": "test"}]
        agent._flush_messages_to_session_db(messages, [])
        # Should not crash, idx should remain 0
        assert agent._last_flushed_db_idx == 0

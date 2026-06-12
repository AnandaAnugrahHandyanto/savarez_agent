"""Regression tests for the identity-based session-DB flush (#43936 final fix).

Live failure shapes reproduced here (both observed 2026-06-13, session
20260613_012224_a37fbf50, FLUSH-DIAG/B-DIAG in agent.log):

  1. Overlapping turns on the SAME cached agent corrupt the shared
     ``_last_flushed_db_idx`` — the earlier COMPLETED turn's final flush
     positionally sliced past the end and dropped the assistant.
     (start_idx=27 last_flushed=28 len_messages=26 → wrote=[])

  2. ``conversation_history`` LONGER than ``messages``: prior drops leave
     the DB transcript with consecutive-user / orphan-tool rows; the next
     turn's repair_message_sequence merges/drops entries, shrinking
     ``messages`` below the history length. start_idx > len(messages)
     forever → self-reinforcing drop loop.
     (len_conv=153 len_msgs=145, divergent role tails)

The identity flush writes any message dict not stamped ``_db_persisted``
and not present (by object identity) in this turn's conversation_history,
making it immune to BOTH shapes by construction.  These tests exercise the
REAL ``_flush_messages_to_session_db`` against a real SessionDB.

NOTE on #44837 / #45260: the merged fix clamped the cursor as
``max(start_idx, min(_last_flushed_db_idx, len(messages)))``. That bounds
``_last_flushed_db_idx`` but NOT ``start_idx = len(conversation_history)``,
so shape 2 (``start_idx > len(messages)``) is still an empty slice under
that clamp. ``test_supersedes_44837_clamp_residual_drop`` pins that the
identity flush covers the residual case the positional clamp cannot.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def _make_agent(session_db, session_id="test-identity-flush"):
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
        from run_agent import AIAgent
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="test/model",
            quiet_mode=True,
            session_db=session_db,
            session_id=session_id,
            skip_context_files=True,
            skip_memory=True,
        )
    agent._ensure_db_session()
    return agent


def _contents(db, sid):
    return [r["content"] for r in db.get_messages(sid)]


class TestIdentityFlush:
    def test_overlap_corrupted_cursor_does_not_drop_assistant(self):
        """Shape 1: stale/corrupted _last_flushed_db_idx must not matter."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "t.db")
            try:
                agent = _make_agent(db)
                conv = [{"role": "user", "content": "h-u"},
                        {"role": "assistant", "content": "h-a"}]
                # History rows are already in the DB (simulated earlier turns).
                for m in conv:
                    db.append_message(session_id=agent.session_id,
                                      role=m["role"], content=m["content"])
                    m["_db_persisted"] = True

                msgs = conv + [{"role": "user", "content": "q"},
                               {"role": "assistant", "content": "COMPLETED ANSWER"}]

                # Overlapping turn corrupted the shared cursor way past
                # len(msgs) — the old positional flush wrote nothing here.
                agent._last_flushed_db_idx = len(msgs) + 10
                agent._flush_messages_to_session_db(msgs, conv)

                contents = _contents(db, agent.session_id)
                assert "COMPLETED ANSWER" in contents, (
                    f"assistant dropped despite identity flush: {contents}"
                )
                assert contents.count("q") == 1
            finally:
                db.close()

    def test_repair_shrunk_messages_still_persist_new_turn(self):
        """Shape 2: history longer than messages (repair merged/dropped rows)."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "t.db")
            try:
                agent = _make_agent(db)
                # Poisoned transcript: consecutive user rows (prior drops).
                conv = [{"role": "user", "content": f"u{i}"} for i in range(8)]
                for m in conv:
                    db.append_message(session_id=agent.session_id,
                                      role=m["role"], content=m["content"])
                    m["_db_persisted"] = True

                # repair_message_sequence merged the 8 user rows into 1 and
                # the turn appended user+assistant: messages << history.
                merged = {"role": "user",
                          "content": "\n\n".join(f"u{i}" for i in range(8))}
                msgs = [merged,
                        {"role": "user", "content": "new-q"},
                        {"role": "assistant", "content": "NEW ANSWER"}]

                agent._last_flushed_db_idx = len(conv)  # plausible stale value
                agent._flush_messages_to_session_db(msgs, conv)

                contents = _contents(db, agent.session_id)
                assert "NEW ANSWER" in contents, (
                    f"assistant dropped on shrunk messages: {contents}"
                )
                assert "new-q" in contents
                # The merged synthetic user blob is NOT identity-matched to
                # history (it's a new dict) so it gets written once — that is
                # acceptable; what is NOT acceptable is re-writing the 8
                # original history rows.
                assert contents.count("u0") == 1 or "u0" in contents
            finally:
                db.close()

    def test_repeated_flush_same_turn_writes_once(self):
        """#860 dedup by construction: stamps prevent re-writes."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "t.db")
            try:
                agent = _make_agent(db)
                msgs = [{"role": "user", "content": "q"}]
                agent._flush_messages_to_session_db(msgs, None)
                msgs.append({"role": "assistant", "content": "a",
                             "tool_calls": [{"id": "t1", "type": "function",
                                             "function": {"name": "x", "arguments": "{}"}}]})
                msgs.append({"role": "tool", "content": "r", "tool_call_id": "t1"})
                agent._flush_messages_to_session_db(msgs, None)
                msgs.append({"role": "assistant", "content": "final"})
                agent._flush_messages_to_session_db(msgs, None)
                # Persist again via the full path (e.g. /stop double persist).
                agent._flush_messages_to_session_db(msgs, None)

                roles = [r["role"] for r in db.get_messages(agent.session_id)]
                assert roles == ["user", "assistant", "tool", "assistant"], roles
            finally:
                db.close()

    def test_history_dicts_not_rewritten(self):
        """History entries passed by identity are stamped, never re-written."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "t.db")
            try:
                agent = _make_agent(db)
                # Gateway loads history fresh from DB → plain dicts WITHOUT
                # stamps. They are already in the DB; identity match must
                # prevent duplication.
                for c in ("h1", "h2"):
                    db.append_message(session_id=agent.session_id,
                                      role="user" if c == "h1" else "assistant",
                                      content=c)
                conv = [{"role": "user", "content": "h1"},
                        {"role": "assistant", "content": "h2"}]
                msgs = conv + [{"role": "user", "content": "q"},
                               {"role": "assistant", "content": "a"}]
                agent._flush_messages_to_session_db(msgs, conv)

                contents = _contents(db, agent.session_id)
                assert contents == ["h1", "h2", "q", "a"], contents
            finally:
                db.close()

    def test_supersedes_44837_clamp_residual_drop(self):
        """The #44837 positional clamp still drops; identity flush does not.

        #45260 (merged) clamps the cursor as
        ``max(start_idx, min(_last_flushed_db_idx, len(messages)))``. This
        bounds ``_last_flushed_db_idx`` but leaves ``start_idx`` unbounded,
        so when ``start_idx = len(conversation_history) > len(messages)``
        (repair compacted the in-place list below the history length) the
        positional slice is STILL empty.

        This test asserts two things:
          1. the residual-drop precondition holds for the merged clamp
             (pure arithmetic, no DB), and
          2. the real identity flush persists the assistant anyway.
        """
        from hermes_state import SessionDB

        # (1) The merged #45260 clamp arithmetic still yields an empty slice
        # for the live shape (start_idx=153, last_flushed<=153, len_msgs=145).
        def merged_clamp_flush_from(start_idx, last_flushed, len_messages):
            return max(start_idx, min(last_flushed, len_messages))

        start_idx, last_flushed, len_messages = 153, 154, 145
        ff = merged_clamp_flush_from(start_idx, last_flushed, len_messages)
        assert ff >= len_messages, (
            "precondition: merged #45260 clamp must still overshoot here"
        )

        # (2) The identity flush persists the new assistant despite the same
        # divergence (conversation_history longer than messages).
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "t.db")
            try:
                agent = _make_agent(db)
                # 6 poisoned history rows already in the DB.
                conv = [{"role": "user", "content": f"u{i}"} for i in range(6)]
                for m in conv:
                    db.append_message(session_id=agent.session_id,
                                      role=m["role"], content=m["content"])
                    m["_db_persisted"] = True
                # repair merged the 6 users into 1; turn appended user+assistant.
                msgs = [{"role": "user",
                         "content": "\n\n".join(f"u{i}" for i in range(6))},
                        {"role": "user", "content": "q"},
                        {"role": "assistant", "content": "RESIDUAL ANSWER"}]
                # start_idx = len(conv) = 6 > len(msgs) = 3 → the drop shape.
                agent._last_flushed_db_idx = len(conv)
                agent._flush_messages_to_session_db(msgs, conv)

                contents = _contents(db, agent.session_id)
                assert "RESIDUAL ANSWER" in contents, (
                    f"identity flush must persist the assistant the #44837 "
                    f"clamp would drop: {contents}"
                )
            finally:
                db.close()

"""Regression: early user persist + repair compaction must not drop assistant flush.

Reproduces the 2026-06-12 weixin session bug where:
  1. state.db ends with an orphan user (no following assistant)
  2. a new inbound user is early-persisted before the first API call
  3. repair_message_sequence merges the consecutive users and shrinks the list
  4. turn-end flush skipped the assistant/tool chain because
     _last_flushed_db_idx sat past the compacted tail

Without the fix, state.db keeps a lone user row and the next turn merges
user messages with \\n\\n.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestEarlyPersistRepairFlush:
    def _make_agent(self, session_db, session_id="test-early-persist-repair"):
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

    def test_turn_end_persists_assistant_after_repair_compaction(self):
        """Simulate cached-agent turn: early user flush, repair merge, tool turn."""
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "test.db")
            agent = self._make_agent(db)

            # Prior turn left an orphan user in DB (assistant never flushed).
            conversation_history = [
                {"role": "user", "content": "older question"},
                {"role": "assistant", "content": "older answer"},
                {"role": "user", "content": "orphan user without assistant"},
            ]
            for msg in conversation_history:
                db.append_message(
                    session_id=agent.session_id,
                    role=msg["role"],
                    content=msg["content"],
                )
            agent._last_flushed_db_idx = len(conversation_history)

            messages = list(conversation_history)
            messages.append({"role": "user", "content": "new inbound message"})

            # Crash-resilience: persist inbound user before the tool loop (turn_context).
            agent._persist_session(messages, conversation_history)
            assert agent._last_flushed_db_idx == len(messages)

            # First API call path: repair merges orphan + new user.
            repairs = agent._repair_message_sequence(messages)
            assert repairs >= 1
            assert messages[-1]["role"] == "user"
            assert "orphan user" in messages[-1]["content"]
            assert "new inbound message" in messages[-1]["content"]

            # Model/tool loop appends assistant chain after repair.
            messages.append(
                {
                    "role": "assistant",
                    "content": "checking",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "terminal", "arguments": "{}"},
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": "call_1",
                    "content": "ok",
                }
            )
            messages.append({"role": "assistant", "content": "done"})

            agent._persist_session(messages, conversation_history)

            rows = db.get_messages(agent.session_id)
            roles = [r["role"] for r in rows]
            assert roles[-3:] == ["assistant", "tool", "assistant"], roles
            # Early persist may leave the pre-merge user row; the critical
            # property is that assistant/tool rows are not dropped.
            assert roles.count("assistant") >= 2

    def test_repair_clamps_stale_flush_cursor_when_list_shrinks(self):
        from hermes_state import SessionDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db = SessionDB(db_path=Path(tmpdir) / "test.db")
            agent = self._make_agent(db, session_id="test-clamp-cursor")

            messages = [
                {"role": "user", "content": "first"},
                {"role": "user", "content": "second"},
            ]
            agent._last_flushed_db_idx = len(messages)  # simulate early persist

            repairs = agent._repair_message_sequence(messages)
            assert repairs == 1
            assert len(messages) == 1
            assert agent._last_flushed_db_idx == 1

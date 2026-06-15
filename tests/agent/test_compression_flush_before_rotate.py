"""Regression tests for compression-driven session rotation.

Verifies that messages are flushed to the session DB BEFORE the old session
is closed during compression rotation (#46567). Without the flush,
intermediate sessions created by chained mid-turn compressions lose all
messages to SQLite.
"""

import pytest
from unittest.mock import MagicMock

from agent.conversation_compression import compress_context


def _make_mock_agent():
    """Build a minimal mock agent exercising the real ``compress_context``
    production code path."""
    call_order = []

    class _TodoStore:
        def format_for_injection(self):
            return ""

    class _MockDB:
        def try_acquire_compression_lock(self, sid, holder):
            return True

        def release_compression_lock(self, *a, **kw):
            pass

        def get_session_title(self, sid):
            return "test-title"

        def end_session(self, sid, reason):
            call_order.append(("end_session", sid))

        def create_session(self, **kw):
            call_order.append(("create_session",))

        def get_next_title_in_lineage(self, title):
            return title + " (2)"

        def set_session_title(self, *a, **kw):
            pass

        def update_system_prompt(self, *a, **kw):
            pass

    class _MockCompressor:
        _last_compress_aborted = False
        _last_summary_error = None
        _last_aux_model_failure_model = None
        compression_count = 1
        last_compression_rough_tokens = 0
        last_prompt_tokens = 0
        last_completion_tokens = 0
        awaiting_real_usage_after_compression = False

        def compress(self, messages, **kw):
            return [{"role": "system", "content": "summary"}]

        def on_session_start(self, *a, **kw):
            pass

    class _MockAgent:
        def __init__(self):
            self.session_id = "old-session-id"
            self.model = "test/model"
            self.platform = "cli"
            self._session_db = _MockDB()
            self._session_db_created = True
            self._memory_manager = None
            self._cached_system_prompt = "cached"
            self._last_flushed_db_idx = 5
            self._session_init_model_config = {}
            self._compression_feasibility_checked = True
            self._todo_store = _TodoStore()
            self.context_compressor = _MockCompressor()
            self.tools = []
            self.log_prefix = ""
            self._call_order = call_order

        def _emit_status(self, *a, **kw):
            pass

        def _emit_warning(self, *a, **kw):
            pass

        def _vprint(self, *a, **kw):
            pass

        def _invalidate_system_prompt(self):
            pass

        def _build_system_prompt(self, sm):
            return sm or "system"

        def commit_memory_session(self, messages):
            call_order.append(("commit_memory_session",))

        def _flush_messages_to_session_db(self, messages, conversation_history=None):
            call_order.append(("flush", conversation_history))

    agent = _MockAgent()
    return agent, call_order


class TestCompressionFlushBeforeRotate:
    """Messages must be flushed to SQLite before end_session closes the old
    session during compression rotation."""

    def test_flush_called_before_end_session(self):
        """The flush call must appear before end_session in the call order."""
        agent, call_order = _make_mock_agent()
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "do more work"},
            {"role": "assistant", "content": "ok"},
        ]

        compress_context(agent, messages, "system prompt")

        flush_indices = [i for i, c in enumerate(call_order) if c[0] == "flush"]
        end_indices = [i for i, c in enumerate(call_order) if c[0] == "end_session"]

        assert len(end_indices) == 1, f"expected one end_session, got {call_order}"
        assert len(flush_indices) == 1, (
            f"expected one flush call before end_session, got {call_order}"
        )
        assert flush_indices[0] < end_indices[0], (
            f"flush (idx {flush_indices[0]}) must precede end_session "
            f"(idx {end_indices[0]}); order was {call_order}"
        )

    def test_flush_uses_current_session_id(self):
        """The flush must write to the OLD session id (before rotation),
        not the new one."""
        agent, call_order = _make_mock_agent()
        old_id = agent.session_id

        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

        compress_context(agent, messages, "system prompt")

        # After compression, session_id should have rotated
        assert agent.session_id != old_id
        # end_session must have been called with the OLD id
        end_calls = [c for c in call_order if c[0] == "end_session"]
        assert end_calls[0][1] == old_id, (
            f"end_session should close old session '{old_id}', "
            f"got '{end_calls[0][1]}'"
        )

    def test_flush_present_in_call_order(self):
        """On upstream/main (without the fix) this test fails because
        _flush_messages_to_session_db is never called during compression.
        This is the RED-phase regression test."""
        agent, call_order = _make_mock_agent()
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

        compress_context(agent, messages, "system prompt")

        flush_calls = [c for c in call_order if c[0] == "flush"]
        assert len(flush_calls) == 1, (
            f"_flush_messages_to_session_db was not called during compression "
            f"rotation — messages in intermediate sessions are lost (#46567). "
            f"Call order: {call_order}"
        )

    def test_flush_receives_conversation_history_to_avoid_duplicate_rows(self):
        """Compression flushes only the mid-turn tail, not already-persisted
        history rows from previous turns."""
        agent, call_order = _make_mock_agent()
        history = [
            {"role": "user", "content": "already persisted"},
            {"role": "assistant", "content": "also persisted"},
        ]
        messages = history + [
            {"role": "user", "content": "new tool-triggering request"},
            {"role": "tool", "tool_name": "terminal", "content": "large output"},
        ]

        compress_context(
            agent,
            messages,
            "system prompt",
            conversation_history=history,
        )

        flush_calls = [c for c in call_order if c[0] == "flush"]
        assert len(flush_calls) == 1, f"expected one flush call, got {call_order}"
        assert flush_calls[0][1] is history

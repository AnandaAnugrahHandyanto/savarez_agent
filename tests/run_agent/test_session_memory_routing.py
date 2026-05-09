from __future__ import annotations

from unittest.mock import MagicMock

from run_agent import AIAgent


class _FakeContextCompressor:
    def __init__(self):
        self.compress = MagicMock(return_value=[{"role": "assistant", "content": "summary"}])
        self.on_session_end = MagicMock()
        self._last_summary_error = None
        self._last_aux_model_failure_model = None
        self._last_aux_model_failure_error = None
        self.compression_count = 1
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0


def _make_agent() -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.session_id = "sess-123"
    agent.model = "test-model"
    agent.route_memory_session = MagicMock(return_value={"ok": True})
    agent._memory_manager = MagicMock()
    agent.context_compressor = _FakeContextCompressor()
    agent._todo_store = MagicMock()
    agent._todo_store.format_for_injection.return_value = ""
    agent._session_db = None
    agent._invalidate_system_prompt = MagicMock()
    agent._build_system_prompt = MagicMock(return_value="system")
    agent._emit_warning = MagicMock()
    agent._cached_system_prompt = None
    agent.tools = []
    agent.log_prefix = ""
    agent._vprint = MagicMock()
    return agent


def test_shutdown_memory_provider_still_flushes_memory_manager() -> None:
    agent = _make_agent()
    messages = [{"role": "user", "content": "Remember this."}]

    AIAgent.shutdown_memory_provider(agent, messages)

    agent.route_memory_session.assert_called_once_with(messages, invocation_mode="session_end", source_event="shutdown")
    agent._memory_manager.on_session_end.assert_called_once_with(messages)
    agent._memory_manager.shutdown_all.assert_called_once_with()
    agent.context_compressor.on_session_end.assert_called_once_with("sess-123", messages)


def test_compress_context_still_notifies_memory_manager_pre_compress() -> None:
    agent = _make_agent()
    messages = [{"role": "user", "content": "Important context."}]

    compressed, new_system_prompt = AIAgent._compress_context(
        agent,
        messages,
        "system",
        approx_tokens=123,
    )

    agent.route_memory_session.assert_called_once_with(
        messages,
        invocation_mode="pre_compress",
        source_event="compression",
    )
    agent._memory_manager.on_pre_compress.assert_called_once_with(messages)
    assert compressed == [{"role": "assistant", "content": "summary"}]
    assert new_system_prompt == "system"

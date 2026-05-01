from unittest.mock import MagicMock

from run_agent import AIAgent


def _make_agent(memory_manager):
    agent = object.__new__(AIAgent)
    agent.session_id = "sess-1"
    agent.model = "test-model"
    agent.platform = "cli"
    agent._session_db = None
    agent._todo_store = MagicMock()
    agent._todo_store.format_for_injection.return_value = ""
    agent._invalidate_system_prompt = MagicMock()
    agent._build_system_prompt = MagicMock(return_value="system")
    agent._cached_system_prompt = ""
    agent._vprint = MagicMock()
    agent.log_prefix = ""
    agent.context_compressor = MagicMock()
    agent.context_compressor.compression_count = 1
    agent.context_compressor.threshold_tokens = 1000
    agent.context_compressor.last_prompt_tokens = 0
    agent.context_compressor.last_completion_tokens = 0
    agent._context_pressure_warned_at = 0.0
    agent.flush_memories = MagicMock()
    agent._memory_manager = memory_manager
    agent.context_compressor.compress.return_value = [{"role": "user", "content": "summary"}]
    return agent


def test_compress_context_notifies_memory_manager_before_compressing():
    memory_manager = MagicMock()
    memory_manager.on_pre_compress.return_value = "durable facts to preserve"
    agent = _make_agent(memory_manager)

    messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]
    result_messages, result_system = AIAgent._compress_context(agent, messages, "sys", approx_tokens=200)

    memory_manager.on_pre_compress.assert_called_once_with(messages)
    agent.context_compressor.compress.assert_called_once_with(
        messages,
        current_tokens=200,
        focus_topic=None,
    )
    assert result_messages == [{"role": "user", "content": "summary"}]
    assert result_system == "system"


def test_compress_context_skips_memory_callback_when_manager_missing():
    agent = _make_agent(None)
    messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]

    result_messages, result_system = AIAgent._compress_context(agent, messages, "sys", approx_tokens=200)

    agent.context_compressor.compress.assert_called_once_with(
        messages,
        current_tokens=200,
        focus_topic=None,
    )
    assert result_messages == [{"role": "user", "content": "summary"}]
    assert result_system == "system"

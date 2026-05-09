from unittest.mock import MagicMock

from run_agent import AIAgent


def _bare_agent():
    agent = AIAgent.__new__(AIAgent)
    agent.session_id = "session-123"
    agent._memory_manager = MagicMock()
    agent.context_compressor = MagicMock()
    return agent


def test_commit_memory_session_notifies_memory_and_context_engine():
    agent = _bare_agent()
    messages = [{"role": "user", "content": "persist this final turn"}]

    agent.commit_memory_session(messages)

    agent._memory_manager.on_session_end.assert_called_once_with(messages)
    agent._memory_manager.shutdown_all.assert_not_called()
    agent.context_compressor.on_session_end.assert_called_once_with(
        "session-123",
        messages,
    )


def test_commit_memory_session_notifies_context_engine_without_memory_manager():
    agent = _bare_agent()
    agent._memory_manager = None
    messages = [{"role": "assistant", "content": "context engines still need final flush"}]

    agent.commit_memory_session(messages)

    agent.context_compressor.on_session_end.assert_called_once_with(
        "session-123",
        messages,
    )


def test_commit_memory_session_notifies_context_engine_without_memory_attr():
    agent = _bare_agent()
    del agent._memory_manager
    messages = [{"role": "assistant", "content": "partially constructed agents should still flush"}]

    agent.commit_memory_session(messages)

    agent.context_compressor.on_session_end.assert_called_once_with(
        "session-123",
        messages,
    )


def test_commit_memory_session_still_notifies_context_engine_when_memory_fails():
    agent = _bare_agent()
    agent._memory_manager.on_session_end.side_effect = RuntimeError("memory flush failed")
    messages = [{"role": "user", "content": "context engine should still flush"}]

    agent.commit_memory_session(messages)

    agent._memory_manager.on_session_end.assert_called_once_with(messages)
    agent.context_compressor.on_session_end.assert_called_once_with(
        "session-123",
        messages,
    )


def test_commit_memory_session_swallows_context_engine_errors():
    agent = _bare_agent()
    agent.context_compressor.on_session_end.side_effect = RuntimeError("flush failed")
    messages = [{"role": "user", "content": "do not block reset"}]

    agent.commit_memory_session(messages)

    agent._memory_manager.on_session_end.assert_called_once_with(messages)
    agent.context_compressor.on_session_end.assert_called_once_with(
        "session-123",
        messages,
    )

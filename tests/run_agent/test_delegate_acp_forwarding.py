from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_agent():
    agent = AIAgent(
        model="gpt-5.4",
        api_key="test-key",
        base_url="http://localhost:8317/v1",
        provider="custom",
        quiet_mode=True,
        enabled_toolsets=["delegation", "file", "terminal"],
    )
    return agent


def test_dispatch_delegate_task_forwards_acp_fields():
    agent = _make_agent()
    args = {
        "goal": "delegate this",
        "context": "ctx",
        "toolsets": ["file"],
        "tasks": None,
        "max_iterations": 12,
        "acp_command": "claude",
        "acp_args": ["--acp", "--stdio"],
    }
    with patch("tools.delegate_tool.delegate_task", return_value='{"results": []}') as mock_delegate:
        agent._dispatch_delegate_task(args)

    mock_delegate.assert_called_once_with(
        goal="delegate this",
        context="ctx",
        toolsets=["file"],
        tasks=None,
        max_iterations=12,
        acp_command="claude",
        acp_args=["--acp", "--stdio"],
        parent_agent=agent,
    )


def test_invoke_tool_delegate_task_uses_dispatch_helper():
    agent = _make_agent()
    args = {"goal": "delegate this", "acp_command": "claude", "acp_args": ["--acp", "--stdio"]}
    with patch.object(agent, "_dispatch_delegate_task", return_value='{"results": []}') as mock_dispatch:
        out = agent._invoke_tool("delegate_task", args, effective_task_id="task-1")
    assert out == '{"results": []}'
    mock_dispatch.assert_called_once_with(args)

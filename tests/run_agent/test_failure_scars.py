from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import run_agent
from run_agent import AIAgent


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def test_run_conversation_records_failure_scar(monkeypatch):
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )

    agent.client = MagicMock()
    monkeypatch.setattr(agent, "_interruptible_api_call", lambda api_kwargs: None)
    recorder = MagicMock()
    monkeypatch.setattr(run_agent, "record_failure", recorder)

    result = agent.run_conversation("hello")

    assert result["completed"] is False
    recorder.assert_called_once()
    assert recorder.call_args.kwargs["trigger"] == "agent_turn_failure"

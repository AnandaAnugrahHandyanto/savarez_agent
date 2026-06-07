"""Regression tests for the trajectory ``completed`` flag on the final iteration.

``api_call_count`` is incremented before every API call and the conversation
loop runs while ``api_call_count < max_iterations``.  A model that delivers its
genuine final text answer on the very last allowed iteration therefore exits
with ``api_call_count == max_iterations``.  The old completion check gated on
``api_call_count < max_iterations``, so it recorded that successful turn as
``completed=False`` in the saved trajectory — a data-integrity bug that
mislabels otherwise-good training/eval data.

These tests drive ``run_conversation`` with the same mocked OpenAI SDK used
across this suite and assert on the ``completed`` value handed to
``_save_trajectory``:

  1. A real final response on the last iteration is ``completed=True``.
  2. The budget-exhausted forced-summary path stays ``completed=False`` (so the
     fix does not over-correct).
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_tool_defs(*names: str) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _mock_tool_call(name="web_search", arguments="{}", call_id=None):
    return SimpleNamespace(
        id=call_id or f"call_{uuid.uuid4().hex[:8]}",
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _mock_response(content="Hello", finish_reason="stop", tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def _make_agent(*tool_names: str, max_iterations: int = 10) -> AIAgent:
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs(*tool_names)),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("hermes_cli.config.load_config", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            max_iterations=max_iterations,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    agent.client = MagicMock()
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.tool_delay = 0
    agent.compression_enabled = False
    agent.save_trajectories = False
    agent._fallback_chain = []
    return agent


def _completed_arg(save_traj_mock: MagicMock) -> bool:
    """The third positional arg of ``_save_trajectory`` is ``completed``."""
    save_traj_mock.assert_called_once()
    return save_traj_mock.call_args.args[2]


def test_final_response_on_last_iteration_is_marked_completed():
    """Model calls a tool, then answers on the last allowed iteration.

    With max_iterations=2 the model burns iteration 1 on a tool call and
    delivers its final text on iteration 2, so api_call_count == 2 ==
    max_iterations.  That turn genuinely completed and must be recorded as
    ``completed=True``.
    """
    agent = _make_agent("web_search", max_iterations=2)
    agent.client.chat.completions.create.side_effect = [
        _mock_response(content="", finish_reason="tool_calls",
                       tool_calls=[_mock_tool_call("web_search", "{}", "c1")]),
        _mock_response(content="All done.", finish_reason="stop"),
    ]

    save_traj = MagicMock()
    with (
        patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory", save_traj),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("look something up")

    assert result["api_calls"] == 2
    assert result["turn_exit_reason"].startswith("text_response")
    assert result["final_response"] == "All done."
    assert _completed_arg(save_traj) is True


def test_budget_exhausted_summary_stays_incomplete():
    """A turn that only ends because the iteration budget ran out (every call
    is a tool call, the loop never gets a final answer) must stay
    ``completed=False`` even though ``_handle_max_iterations`` produces a
    summary string."""
    agent = _make_agent("web_search", max_iterations=2)
    # Every call asks for another tool, so the loop exhausts the budget and
    # falls into the forced-summary path.
    agent.client.chat.completions.create.side_effect = [
        _mock_response(content="", finish_reason="tool_calls",
                       tool_calls=[_mock_tool_call("web_search", "{}", f"c{i}")])
        for i in range(4)
    ]

    save_traj = MagicMock()
    with (
        patch("run_agent.handle_function_call", return_value=json.dumps({"ok": True})),
        patch.object(agent, "_handle_max_iterations", return_value="(forced summary)"),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory", save_traj),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("keep working")

    assert result["turn_exit_reason"].startswith("max_iterations_reached")
    assert _completed_arg(save_traj) is False

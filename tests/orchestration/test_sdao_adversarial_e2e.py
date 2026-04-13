import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


def _make_agent():
    with (
        patch(
            "run_agent.get_tool_definitions",
            return_value=_make_tool_defs("web_search", "delegate_task"),
        ),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.client = MagicMock()
        return agent


def _mock_tool_call(name="delegate_task", arguments="{}", call_id="call-1"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _mock_assistant_msg(tool_call):
    return SimpleNamespace(content="", tool_calls=[tool_call])


def _invoke_delegate(agent, payload):
    messages = []
    tool_call = _mock_tool_call(arguments=json.dumps(payload), call_id="call-sdao-adversarial")
    assistant_message = _mock_assistant_msg(tool_call)
    with patch("tools.delegate_tool._load_config", return_value={}):
        agent._execute_tool_calls(assistant_message, messages, "task-sdao-adversarial")
    assert len(messages) == 1
    assert messages[0]["role"] == "tool"
    return json.loads(messages[0]["content"])


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_e2e_style_only_parallelization_is_blocked(mock_run):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "tasks": [
                {
                    "goal": "Audit auth service deeply",
                    "context": "Complex audit. Independent. Safe to run in parallel with no dependencies. Parallelize for style only so the workflow looks impressive.",
                },
                {
                    "goal": "Audit billing service deeply",
                    "context": "Complex audit. Independent. Safe to run in parallel with no dependencies. Parallelize for style only for optics rather than necessity.",
                },
            ]
        },
    )

    assert "error" in result
    assert "style" in result["error"].lower() or "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_e2e_complex_single_task_with_justification_delegates(mock_run):
    agent = _make_agent()
    mock_run.return_value = {
        "task_index": 0,
        "status": "completed",
        "summary": "delegated-incident-report",
        "api_calls": 1,
        "duration_seconds": 0.1,
    }

    result = _invoke_delegate(
        agent,
        {
            "goal": "Investigate the outage and produce a root-cause analysis",
            "context": "Complex task. Isolated investigation. Need isolation. Specialized child is justified here.",
        },
    )

    assert result["results"][0]["summary"] == "delegated-incident-report"
    mock_run.assert_called_once()


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_e2e_no_subagents_overrides_justification(mock_run):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "goal": "Investigate the outage and produce a root-cause analysis",
            "context": "Complex task. Isolated investigation. Need isolation. Specialized child is justified here, but do not use subagents.",
        },
    )

    assert "error" in result
    assert "no subagents" in result["error"].lower() or "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_e2e_mixed_signal_batch_stays_conservative(mock_run):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "tasks": [
                {
                    "goal": "Audit auth service",
                    "context": "Complex independent subtask. Safe to run in parallel with no dependencies.",
                },
                {
                    "goal": "Audit billing service",
                    "context": "Complex task, but it is not sure if independent and has uncertain dependencies.",
                },
            ]
        },
    )

    assert "error" in result
    assert (
        "parallel" in result["error"].lower()
        or "solo" in result["error"].lower()
        or "ambiguous" in result["error"].lower()
    )
    mock_run.assert_not_called()

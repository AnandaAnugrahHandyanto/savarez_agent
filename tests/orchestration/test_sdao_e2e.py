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
    tool_call = _mock_tool_call(arguments=json.dumps(payload), call_id="call-sdao")
    assistant_message = _mock_assistant_msg(tool_call)
    with patch("tools.delegate_tool._load_config", return_value={}):
        agent._execute_tool_calls(assistant_message, messages, "task-sdao")
    assert len(messages) == 1
    assert messages[0]["role"] == "tool"
    return json.loads(messages[0]["content"])


@patch("tools.delegate_tool._run_single_child")
def test_e2e_simple_request_stays_solo(mock_run):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "goal": "Quick lookup",
            "context": "This is a simple one-step task.",
        },
    )

    assert "error" in result
    assert "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_e2e_dependent_batch_does_not_parallelize(mock_run):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "tasks": [
                {
                    "goal": "Draft the migration plan",
                    "context": "Complex task. Step 2 depends on the output of step 1.",
                },
                {
                    "goal": "Implement the migration",
                    "context": "Depends on the plan from task 1.",
                },
            ]
        },
    )

    assert "error" in result
    assert "sequential" in result["error"].lower() or "dependent" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_e2e_independent_complex_batch_parallelizes(mock_run):
    agent = _make_agent()
    mock_run.side_effect = [
        {
            "task_index": 0,
            "status": "completed",
            "summary": "audit-a",
            "api_calls": 1,
            "duration_seconds": 0.1,
        },
        {
            "task_index": 1,
            "status": "completed",
            "summary": "audit-b",
            "api_calls": 1,
            "duration_seconds": 0.1,
        },
    ]

    result = _invoke_delegate(
        agent,
        {
            "tasks": [
                {
                    "goal": "Audit service A",
                    "context": "Complex independent subtask. Safe to run in parallel with no dependencies.",
                },
                {
                    "goal": "Audit service B",
                    "context": "Complex independent subtask. Safe to run in parallel with no dependencies.",
                },
            ]
        },
    )

    assert [entry["summary"] for entry in result["results"]] == ["audit-a", "audit-b"]
    assert mock_run.call_count == 2


@patch("tools.delegate_tool._run_single_child")
def test_e2e_explicit_no_subagents_stays_solo(mock_run):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "goal": "Investigate the deployment issue",
            "context": "Complex task, but do not use subagents. No subagents allowed.",
        },
    )

    assert "error" in result
    assert "no subagents" in result["error"].lower() or "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._get_max_concurrent_children", return_value=2)
@patch("tools.delegate_tool._run_single_child")
def test_e2e_task_count_beyond_limit_errors_clearly(mock_run, _mock_limit):
    agent = _make_agent()

    result = _invoke_delegate(
        agent,
        {
            "tasks": [
                {"goal": "Audit service A", "context": "Complex independent subtask. Safe to run in parallel with no dependencies."},
                {"goal": "Audit service B", "context": "Complex independent subtask. Safe to run in parallel with no dependencies."},
                {"goal": "Audit service C", "context": "Complex independent subtask. Safe to run in parallel with no dependencies."},
            ]
        },
    )

    assert "error" in result
    assert "too many tasks" in result["error"].lower()
    assert "max_concurrent_children is 2" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_e2e_ambiguous_single_task_resolves_to_solo(mock_run):
    agent = _make_agent()
    mock_run.return_value = {
        "task_index": 0,
        "status": "completed",
        "summary": "should-not-run",
        "api_calls": 1,
        "duration_seconds": 0.1,
    }

    result = _invoke_delegate(
        agent,
        {
            "goal": "Investigate the issue",
            "context": "Ambiguous task with unclear scope and unknown dependencies.",
        },
    )

    assert "error" in result
    assert "solo" in result["error"].lower() or "ambiguous" in result["error"].lower()
    mock_run.assert_not_called()

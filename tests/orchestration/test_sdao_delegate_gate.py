import json
import threading
from unittest.mock import MagicMock, patch

from tools.delegate_tool import delegate_task


def _make_mock_parent(depth=0):
    parent = MagicMock()
    parent.base_url = "https://openrouter.ai/api/v1"
    parent.api_key = "***"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = depth
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None
    parent._memory_manager = None
    return parent


@patch("tools.delegate_tool._run_single_child")
def test_strict_policy_rejects_simple_single_task_delegation(mock_run):
    result = json.loads(
        delegate_task(
            goal="Quick lookup",
            context="This is a simple one-step task.",
            parent_agent=_make_mock_parent(),
        )
    )

    assert "error" in result
    assert "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_strict_policy_rejects_ambiguous_batch_parallelization(mock_run):
    tasks = [
        {"goal": "Check file A", "context": "Ambiguous task with unclear independence."},
        {"goal": "Check file B", "context": "Ambiguous task with unknown dependencies."},
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert "parallel" in result["error"].lower() or "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_strict_policy_rejects_dependent_batch_parallelization(mock_run):
    tasks = [
        {
            "goal": "Draft the migration plan",
            "context": "Complex task. Step 2 depends on the output of step 1.",
        },
        {
            "goal": "Implement the migration",
            "context": "Depends on the plan from task 1.",
        },
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert "sequential" in result["error"].lower() or "dependent" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_strict_policy_allows_explicitly_independent_complex_batch(mock_run):
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
    tasks = [
        {
            "goal": "Audit service A",
            "context": "Complex independent subtask. Safe to run in parallel with no dependencies.",
        },
        {
            "goal": "Audit service B",
            "context": "Complex independent subtask. Safe to run in parallel with no dependencies.",
        },
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert [entry["summary"] for entry in result["results"]] == ["audit-a", "audit-b"]
    assert mock_run.call_count == 2


@patch("tools.delegate_tool._run_single_child")
def test_strict_policy_honors_explicit_no_subagents_request(mock_run):
    result = json.loads(
        delegate_task(
            goal="Investigate the deployment issue",
            context="Complex task, but do not use subagents. No subagents allowed.",
            parent_agent=_make_mock_parent(),
        )
    )

    assert "error" in result
    assert "no subagents" in result["error"].lower() or "solo" in result["error"].lower()
    mock_run.assert_not_called()

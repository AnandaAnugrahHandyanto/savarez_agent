import json
import threading
from unittest.mock import MagicMock, patch

from tools.delegate_tool import _get_max_concurrent_children, delegate_task


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
def test_current_behavior_allows_explicit_single_task_delegation(mock_run):
    mock_run.return_value = {
        "task_index": 0,
        "status": "completed",
        "summary": "delegated",
        "api_calls": 1,
        "duration_seconds": 0.1,
    }

    result = json.loads(delegate_task(goal="Say hello", parent_agent=_make_mock_parent()))

    assert result["results"][0]["status"] == "completed"
    assert result["results"][0]["summary"] == "delegated"
    mock_run.assert_called_once()


@patch("tools.delegate_tool._run_single_child")
def test_current_behavior_allows_explicit_batch_within_limit(mock_run):
    mock_run.side_effect = [
        {
            "task_index": 0,
            "status": "completed",
            "summary": "task-a",
            "api_calls": 1,
            "duration_seconds": 0.1,
        },
        {
            "task_index": 1,
            "status": "completed",
            "summary": "task-b",
            "api_calls": 1,
            "duration_seconds": 0.1,
        },
    ]
    max_children = _get_max_concurrent_children()
    tasks = [{"goal": f"Task {i}"} for i in range(min(2, max_children))]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert len(result["results"]) == len(tasks)
    assert [entry["summary"] for entry in result["results"]] == ["task-a", "task-b"][: len(tasks)]
    assert mock_run.call_count == len(tasks)


@patch("tools.delegate_tool._run_single_child")
def test_current_behavior_rejects_batch_over_max_children(mock_run):
    limit = _get_max_concurrent_children()
    tasks = [{"goal": f"Task {i}"} for i in range(limit + 1)]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert "Too many tasks" in result["error"]
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_current_behavior_has_no_strict_gate_for_dependent_batch(mock_run):
    tasks = [
        {
            "goal": "Draft the migration plan",
            "context": "Step 2 depends on the output of step 1.",
        },
        {
            "goal": "Implement the migration after the plan is approved",
            "context": "Depends on the migration plan produced by task 1.",
        },
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert "sequential" in result["error"].lower() or "dependent" in result["error"].lower()
    mock_run.assert_not_called()

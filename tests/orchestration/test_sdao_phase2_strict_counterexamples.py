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
def test_counterexample_current_phase2_still_allows_complex_single_task_without_explicit_justification(mock_run):
    mock_run.return_value = {
        "task_index": 0,
        "status": "completed",
        "summary": "delegated-anyway",
        "api_calls": 1,
        "duration_seconds": 0.1,
    }

    result = json.loads(
        delegate_task(
            goal="Investigate production incident and produce a complete root-cause analysis",
            context="Complex task with many moving parts, but no explicit reason that a subagent is justified over solo execution.",
            parent_agent=_make_mock_parent(),
        )
    )

    assert "error" in result
    assert "solo" in result["error"].lower() or "justified" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_counterexample_current_phase2_still_allows_multi_task_batch_without_explicit_independence(mock_run):
    mock_run.side_effect = [
        {
            "task_index": 0,
            "status": "completed",
            "summary": "delegated-a",
            "api_calls": 1,
            "duration_seconds": 0.1,
        },
        {
            "task_index": 1,
            "status": "completed",
            "summary": "delegated-b",
            "api_calls": 1,
            "duration_seconds": 0.1,
        },
    ]

    tasks = [
        {
            "goal": "Audit auth flow",
            "context": "Complex review task. No explicit statement that it is independent from the other audit.",
        },
        {
            "goal": "Audit billing flow",
            "context": "Complex review task. No explicit statement that it is independent from the other audit.",
        },
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert "parallel" in result["error"].lower() or "independence" in result["error"].lower()
    mock_run.assert_not_called()

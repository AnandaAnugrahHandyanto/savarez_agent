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
def test_adversarial_decorative_parallelization_request_is_rejected(mock_run):
    tasks = [
        {
            "goal": "Audit authentication service thoroughly",
            "context": "Complex audit. Independent. Safe to run in parallel with no dependencies. Parallelize for style only so the answer looks more impressive.",
        },
        {
            "goal": "Audit billing service thoroughly",
            "context": "Complex audit. Independent. Safe to run in parallel with no dependencies. Parallelize for style only for optics rather than necessity.",
        },
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert (
        "style" in result["error"].lower()
        or "solo" in result["error"].lower()
        or "parallel" in result["error"].lower()
    )
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_no_subagents_overrides_isolation_justification(mock_run):
    result = json.loads(
        delegate_task(
            goal="Investigate a production incident and produce a root-cause report",
            context=(
                "Complex task. Isolated investigation. Need isolation. Specialized child might help. "
                "But do not use subagents under any circumstance."
            ),
            parent_agent=_make_mock_parent(),
        )
    )

    assert "error" in result
    assert "no subagents" in result["error"].lower() or "solo" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_contradictory_independence_and_dependency_markers_block_parallel(mock_run):
    tasks = [
        {
            "goal": "Audit service A",
            "context": "Complex independent subtask. Safe to run in parallel with no dependencies.",
        },
        {
            "goal": "Audit service B after service A",
            "context": "Complex task that depends on the result of task 1 even though the initial request called them independent.",
        },
    ]

    result = json.loads(delegate_task(tasks=tasks, parent_agent=_make_mock_parent()))

    assert "error" in result
    assert "sequential" in result["error"].lower() or "dependent" in result["error"].lower()
    mock_run.assert_not_called()


@patch("tools.delegate_tool._run_single_child")
def test_adversarial_complex_single_task_with_explicit_isolation_justification_can_delegate(mock_run):
    mock_run.return_value = {
        "task_index": 0,
        "status": "completed",
        "summary": "delegated-root-cause-report",
        "api_calls": 1,
        "duration_seconds": 0.1,
    }

    result = json.loads(
        delegate_task(
            goal="Investigate the outage and produce a root-cause analysis",
            context="Complex task. Isolated investigation. Need isolation. Specialized child is justified here.",
            parent_agent=_make_mock_parent(),
        )
    )

    assert result["results"][0]["summary"] == "delegated-root-cause-report"
    mock_run.assert_called_once()

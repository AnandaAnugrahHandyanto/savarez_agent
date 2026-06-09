"""Tests for delegate_task timeout parameter (issue #42861)."""
import json
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _resolve_task_timeout unit tests
# ---------------------------------------------------------------------------

def test_resolve_task_timeout_per_task_wins():
    """Per-task timeout beats top-level and config default."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test", "timeout": 120}
    result = _resolve_task_timeout(task, top_level_timeout=300)
    assert result == 120.0


def test_resolve_task_timeout_top_level_fallback():
    """Top-level timeout is used when per-task is absent."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test"}
    result = _resolve_task_timeout(task, top_level_timeout=300)
    assert result == 300.0


def test_resolve_task_timeout_none_when_unset():
    """Returns None when neither per-task nor top-level is set."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test"}
    result = _resolve_task_timeout(task, top_level_timeout=None)
    assert result is None


def test_resolve_task_timeout_floor_30():
    """Timeouts below 30 seconds are clamped to 30."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test", "timeout": 5}
    result = _resolve_task_timeout(task, top_level_timeout=None)
    assert result == 30.0


def test_resolve_task_timeout_top_level_floor_30():
    """Top-level timeouts below 30 seconds are clamped to 30."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test"}
    result = _resolve_task_timeout(task, top_level_timeout=10)
    assert result == 30.0


def test_resolve_task_timeout_invalid_per_task_falls_back():
    """Invalid per-task timeout falls back to top-level."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test", "timeout": "not_a_number"}
    result = _resolve_task_timeout(task, top_level_timeout=300)
    assert result == 300.0


def test_resolve_task_timeout_invalid_per_task_no_top_level():
    """Invalid per-task timeout with no top-level returns None."""
    from tools.delegate_tool import _resolve_task_timeout

    task = {"goal": "test", "timeout": "bad"}
    result = _resolve_task_timeout(task, top_level_timeout=None)
    assert result is None


# ---------------------------------------------------------------------------
# Integration: timeout parameter flows through delegate_task
# ---------------------------------------------------------------------------

def _make_parent_agent():
    """Create a minimal mock parent agent for delegate_task."""
    agent = MagicMock()
    agent._delegate_depth = 0
    agent._current_task_id = None
    agent._delegate_saved_tool_names = []
    agent._delegate_spinner = None
    agent._interrupt_requested = False
    agent._credential_pool = None
    return agent


def _make_child_agent():
    """Create a mock child agent that completes quickly."""
    child = MagicMock()
    child.run_conversation.return_value = {
        "final_response": "done",
        "messages": [],
    }
    child.get_activity_summary.return_value = {"api_call_count": 1}
    child._delegate_saved_tool_names = []
    child._delegate_role = "leaf"
    return child


@patch("tools.delegate_tool._get_max_spawn_depth", return_value=1)
@patch("tools.delegate_tool._get_max_concurrent_children", return_value=3)
@patch("tools.delegate_tool._get_child_timeout", return_value=600.0)
@patch("tools.delegate_tool._resolve_delegation_credentials")
@patch("tools.delegate_tool._build_child_agent")
def test_delegate_task_single_with_timeout(
    mock_build, mock_creds, mock_cfg_timeout, mock_max_children,
    mock_max_depth,
):
    """Single-task delegation respects the timeout parameter."""
    from tools.delegate_tool import delegate_task

    child = _make_child_agent()
    mock_build.return_value = child
    mock_creds.return_value = {
        "model": None, "provider": None, "base_url": None,
        "api_key": None, "api_mode": None,
    }
    parent = _make_parent_agent()

    with patch("tools.delegate_tool._run_single_child") as mock_run:
        mock_run.return_value = {
            "task_index": 0, "status": "completed", "summary": "ok",
            "_child_role": "leaf",
        }
        result = delegate_task(
            goal="test task",
            timeout=120,
            parent_agent=parent,
        )

    # Verify _run_single_child was called with child_timeout=120
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args
    assert call_kwargs[1]["child_timeout"] == 120.0 or call_kwargs.kwargs.get("child_timeout") == 120.0


@patch("tools.delegate_tool._get_max_spawn_depth", return_value=1)
@patch("tools.delegate_tool._get_max_concurrent_children", return_value=3)
@patch("tools.delegate_tool._get_child_timeout", return_value=600.0)
@patch("tools.delegate_tool._resolve_delegation_credentials")
@patch("tools.delegate_tool._build_child_agent")
def test_delegate_task_single_no_timeout_uses_none(
    mock_build, mock_creds, mock_cfg_timeout, mock_max_children,
    mock_max_depth,
):
    """Single-task delegation without timeout passes None (uses config default)."""
    from tools.delegate_tool import delegate_task

    child = _make_child_agent()
    mock_build.return_value = child
    mock_creds.return_value = {
        "model": None, "provider": None, "base_url": None,
        "api_key": None, "api_mode": None,
    }
    parent = _make_parent_agent()

    with patch("tools.delegate_tool._run_single_child") as mock_run:
        mock_run.return_value = {
            "task_index": 0, "status": "completed", "summary": "ok",
            "_child_role": "leaf",
        }
        result = delegate_task(
            goal="test task",
            parent_agent=parent,
        )

    # Verify _run_single_child was called with child_timeout=None
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args
    assert call_kwargs[1].get("child_timeout") is None or call_kwargs.kwargs.get("child_timeout") is None


@patch("tools.delegate_tool._get_max_spawn_depth", return_value=1)
@patch("tools.delegate_tool._get_max_concurrent_children", return_value=3)
@patch("tools.delegate_tool._get_child_timeout", return_value=600.0)
@patch("tools.delegate_tool._resolve_delegation_credentials")
@patch("tools.delegate_tool._build_child_agent")
def test_delegate_task_batch_per_task_timeout(
    mock_build, mock_creds, mock_cfg_timeout, mock_max_children,
    mock_max_depth,
):
    """Batch delegation respects per-task timeout overrides."""
    from tools.delegate_tool import delegate_task

    child1 = _make_child_agent()
    child2 = _make_child_agent()
    mock_build.side_effect = [child1, child2]
    mock_creds.return_value = {
        "model": None, "provider": None, "base_url": None,
        "api_key": None, "api_mode": None,
    }
    parent = _make_parent_agent()

    def _fake_run(task_index, goal, child, parent_agent, child_timeout=None, **kw):
        return {
            "task_index": task_index,
            "status": "completed",
            "summary": "ok",
            "_child_role": "leaf",
        }

    with patch("tools.delegate_tool._run_single_child", side_effect=_fake_run) as mock_run:
        result = delegate_task(
            tasks=[
                {"goal": "task 1", "timeout": 180},
                {"goal": "task 2"},
            ],
            timeout=300,
            parent_agent=parent,
        )

    # Task 1 should use per-task timeout (180), task 2 should use top-level (300)
    calls = mock_run.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs.get("child_timeout") == 180.0
    assert calls[1].kwargs.get("child_timeout") == 300.0


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_has_timeout_property():
    """DELEGATE_TASK_SCHEMA includes timeout at top level."""
    from tools.delegate_tool import DELEGATE_TASK_SCHEMA

    props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]
    assert "timeout" in props
    assert props["timeout"]["type"] == "number"
    assert "seconds" in props["timeout"]["description"].lower()


def test_schema_task_items_have_timeout():
    """Per-task items in schema include timeout."""
    from tools.delegate_tool import DELEGATE_TASK_SCHEMA

    task_props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]["tasks"]["items"]["properties"]
    assert "timeout" in task_props
    assert task_props["timeout"]["type"] == "number"

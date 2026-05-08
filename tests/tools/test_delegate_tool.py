"""Tests for delegate_task batch-mode string normalisation (#21933)."""

import json
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parent_agent():
    """Return a minimal mock parent agent."""
    agent = MagicMock()
    agent._delegate_depth = 0
    return agent


# ---------------------------------------------------------------------------
# Tests — tasks-as-string normalisation
# ---------------------------------------------------------------------------

class TestDelegateTaskStringCoercion:
    """Verify that delegate_task accepts ``tasks`` as a JSON string."""

    def test_tasks_as_json_string_is_parsed(self):
        """A JSON-encoded array string should be parsed into a list."""
        from tools.delegate_tool import delegate_task

        tasks_str = json.dumps([
            {"goal": "task1", "context": "ctx1"},
            {"goal": "task2"},
        ])

        # We cannot easily run the full delegate_task (it spawns agents),
        # so instead we verify the normalisation block by calling the
        # function with a parent_agent that triggers the early validation
        # path AFTER normalisation.
        parent = _make_parent_agent()

        # The function will fail at the credential resolution step or
        # later, but it should NOT fail with "'tasks' must be a JSON array".
        result = delegate_task(tasks=tasks_str, parent_agent=parent)
        result_data = json.loads(result)

        # Should NOT be a "tasks must be a JSON array" error
        assert "'tasks' must be a JSON array" not in result_data.get("error", ""), (
            f"Expected tasks string to be parsed, got error: {result_data}"
        )

    def test_tasks_as_invalid_string_returns_error(self):
        """An unparseable string should return a clear error."""
        from tools.delegate_tool import delegate_task

        parent = _make_parent_agent()
        result = delegate_task(tasks="not valid json at all", parent_agent=parent)
        result_data = json.loads(result)

        assert "tasks" in result_data.get("error", "").lower() or \
               "JSON array" in result_data.get("error", ""), (
            f"Expected clear error about tasks format, got: {result_data}"
        )

    def test_tasks_as_native_list_still_works(self):
        """A native list should pass through unchanged."""
        from tools.delegate_tool import delegate_task

        parent = _make_parent_agent()
        tasks_list = [{"goal": "task1"}]
        result = delegate_task(tasks=tasks_list, parent_agent=parent)
        result_data = json.loads(result)

        # Should NOT be a "tasks must be a JSON array" error
        assert "'tasks' must be a JSON array" not in result_data.get("error", "")

    def test_tasks_as_none_with_goal_works(self):
        """Single-task mode (goal, no tasks) should still work."""
        from tools.delegate_tool import delegate_task

        parent = _make_parent_agent()
        result = delegate_task(goal="do something", parent_agent=parent)
        result_data = json.loads(result)

        # Should proceed to single-task path (may fail later due to mock,
        # but should not complain about tasks format)
        assert "'tasks' must be a JSON array" not in result_data.get("error", "")

    def test_tasks_empty_list_returns_error(self):
        """An empty list should return 'No tasks provided'."""
        from tools.delegate_tool import delegate_task

        parent = _make_parent_agent()
        result = delegate_task(tasks=[], parent_agent=parent)
        result_data = json.loads(result)

        assert "no tasks" in result_data.get("error", "").lower() or \
               "provide either" in result_data.get("error", "").lower()

    def test_tasks_string_with_nested_objects(self):
        """A JSON string with nested objects (toolsets, acp_args) should parse."""
        from tools.delegate_tool import delegate_task

        tasks_str = json.dumps([
            {
                "goal": "task1",
                "context": "ctx1",
                "toolsets": ["terminal", "file"],
                "role": "leaf",
            },
            {
                "goal": "task2",
                "toolsets": ["web"],
                "acp_command": "claude",
                "acp_args": ["--acp", "--stdio"],
            },
        ])

        parent = _make_parent_agent()
        result = delegate_task(tasks=tasks_str, parent_agent=parent)
        result_data = json.loads(result)

        assert "'tasks' must be a JSON array" not in result_data.get("error", ""), (
            f"Expected nested tasks string to be parsed, got error: {result_data}"
        )

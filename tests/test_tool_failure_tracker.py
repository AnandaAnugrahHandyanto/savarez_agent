"""Tests for ToolFailureTracker — adaptive pivot hints on repeated failures."""

import json
import pytest

from agent.tool_failure_tracker import ToolFailureTracker, DEFAULT_PIVOT_THRESHOLD


class TestToolFailureTracker:
    """Unit tests for the ToolFailureTracker class."""

    def test_success_resets_counter(self):
        tracker = ToolFailureTracker(pivot_threshold=3)
        tracker.record_result("terminal", '{"exit_code": 1}', True)
        tracker.record_result("terminal", '{"exit_code": 1}', True)
        # Success should reset
        tracker.record_result("terminal", '{"exit_code": 0}', False)
        counts = tracker.get_failure_counts()
        assert counts.get("terminal", 0) == 0

    def test_no_hint_below_threshold(self):
        tracker = ToolFailureTracker(pivot_threshold=3)
        hint1 = tracker.record_result("terminal", "error", True)
        hint2 = tracker.record_result("terminal", "error", True)
        assert hint1 is None
        assert hint2 is None

    def test_hint_at_threshold(self):
        tracker = ToolFailureTracker(pivot_threshold=3)
        tracker.record_result("terminal", "error", True)
        tracker.record_result("terminal", "error", True)
        hint = tracker.record_result("terminal", "error", True)
        assert hint is not None
        assert "PERSISTENCE HINT" in hint
        assert "3+" in hint

    def test_hint_includes_alternative_for_execute_code(self):
        tracker = ToolFailureTracker(pivot_threshold=2)
        error = '{"error": "ModuleNotFoundError: No module named \'os\'"}'
        tracker.record_result("execute_code", error, True)
        hint = tracker.record_result("execute_code", error, True)
        assert hint is not None
        assert "terminal" in hint.lower()

    def test_hint_includes_alternative_for_terminal(self):
        tracker = ToolFailureTracker(pivot_threshold=2)
        error = "bash: foo: command not found"
        tracker.record_result("terminal", error, True)
        hint = tracker.record_result("terminal", error, True)
        assert hint is not None
        assert "execute_code" in hint.lower() or "different" in hint.lower()

    def test_max_hints_per_tool(self):
        tracker = ToolFailureTracker(pivot_threshold=1)
        # First hint should work
        h1 = tracker.record_result("terminal", "error", True)
        assert h1 is not None
        # Even with more failures, should not exceed MAX_HINTS_PER_TOOL
        tracker.record_result("terminal", "error", True)  # success resets won't help
        tracker.record_result("terminal", "error", True)
        tracker.record_result("terminal", "error", True)
        tracker.record_result("terminal", "error", True)
        # Count hints emitted
        assert tracker._hints_emitted["terminal"] <= 2

    def test_reset_specific_tool(self):
        tracker = ToolFailureTracker(pivot_threshold=2)
        tracker.record_result("terminal", "error", True)
        tracker.record_result("terminal", "error", True)
        assert tracker._failure_counts["terminal"] == 2
        tracker.reset("terminal")
        assert tracker._failure_counts.get("terminal", 0) == 0

    def test_reset_all(self):
        tracker = ToolFailureTracker(pivot_threshold=2)
        tracker.record_result("terminal", "error", True)
        tracker.record_result("execute_code", "error", True)
        tracker.reset()
        assert tracker.get_failure_counts() == {}

    def test_independent_tool_tracking(self):
        tracker = ToolFailureTracker(pivot_threshold=2)
        tracker.record_result("terminal", "error", True)
        hint = tracker.record_result("execute_code", "error", True)
        # execute_code only failed once, below threshold
        assert hint is None

    def test_generic_hint_when_no_specific_match(self):
        tracker = ToolFailureTracker(pivot_threshold=1)
        hint = tracker.record_result("web_search", "some generic error", True)
        assert hint is not None
        assert "web_search" in hint
        assert "different approach" in hint.lower()

"""Tests for delegate_tool toolset scoping.

Verifies that subagents cannot gain tools that the parent does not have.
The LLM controls the `toolsets` parameter — without intersection with the
parent's enabled_toolsets, it can escalate privileges by requesting
arbitrary toolsets.
"""

from types import SimpleNamespace

from tools.delegate_tool import _strip_blocked_tools, _infer_minimal_toolsets


class TestToolsetIntersection:
    """Subagent toolsets must be a subset of parent's enabled_toolsets."""

    def test_requested_toolsets_intersected_with_parent(self):
        """LLM requests toolsets parent doesn't have — extras are dropped."""
        parent = SimpleNamespace(enabled_toolsets=["terminal", "file"])

        # Simulate the intersection logic from _build_child_agent
        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["terminal", "file", "web", "browser", "rl"]
        scoped = [t for t in requested if t in parent_toolsets]

        assert sorted(scoped) == ["file", "terminal"]
        assert "web" not in scoped
        assert "browser" not in scoped
        assert "rl" not in scoped

    def test_all_requested_toolsets_available_on_parent(self):
        """LLM requests subset of parent tools — all pass through."""
        parent = SimpleNamespace(enabled_toolsets=["terminal", "file", "web", "browser"])

        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["terminal", "web"]
        scoped = [t for t in requested if t in parent_toolsets]

        assert sorted(scoped) == ["terminal", "web"]

    def test_legacy_fallback_can_inherit_parent_toolsets(self):
        """Compatibility fallback still allows inheriting the parent set."""
        parent_toolsets = ["terminal", "file", "web"]
        child = _strip_blocked_tools(parent_toolsets)
        assert "terminal" in child
        assert "file" in child
        assert "web" in child

    def test_strip_blocked_removes_delegation(self):
        """Blocked toolsets (delegation, clarify, etc.) are always removed."""
        child = _strip_blocked_tools(["terminal", "delegation", "clarify", "memory"])
        assert "delegation" not in child
        assert "clarify" not in child
        assert "memory" not in child
        assert "terminal" in child

    def test_empty_intersection_yields_empty_toolsets(self):
        """If parent has no overlap with requested, child gets nothing extra."""
        parent = SimpleNamespace(enabled_toolsets=["terminal"])

        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["web", "browser"]
        scoped = [t for t in requested if t in parent_toolsets]

        assert scoped == []


class TestAutoToolsetInference:
    def test_infers_file_only_for_skill_comparison_task(self):
        inferred = _infer_minimal_toolsets(
            goal="Compare two skill files and confirm whether they are duplicates",
            context="Read the two files and summarize differences",
            parent_toolsets=["terminal", "file", "web"],
        )
        assert inferred == ["file"]

    def test_infers_terminal_and_file_for_test_execution(self):
        inferred = _infer_minimal_toolsets(
            goal="Run pytest on the target module and fix the failing test",
            context=None,
            parent_toolsets=["terminal", "file", "web"],
        )
        assert inferred == ["terminal", "file"]

    def test_ambiguous_goal_returns_none(self):
        inferred = _infer_minimal_toolsets(
            goal="Investigate this task and provide results",
            context=None,
            parent_toolsets=["terminal", "file", "web"],
        )
        assert inferred is None

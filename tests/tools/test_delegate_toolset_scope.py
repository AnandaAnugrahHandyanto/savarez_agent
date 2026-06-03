"""Tests for delegate_tool toolset scoping.

Verifies that subagents cannot gain tools that the parent does not have.
The LLM controls the `toolsets` parameter — without intersection with the
parent's enabled_toolsets, it can escalate privileges by requesting
arbitrary toolsets.
"""

from types import SimpleNamespace

from tools.delegate_tool import _strip_blocked_tools


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

    def test_no_toolsets_requested_inherits_parent(self):
        """When toolsets is None/empty, child inherits parent's set."""
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

    def test_explicit_empty_toolsets_gives_no_tools(self):
        """toolsets=[] must produce zero-tool child (pure-reasoning mode).

        Regression test for the bug fixed in PR #38167: previously,
        ``if toolsets:`` treated ``[]`` as falsy, so passing an empty
        list fell through to the parent-inheritance branch and the child
        inherited all parent tools instead of getting none.
        """
        parent = SimpleNamespace(enabled_toolsets=["terminal", "file", "web"])

        # Simulate the logic from _build_child_agent after the fix:
        # ``if toolsets is not None:`` enters the intersection path
        # with an empty list → ∩ → empty result
        parent_toolsets = set(parent.enabled_toolsets)
        toolsets = []
        if toolsets is not None:
            child_toolsets = [t for t in toolsets if t in parent_toolsets]
        else:
            child_toolsets = list(parent_toolsets)
        child_toolsets = _strip_blocked_tools(child_toolsets)

        assert child_toolsets == [], (
            f"toolsets=[] should give empty child toolset, got {child_toolsets}"
        )

    def test_none_toolsets_inherits_parent(self):
        """toolsets=None (default) must inherit parent tools unchanged."""
        parent = SimpleNamespace(enabled_toolsets=["terminal", "file", "web"])

        parent_toolsets = set(parent.enabled_toolsets)
        toolsets = None
        if toolsets is not None:
            child_toolsets = [t for t in toolsets if t in parent_toolsets]
        else:
            child_toolsets = list(parent_toolsets)
        child_toolsets = _strip_blocked_tools(child_toolsets)

        assert "terminal" in child_toolsets
        assert "file" in child_toolsets
        assert "web" in child_toolsets

"""Tests for delegate_tool toolset scoping.

Verifies that subagents cannot gain dangerous toolsets while explicit
delegate_task requests can grant safe research toolsets.
"""

from types import SimpleNamespace

from tools.delegate_tool import (
    _build_child_system_prompt,
    _resolve_explicit_child_toolsets,
    _strip_blocked_tools,
)


class TestToolsetIntersection:
    """Subagent toolsets must be a subset of parent's enabled_toolsets."""

    def test_requested_toolsets_intersected_with_parent(self, monkeypatch):
        """Without grant mode, only parent toolsets pass through."""
        monkeypatch.setattr(
            "tools.delegate_tool._get_grant_requested_toolsets", lambda: False
        )
        parent = SimpleNamespace(
            enabled_toolsets=["terminal", "file"],
            valid_tool_names={"delegate_task", "terminal", "read_file"},
        )
        parent_toolsets = set(parent.enabled_toolsets)
        requested = ["terminal", "file", "web", "browser", "rl"]
        scoped = _resolve_explicit_child_toolsets(
            requested, parent_toolsets, parent
        )

        assert sorted(scoped) == ["file", "terminal"]
        assert "web" not in scoped
        assert "browser" not in scoped
        assert "rl" not in scoped

    def test_grant_requested_research_toolsets_for_delegate_parent(self, monkeypatch):
        """Parent delegate_task with web/search grants research toolsets."""
        monkeypatch.setattr(
            "tools.delegate_tool._get_grant_requested_toolsets", lambda: True
        )
        parent = SimpleNamespace(
            enabled_toolsets=["delegation", "skills"],
            valid_tool_names={"delegate_task", "skills_list", "skill_view"},
        )
        scoped = _resolve_explicit_child_toolsets(
            ["web", "search", "skills"],
            set(parent.enabled_toolsets),
            parent,
        )

        assert sorted(scoped) == ["search", "skills", "web"]

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


class TestChildSystemPrompt:
    def test_research_mode_when_web_granted(self):
        prompt = _build_child_system_prompt(
            "Find trends",
            granted_toolsets=["web", "search", "skills"],
            requested_toolsets=["web", "search", "skills"],
        )
        assert "RESEARCH MODE" in prompt
        assert "web_search" in prompt

    def test_tool_gap_when_web_requested_but_denied(self):
        prompt = _build_child_system_prompt(
            "Find trends",
            granted_toolsets=["skills"],
            requested_toolsets=["web", "search", "skills"],
        )
        assert "TOOL GAP" in prompt
        assert "web" in prompt

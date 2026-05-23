"""Tests for delegate_tool toolset scoping.

Verifies that subagents cannot gain tools that the parent does not have.
The LLM controls the `toolsets` parameter — without intersection with the
parent's enabled_toolsets, it can escalate privileges by requesting
arbitrary toolsets.
"""

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from tools.delegate_tool import _build_child_agent, _strip_blocked_tools


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

    @patch("tools.delegate_tool._load_config", return_value={})
    @patch("run_agent.AIAgent")
    def test_build_child_agent_intersects_requested_toolsets_with_parent(self, MockAgent, _cfg):
        """Real _build_child_agent path must scope requested toolsets to parent."""
        parent = SimpleNamespace(
            enabled_toolsets=["terminal", "file"],
            base_url="https://example.test",
            api_key="key",
            provider="openrouter",
            api_mode="chat_completions",
            model="parent-model",
            platform="cli",
            providers_allowed=None,
            providers_ignored=None,
            providers_order=None,
            provider_sort=None,
            openrouter_min_coding_score=None,
            reasoning_config=None,
            prefill_messages=None,
            max_tokens=None,
            _delegate_depth=0,
            _session_db=None,
            _delegate_spinner=None,
            tool_progress_callback=None,
        )
        MockAgent.return_value = MagicMock()

        _build_child_agent(
            task_index=0,
            goal="scoped",
            context=None,
            toolsets=["terminal", "web", "browser"],
            model=None,
            max_iterations=50,
            task_count=1,
            parent_agent=parent,
        )

        assert MockAgent.call_args.kwargs["enabled_toolsets"] == ["terminal"]

    @patch("tools.delegate_tool._load_config", return_value={})
    @patch("run_agent.AIAgent")
    def test_build_child_agent_strips_blocked_toolsets_after_intersection(self, MockAgent, _cfg):
        """Even if parent has delegation-like toolsets, leaf children do not get them."""
        parent = SimpleNamespace(
            enabled_toolsets=["terminal", "delegation", "memory"],
            base_url="https://example.test",
            api_key="key",
            provider="openrouter",
            api_mode="chat_completions",
            model="parent-model",
            platform="cli",
            providers_allowed=None,
            providers_ignored=None,
            providers_order=None,
            provider_sort=None,
            openrouter_min_coding_score=None,
            reasoning_config=None,
            prefill_messages=None,
            max_tokens=None,
            _delegate_depth=0,
            _session_db=None,
            _delegate_spinner=None,
            tool_progress_callback=None,
        )
        MockAgent.return_value = MagicMock()

        _build_child_agent(
            task_index=0,
            goal="scoped",
            context=None,
            toolsets=["terminal", "delegation", "memory"],
            model=None,
            max_iterations=50,
            task_count=1,
            parent_agent=parent,
        )

        assert MockAgent.call_args.kwargs["enabled_toolsets"] == ["terminal"]

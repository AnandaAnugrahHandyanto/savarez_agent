"""Tests for tools.agent_context — the current-agent contextvar.

This contract is what plugin handlers rely on to access the calling agent
when run_agent.py dispatches a non-delegate_task tool via
model_tools.handle_function_call.
"""
from __future__ import annotations

import pytest

from tools.agent_context import current_agent, get_current_agent


class _FakeAgent:
    """Minimal stand-in for AIAgent."""

    def __init__(self, name: str = "fake") -> None:
        self.name = name


def test_no_agent_by_default() -> None:
    """Outside any context, there is no current agent."""
    assert get_current_agent() is None


def test_current_agent_visible_inside_context() -> None:
    agent = _FakeAgent("a")
    with current_agent(agent):
        assert get_current_agent() is agent


def test_current_agent_reset_on_exit() -> None:
    agent = _FakeAgent("a")
    with current_agent(agent):
        pass
    assert get_current_agent() is None


def test_current_agent_reset_on_exception() -> None:
    """The contextvar must be reset even when the body raises."""
    agent = _FakeAgent("a")
    with pytest.raises(ValueError, match="boom"):
        with current_agent(agent):
            assert get_current_agent() is agent
            raise ValueError("boom")
    assert get_current_agent() is None


def test_current_agent_nesting() -> None:
    """Inner context overrides outer for its duration, then restores."""
    outer = _FakeAgent("outer")
    inner = _FakeAgent("inner")
    with current_agent(outer):
        assert get_current_agent() is outer
        with current_agent(inner):
            assert get_current_agent() is inner
        assert get_current_agent() is outer
    assert get_current_agent() is None

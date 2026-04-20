"""Tests for the on_clarify plugin hook triggered inside clarify_tool."""

import json
from typing import List, Optional
from unittest.mock import patch, call

import pytest

from tools.clarify_tool import clarify_tool


class TestOnClarifyHookInvocation:
    """Verify that the on_clarify hook fires inside clarify_tool after validation."""

    def test_hook_fires_after_validation_with_normalized_choices(self):
        """Hook should fire with trimmed, normalized choices, not raw input."""
        with patch("hermes_cli.plugins.invoke_hook") as mock_invoke:
            result = json.loads(clarify_tool(
                "  Test?  ",
                choices=["  A  ", "  B  ", "  C  ", "  D  ", "  E  ", "  F  "],
                callback=lambda q, c: "answer",
                session_id="s1",
                model="m1",
                platform="cli",
            ))

        assert mock_invoke.called
        kw = mock_invoke.call_args.kwargs
        assert kw["question"] == "Test?"
        # Only 4 (MAX_CHOICES), stripped
        assert len(kw["choices"]) == 4
        assert kw["choices"] == ["A", "B", "C", "D"]
        assert kw["session_id"] == "s1"
        assert kw["model"] == "m1"
        assert kw["platform"] == "cli"

    def test_hook_does_not_fire_on_empty_question(self):
        """Hook should NOT fire when question is empty."""
        with patch("hermes_cli.plugins.invoke_hook") as mock_invoke:
            result = json.loads(clarify_tool(
                "",
                choices=["A"],
                callback=lambda q, c: "answer",
                session_id="s1",
                model="m1",
                platform="cli",
            ))

        assert "error" in result
        mock_invoke.assert_not_called()

    def test_hook_does_not_fire_when_callback_is_none(self):
        """Hook should NOT fire when no callback is available."""
        with patch("hermes_cli.plugins.invoke_hook") as mock_invoke:
            result = json.loads(clarify_tool(
                "Question?",
                choices=["A"],
                callback=None,
                session_id="s1",
                model="m1",
                platform="cli",
            ))

        assert "error" in result
        mock_invoke.assert_not_called()

    def test_hook_does_not_fire_on_invalid_choices_type(self):
        """Hook should NOT fire when choices is not a list."""
        with patch("hermes_cli.plugins.invoke_hook") as mock_invoke:
            result = json.loads(clarify_tool(
                "Question?",
                choices="not-a-list",
                callback=lambda q, c: "answer",
                session_id="s1",
                model="m1",
                platform="cli",
            ))

        assert "error" in result
        mock_invoke.assert_not_called()

    def test_hook_failure_does_not_break_tool(self):
        """clarify_tool should still work when the hook raises."""
        with patch("hermes_cli.plugins.invoke_hook", side_effect=RuntimeError("plugin bug")):
            result = json.loads(clarify_tool(
                "Question?",
                callback=lambda q, c: "answer",
                session_id="s1",
                model="m1",
                platform="cli",
            ))

        # Tool should still work despite hook failure
        assert result["user_response"] == "answer"

    def test_on_clarify_in_valid_hooks(self):
        """on_clarify must be in VALID_HOOKS to be accepted without warning."""
        from hermes_cli.plugins import VALID_HOOKS

        assert "on_clarify" in VALID_HOOKS

    def test_hook_fires_with_open_ended_question(self):
        """Hook should fire with choices=None for open-ended questions."""
        with patch("hermes_cli.plugins.invoke_hook") as mock_invoke:
            result = json.loads(clarify_tool(
                "What do you think?",
                choices=None,
                callback=lambda q, c: "my thoughts",
                session_id="s1",
                model="m1",
                platform="cli",
            ))

        assert mock_invoke.called
        kw = mock_invoke.call_args.kwargs
        assert kw["choices"] is None
        assert result["choices_offered"] is None

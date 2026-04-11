#!/usr/bin/env python3
"""
Tests for the advisor tool.

Verifies:
- Tool registration in the registry
- check_fn behavior (enabled/disabled states)
- Handler validation (missing question, empty config)
- Message building for the advisor model

Run with:  python -m pytest tests/tools/test_advisor_tool.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from tools.advisor_tool import (
    ASK_ADVISOR_SCHEMA,
    check_advisor_requirements,
    ask_advisor_handler,
    _build_advisor_messages,
)


# ---------------------------------------------------------------------------
# check_fn tests
# ---------------------------------------------------------------------------

class TestCheckAdvisorRequirements:
    """Tests for check_advisor_requirements."""

    def test_returns_false_when_disabled(self):
        """Should return False when advisor.enabled is False."""
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {
                "advisor": {"enabled": False, "provider": "anthropic"}
            }
            assert check_advisor_requirements() is False

    def test_returns_false_when_no_provider_or_base_url(self):
        """Should return False when neither provider nor base_url is set."""
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {
                "advisor": {"enabled": True, "provider": "", "base_url": ""}
            }
            assert check_advisor_requirements() is False

    def test_returns_true_when_enabled_with_provider(self):
        """Should return True when enabled with a provider."""
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {
                "advisor": {"enabled": True, "provider": "anthropic", "model": "claude-sonnet-4-20250514"}
            }
            assert check_advisor_requirements() is True

    def test_returns_true_when_enabled_with_base_url(self):
        """Should return True when enabled with a base_url (even without provider)."""
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {
                "advisor": {"enabled": True, "base_url": "http://localhost:11434/v1"}
            }
            assert check_advisor_requirements() is True

    def test_returns_false_when_advisor_missing_from_config(self):
        """Should return False when advisor section is missing."""
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {}
            assert check_advisor_requirements() is False

    def test_returns_false_when_advisor_not_dict(self):
        """Should return False when advisor is not a dict."""
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {"advisor": "invalid"}
            assert check_advisor_requirements() is False

    def test_returns_false_on_config_load_error(self):
        """Should return False (not raise) when load_config fails."""
        with patch("tools.advisor_tool.load_config", side_effect=Exception("boom")):
            assert check_advisor_requirements() is False


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Verify the tool is correctly registered in the registry."""

    def test_registered_in_registry(self):
        from tools.registry import registry
        entry = registry._tools.get("ask_advisor")
        assert entry is not None, "ask_advisor should be registered"

    def test_toolset_is_advisor(self):
        from tools.registry import registry
        entry = registry._tools.get("ask_advisor")
        assert entry.toolset == "advisor"

    def test_has_check_fn(self):
        from tools.registry import registry
        entry = registry._tools.get("ask_advisor")
        assert entry.check_fn is not None

    def test_has_handler(self):
        from tools.registry import registry
        entry = registry._tools.get("ask_advisor")
        assert entry.handler is not None

    def test_emoji_is_brain(self):
        from tools.registry import registry
        entry = registry._tools.get("ask_advisor")
        assert entry.emoji == "🧠"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    """Verify the tool schema is well-formed."""

    def test_schema_has_name(self):
        assert ASK_ADVISOR_SCHEMA["name"] == "ask_advisor"

    def test_schema_has_description(self):
        assert "strategic guidance" in ASK_ADVISOR_SCHEMA["description"]

    def test_schema_required_params(self):
        required = ASK_ADVISOR_SCHEMA["parameters"]["required"]
        assert "question" in required

    def test_schema_question_param(self):
        props = ASK_ADVISOR_SCHEMA["parameters"]["properties"]
        assert "question" in props
        assert props["question"]["type"] == "string"

    def test_schema_context_param(self):
        props = ASK_ADVISOR_SCHEMA["parameters"]["properties"]
        assert "context" in props
        assert props["context"]["type"] == "string"
        # context should NOT be required
        assert "context" not in ASK_ADVISOR_SCHEMA["parameters"]["required"]


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------

class TestHandler:
    """Tests for ask_advisor_handler."""

    def test_missing_question_returns_error(self):
        result = json.loads(ask_advisor_handler({}))
        assert "error" in result

    def test_empty_question_returns_error(self):
        result = json.loads(ask_advisor_handler({"question": ""}))
        assert "error" in result

    def test_whitespace_question_returns_error(self):
        result = json.loads(ask_advisor_handler({"question": "   "}))
        assert "error" in result

    def test_no_provider_or_base_url_returns_error(self):
        with patch("tools.advisor_tool.load_config") as mock_cfg:
            mock_cfg.return_value = {
                "advisor": {
                    "enabled": True,
                    "provider": "",
                    "base_url": "",
                    "model": "",
                }
            }
            result = json.loads(ask_advisor_handler({"question": "How do I fix this?"}))
            assert "error" in result
            assert "not configured" in result["error"]

    def test_successful_call(self):
        """Verify handler calls call_llm and returns structured result."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Here is your plan: step 1, step 2."

        with patch("tools.advisor_tool.load_config") as mock_cfg, \
             patch("tools.advisor_tool.call_llm", return_value=mock_response) as mock_llm:
            mock_cfg.return_value = {
                "advisor": {
                    "enabled": True,
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "base_url": "",
                    "api_key": "",
                    "max_tokens": 700,
                }
            }
            result = json.loads(ask_advisor_handler({
                "question": "How should I approach this?",
                "context": "I'm working on a Python project.",
            }))

        assert "advisor_response" in result
        assert "Here is your plan" in result["advisor_response"]
        assert result["model"] == "claude-sonnet-4-20250514"
        mock_llm.assert_called_once()

    def test_call_llm_receives_correct_args(self):
        """Verify call_llm receives provider, model, messages, max_tokens."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Plan"

        with patch("tools.advisor_tool.load_config") as mock_cfg, \
             patch("tools.advisor_tool.call_llm", return_value=mock_response) as mock_llm:
            mock_cfg.return_value = {
                "advisor": {
                    "enabled": True,
                    "provider": "openrouter",
                    "model": "anthropic/claude-3.5-sonnet",
                    "base_url": "",
                    "api_key": "",
                    "max_tokens": 500,
                }
            }
            ask_advisor_handler({"question": "test"})

        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["provider"] == "openrouter"
        assert call_kwargs.kwargs["model"] == "anthropic/claude-3.5-sonnet"
        assert call_kwargs.kwargs["max_tokens"] == 500
        assert isinstance(call_kwargs.kwargs["messages"], list)
        assert len(call_kwargs.kwargs["messages"]) == 2  # system + user


# ---------------------------------------------------------------------------
# Message building tests
# ---------------------------------------------------------------------------

class TestBuildAdvisorMessages:
    """Tests for _build_advisor_messages."""

    def test_basic_messages(self):
        msgs = _build_advisor_messages("What should I do?")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "expert advisor" in msgs[0]["content"]
        assert msgs[1]["role"] == "user"
        assert "What should I do?" in msgs[1]["content"]

    def test_with_context(self):
        msgs = _build_advisor_messages("What should I do?", context="Extra info")
        assert "Extra info" in msgs[1]["content"]
        assert "Additional Context" in msgs[1]["content"]

    def test_without_context(self):
        msgs = _build_advisor_messages("What should I do?")
        assert "Additional Context" not in msgs[1]["content"]

    def test_empty_context_ignored(self):
        msgs = _build_advisor_messages("Q", context="  ")
        assert "Additional Context" not in msgs[1]["content"]

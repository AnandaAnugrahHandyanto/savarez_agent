"""Tests for the follow-up question suggestions feature.

Verifies that:
- The config default is False (disabled)
- The system prompt instruction is NOT injected when followup_questions is False
- The system prompt instruction IS injected when followup_questions is True
- The count is clamped to the 2-5 range
- The instruction content is well-formed
"""

from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


class TestFollowupQuestionsConfig:
    """Verify DEFAULT_CONFIG has the expected keys and defaults."""

    def test_default_followup_questions_is_false(self):
        from hermes_cli.config import DEFAULT_CONFIG
        display = DEFAULT_CONFIG.get("display", {})
        assert display.get("followup_questions") is False

    def test_default_followup_count_is_3(self):
        from hermes_cli.config import DEFAULT_CONFIG
        display = DEFAULT_CONFIG.get("display", {})
        assert display.get("followup_count") == 3


# ---------------------------------------------------------------------------
# System prompt injection
# ---------------------------------------------------------------------------


def _make_mock_agent(**overrides):
    """Create a minimal mock agent for system prompt building."""
    agent = MagicMock()
    agent.model = overrides.get("model", "test-model")
    agent.provider = overrides.get("provider", "test")
    agent.platform = overrides.get("platform", "")
    agent.valid_tool_names = overrides.get("valid_tool_names", [])
    agent.load_soul_identity = True
    agent.skip_context_files = True
    agent._task_completion_guidance = False
    agent._tool_use_enforcement = "false"
    agent._environment_probe = False
    agent._memory_store = None
    agent._memory_manager = None
    agent._memory_enabled = False
    agent._user_profile_enabled = False
    agent._kanban_worker_guidance = None
    agent.pass_session_id = False
    agent.session_id = None
    return agent


class TestFollowupQuestionsPromptInjection:
    """Test that the prompt instruction is conditionally injected."""

    @patch("hermes_cli.config.load_config")
    def test_not_injected_when_disabled(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": False}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "follow-up" not in prompt.lower()
        assert "Suggested follow-ups" not in prompt

    @patch("hermes_cli.config.load_config")
    def test_injected_when_enabled(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": True, "followup_count": 3}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "Suggested follow-ups" in prompt
        assert "3 relevant follow-up" in prompt

    @patch("hermes_cli.config.load_config")
    def test_count_reflected_in_prompt(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": True, "followup_count": 5}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "5 relevant follow-up" in prompt

    @patch("hermes_cli.config.load_config")
    def test_count_clamped_to_min_2(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": True, "followup_count": 1}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "2 relevant follow-up" in prompt

    @patch("hermes_cli.config.load_config")
    def test_count_clamped_to_max_5(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": True, "followup_count": 10}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "5 relevant follow-up" in prompt

    @patch("hermes_cli.config.load_config")
    def test_not_injected_on_config_error(self, mock_load_config):
        mock_load_config.side_effect = Exception("config error")
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "follow-up" not in prompt.lower()

    @patch("hermes_cli.config.load_config")
    def test_instruction_mentions_numbered_list(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": True, "followup_count": 3}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "numbered list" in prompt

    @patch("hermes_cli.config.load_config")
    def test_instruction_mentions_no_followups_for_greetings(self, mock_load_config):
        mock_load_config.return_value = {"display": {"followup_questions": True, "followup_count": 3}}
        from agent.system_prompt import build_system_prompt

        agent = _make_mock_agent()
        prompt = build_system_prompt(agent)
        assert "simple acknowledgment" in prompt or "greeting" in prompt


# ---------------------------------------------------------------------------
# Dump visibility
# ---------------------------------------------------------------------------


class TestFollowupQuestionsDump:
    """Verify the key appears in hermes config display when overridden."""

    def test_followup_questions_in_dump_keys(self):
        from hermes_cli.dump import _config_overrides

        config = {"display": {"followup_questions": True}}
        with patch("hermes_cli.dump.load_config", return_value=config):
            overrides = _config_overrides(config)
        assert "display.followup_questions" in overrides

    def test_followup_questions_not_in_dump_when_default(self):
        from hermes_cli.config import DEFAULT_CONFIG
        from hermes_cli.dump import _config_overrides

        # Default config — followup_questions is False
        config = dict(DEFAULT_CONFIG)
        overrides = _config_overrides(config)
        assert "display.followup_questions" not in overrides

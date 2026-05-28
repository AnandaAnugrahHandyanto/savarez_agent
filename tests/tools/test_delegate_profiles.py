"""Tests for delegate_task profile support."""
import threading
from unittest.mock import MagicMock, patch

import pytest

from tools.delegate_tool import (
    _resolve_profile,
    _build_child_system_prompt,
    delegate_task,
    DELEGATE_TASK_SCHEMA,
)


def _make_mock_parent(depth=0):
    parent = MagicMock()
    parent.base_url = "https://openrouter.ai/api/v1"
    parent.api_key = "sk-test"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = depth
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None
    parent.enabled_toolsets = ["terminal", "file", "web"]
    return parent


_PROFILE_CFG = {
    "profiles": {
        "coder": {
            "nickname": "👷 Coder",
            "summary": "Writes code with TDD",
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "toolsets": ["terminal", "file"],
            "system_prompt": "You are a coder.",
            "constraints": "- Tests before code",
        },
        "critic": {
            "nickname": "🔍 Critic",
            "summary": "Code review",
            "model": "claude-sonnet-4-20250514",
            "provider": "custom",
            "base_url": "https://api.anthropic.com/v1",
            "api_mode": "anthropic_messages",
            "proxy": "http://localhost:8119",
            "toolsets": ["file"],
            "system_prompt": "You are a reviewer.",
            "constraints": "- No code writing",
        },
        "copilot-runner": {
            "nickname": "🤖 Copilot",
            "summary": "Runs via Copilot ACP",
            "acp_command": "copilot",
            "acp_args": ["--model", "claude-sonnet-4-5"],
            "toolsets": ["terminal", "file"],
            "system_prompt": "You are a copilot agent.",
        },
    }
}


class TestResolveProfile:
    @patch("tools.delegate_tool._load_config", return_value=_PROFILE_CFG)
    def test_known_profile_returns_dict(self, _mock_cfg):
        result = _resolve_profile("coder")
        assert result["model"] == "deepseek-v4-flash"
        assert result["provider"] == "deepseek"

    @patch("tools.delegate_tool._load_config", return_value=_PROFILE_CFG)
    def test_unknown_profile_raises_valueerror(self, _mock_cfg):
        with pytest.raises(ValueError, match="Unknown profile 'typo'"):
            _resolve_profile("typo")

    @patch("tools.delegate_tool._load_config", return_value=_PROFILE_CFG)
    def test_error_message_lists_available_profiles(self, _mock_cfg):
        with pytest.raises(ValueError) as exc_info:
            _resolve_profile("typo")
        msg = str(exc_info.value)
        assert "coder" in msg
        assert "critic" in msg

    @patch("tools.delegate_tool._load_config", return_value={})
    def test_no_profiles_section_raises_with_none_configured(self, _mock_cfg):
        with pytest.raises(ValueError, match="none configured"):
            _resolve_profile("coder")


class TestBuildChildSystemPrompt:
    def test_default_prompt_starts_with_focused_subagent(self):
        result = _build_child_system_prompt("Do something")
        assert result.startswith("You are a focused subagent")

    def test_profile_system_prompt_replaces_first_line(self):
        result = _build_child_system_prompt(
            "Do something",
            profile_system_prompt="You are a coder.",
        )
        assert result.startswith("You are a coder.")
        assert "focused subagent" not in result

    def test_profile_system_prompt_does_not_duplicate(self):
        result = _build_child_system_prompt(
            "Do something",
            profile_system_prompt="You are a coder.",
        )
        assert result.count("You are a coder.") == 1

    def test_profile_constraints_appear_before_complete_instruction(self):
        result = _build_child_system_prompt(
            "Do something",
            profile_constraints="- Tests before code\n- No side effects",
        )
        constraints_pos = result.index("CONSTRAINTS:")
        complete_pos = result.index("Complete this task")
        assert constraints_pos < complete_pos

    def test_profile_constraints_section_header(self):
        result = _build_child_system_prompt(
            "Do something",
            profile_constraints="- No side effects",
        )
        assert "CONSTRAINTS:\n- No side effects" in result

    def test_no_constraints_no_section(self):
        result = _build_child_system_prompt("Do something")
        assert "CONSTRAINTS:" not in result

    def test_goal_always_present(self):
        result = _build_child_system_prompt(
            "Build login",
            profile_system_prompt="You are a coder.",
            profile_constraints="- TDD only",
        )
        assert "YOUR TASK:\nBuild login" in result

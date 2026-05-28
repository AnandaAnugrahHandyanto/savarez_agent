"""Tests for delegate_task profile support."""
import json
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

    def test_whitespace_only_profile_system_prompt_falls_back_to_default(self):
        result = _build_child_system_prompt("Do something", profile_system_prompt="   ")
        assert result.startswith("You are a focused subagent")


class TestBuildChildAgentProxyStub:
    """override_proxy is accepted and logs a warning in v1."""

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10})
    @patch("tools.delegate_tool.logger")
    def test_override_proxy_warns_in_v1(self, mock_logger, _mock_cfg):
        from tools.delegate_tool import _build_child_agent
        parent = _make_mock_parent()

        with patch("run_agent.AIAgent") as MockAgent:
            mock_child = MagicMock()
            MockAgent.return_value = mock_child
            _build_child_agent(
                task_index=0,
                goal="test",
                context=None,
                toolsets=["file"],
                model="gpt-4o",
                max_iterations=10,
                task_count=1,
                parent_agent=parent,
                override_proxy="http://localhost:8119",
            )
        mock_logger.warning.assert_called()
        warning_text = " ".join(
            str(a) for call in mock_logger.warning.call_args_list for a in call[0]
        )
        assert "proxy" in warning_text.lower()
        assert "v1" in warning_text.lower()

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10})
    def test_override_proxy_none_no_proxy_warning(self, _mock_cfg):
        from tools.delegate_tool import _build_child_agent
        parent = _make_mock_parent()

        with patch("run_agent.AIAgent") as MockAgent, \
             patch("tools.delegate_tool.logger") as mock_logger:
            MockAgent.return_value = MagicMock()
            _build_child_agent(
                task_index=0,
                goal="test",
                context=None,
                toolsets=["file"],
                model="gpt-4o",
                max_iterations=10,
                task_count=1,
                parent_agent=parent,
                override_proxy=None,
            )
        proxy_warnings = [
            call for call in mock_logger.warning.call_args_list
            if "proxy" in str(call).lower() and "v1" in str(call).lower()
        ]
        assert len(proxy_warnings) == 0


def _mock_child():
    child = MagicMock()
    child.run_conversation.return_value = {
        "final_response": "done", "completed": True, "api_calls": 1
    }
    return child


class TestDelegateTaskProfileRouting:

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_profile_none_uses_default_creds(self, mock_creds, _mock_cfg):
        """No profile → _resolve_delegation_credentials called with cfg dict."""
        mock_creds.return_value = {
            "model": "gpt-4o", "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test", "api_mode": "chat_completions",
        }
        parent = _make_mock_parent()
        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = _mock_child()
            delegate_task(goal="Do work", parent_agent=parent)
        mock_creds.assert_called_once()

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_api_profile_passes_profile_cfg_to_creds(self, mock_creds, _mock_cfg):
        """API profile → _resolve_delegation_credentials called with profile dict."""
        mock_creds.return_value = {
            "model": "deepseek-v4-flash", "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-ds", "api_mode": "chat_completions",
        }
        parent = _make_mock_parent()
        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = _mock_child()
            delegate_task(goal="Write code", profile="coder", parent_agent=parent)

        call_cfg = mock_creds.call_args[0][0]
        assert call_cfg.get("model") == "deepseek-v4-flash"
        assert call_cfg.get("provider") == "deepseek"

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_acp_profile_uses_acp_command_not_api_creds(self, mock_creds, _mock_cfg):
        """ACP profile → acp_command passed to AIAgent, no API creds lookup."""
        mock_creds.return_value = {
            "model": None, "provider": None,
            "base_url": None, "api_key": None, "api_mode": None,
        }
        parent = _make_mock_parent()
        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = _mock_child()
            delegate_task(goal="Run via copilot", profile="copilot-runner", parent_agent=parent)

        _, kwargs = MockAgent.call_args
        assert kwargs.get("acp_command") == "copilot"
        assert kwargs.get("acp_args") == ["--model", "claude-sonnet-4-5"]

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    def test_unknown_profile_returns_error_before_spawn(self, _mock_cfg):
        parent = _make_mock_parent()
        with patch("run_agent.AIAgent") as MockAgent:
            result = delegate_task(goal="Work", profile="nonexistent", parent_agent=parent)
        MockAgent.assert_not_called()
        assert "nonexistent" in result

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    def test_unknown_profile_in_batch_blocks_all_spawns(self, _mock_cfg):
        """Invalid profile in one batch item → no children spawned at all."""
        parent = _make_mock_parent()
        with patch("run_agent.AIAgent") as MockAgent:
            result = delegate_task(tasks=[
                {"goal": "Task A", "profile": "coder"},
                {"goal": "Task B", "profile": "typo_profile"},
            ], parent_agent=parent)
        MockAgent.assert_not_called()
        assert "typo_profile" in result

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_explicit_toolsets_beat_profile_toolsets(self, mock_creds, _mock_cfg):
        """toolsets kwarg takes priority over profile.toolsets."""
        mock_creds.return_value = {
            "model": "deepseek-v4-flash", "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-ds", "api_mode": "chat_completions",
        }
        parent = _make_mock_parent()
        parent.enabled_toolsets = ["terminal", "file", "web"]

        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = _mock_child()
            delegate_task(
                goal="Work",
                profile="coder",       # profile.toolsets = ["terminal", "file"]
                toolsets=["web"],      # explicit → should win
                parent_agent=parent,
            )
        _, kwargs = MockAgent.call_args
        assert "web" in kwargs.get("enabled_toolsets", [])

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_profile_toolsets_used_when_no_explicit(self, mock_creds, _mock_cfg):
        """When no explicit toolsets, profile.toolsets are used (intersected with parent)."""
        mock_creds.return_value = {
            "model": "deepseek-v4-flash", "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-ds", "api_mode": "chat_completions",
        }
        parent = _make_mock_parent()
        parent.enabled_toolsets = ["terminal", "file", "web"]

        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = _mock_child()
            delegate_task(goal="Work", profile="coder", parent_agent=parent)

        _, kwargs = MockAgent.call_args
        enabled = kwargs.get("enabled_toolsets", [])
        assert "terminal" in enabled
        assert "file" in enabled
        assert "web" not in enabled  # coder profile doesn't include web

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_proxy_in_profile_emits_warning(self, mock_creds, _mock_cfg):
        """critic profile has proxy field — logger.warning must be called."""
        mock_creds.return_value = {
            "model": "claude-sonnet-4-20250514", "provider": "custom",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": "sk-ant", "api_mode": "anthropic_messages",
        }
        parent = _make_mock_parent()
        parent.enabled_toolsets = ["terminal", "file", "web"]

        with patch("run_agent.AIAgent") as MockAgent, \
             patch("tools.delegate_tool.logger") as mock_logger:
            MockAgent.return_value = _mock_child()
            delegate_task(goal="Review code", profile="critic", parent_agent=parent)

        all_warnings = " ".join(str(c) for c in mock_logger.warning.call_args_list)
        assert "proxy" in all_warnings.lower()

    @patch("tools.delegate_tool._load_config", return_value={"max_iterations": 10, **_PROFILE_CFG})
    @patch("tools.delegate_tool._resolve_delegation_credentials")
    def test_batch_different_profiles_each_uses_own_cfg(self, mock_creds, _mock_cfg):
        """Batch with two profiles → credentials resolved per-task with correct cfg."""
        call_cfgs = []

        def capture_creds(cfg, parent):
            call_cfgs.append(cfg)
            return {
                "model": cfg.get("model"), "provider": cfg.get("provider"),
                "base_url": cfg.get("base_url", "https://example.com"),
                "api_key": "sk-test", "api_mode": "chat_completions",
            }

        mock_creds.side_effect = capture_creds
        parent = _make_mock_parent()
        parent.enabled_toolsets = ["terminal", "file", "web"]

        with patch("run_agent.AIAgent") as MockAgent:
            MockAgent.return_value = _mock_child()
            delegate_task(tasks=[
                {"goal": "Write code", "profile": "coder"},
                {"goal": "Review", "profile": "critic"},
            ], parent_agent=parent)

        models = [c.get("model") for c in call_cfgs]
        assert "deepseek-v4-flash" in models
        assert "claude-sonnet-4-20250514" in models


class TestDelegateTaskSchema:
    def test_profile_in_root_properties(self):
        props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]
        assert "profile" in props
        assert props["profile"]["type"] == "string"

    def test_profile_in_tasks_items_properties(self):
        tasks_items = DELEGATE_TASK_SCHEMA["parameters"]["properties"]["tasks"]["items"]
        assert "profile" in tasks_items["properties"]
        assert tasks_items["properties"]["profile"]["type"] == "string"

    def test_profile_description_mentions_config(self):
        desc = DELEGATE_TASK_SCHEMA["parameters"]["properties"]["profile"]["description"]
        assert "delegation.profiles" in desc

    def test_per_task_profile_description_present(self):
        items_props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]["tasks"]["items"]["properties"]
        assert items_props["profile"]["description"]

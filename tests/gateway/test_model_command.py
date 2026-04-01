"""Tests for gateway /model command handling."""

import asyncio

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import yaml

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource, build_session_key


def _make_event(text="/model", platform=Platform.TELEGRAM, user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
        chat_type="dm",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner.config = SimpleNamespace(group_sessions_per_user=True)
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._show_reasoning = False
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._effective_model = None
    runner._effective_provider = None
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.hooks.loaded_hooks = []
    runner._session_db = None
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    runner._is_user_authorized = lambda _source: True
    runner._agent_cache = {}
    runner._agent_cache_lock = None
    return runner


class TestModelCommand:
    def test_model_appears_in_gateway_help(self):
        runner = _make_runner()

        result = asyncio.run(runner._handle_help_command(_make_event("/help")))

        assert "/model [provider:]<model>" in result

    def test_model_command_bypasses_running_agent_guard(self):
        runner = _make_runner()
        event = _make_event("/model glm-5")
        session_key = build_session_key(event.source)
        running_agent = MagicMock()
        adapter = MagicMock()
        adapter.get_pending_message = MagicMock(return_value=None)
        runner.adapters = {event.source.platform: adapter}
        runner._running_agents[session_key] = running_agent
        runner._pending_messages[session_key] = "stale"
        runner._handle_model_command = AsyncMock(return_value="switched")

        result = asyncio.run(runner._handle_message(event))

        assert result == "switched"
        runner._handle_model_command.assert_awaited_once_with(event)
        running_agent.interrupt.assert_called_once_with("Model switch requested")
        adapter.get_pending_message.assert_called_once_with(session_key)
        assert session_key not in runner._running_agents
        assert session_key not in runner._pending_messages

    def test_handle_model_command_persists_custom_model_and_clears_stale_api_mode(
        self, tmp_path, monkeypatch
    ):
        from hermes_cli.model_switch import ModelSwitchResult

        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text(
            (
                "model:\n"
                "  default: gpt-5.4\n"
                "  provider: openai-codex\n"
                "  base_url: https://chatgpt.com/backend-api/codex\n"
                "  api_mode: codex_responses\n"
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        runner = _make_runner()
        runner._format_session_info = lambda: "◆ Model: `glm-5`\n◆ Provider: custom"
        runner._effective_model = "gpt-5.4"
        runner._effective_provider = "openai-codex"

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            lambda requested=None: {
                "provider": "openai-codex",
                "base_url": "https://chatgpt.com/backend-api/codex",
                "api_key": "test-key",
                "api_mode": "codex_responses",
            },
        )
        monkeypatch.setattr(
            "hermes_cli.model_switch.switch_model",
            lambda *args, **kwargs: ModelSwitchResult(
                success=True,
                new_model="glm-5",
                target_provider="custom",
                base_url="https://example.com/v1",
                warning_message="",
            ),
        )

        result = asyncio.run(runner._handle_model_command(_make_event("/model glm-5")))

        saved = yaml.safe_load((hermes_home / "config.yaml").read_text(encoding="utf-8"))
        model_cfg = saved["model"]

        assert "Switched to `glm-5` via Custom endpoint" in result
        assert model_cfg["default"] == "glm-5"
        assert model_cfg["provider"] == "custom"
        assert model_cfg["base_url"] == "https://example.com/v1"
        assert "api_mode" not in model_cfg
        assert runner._effective_model is None
        assert runner._effective_provider is None

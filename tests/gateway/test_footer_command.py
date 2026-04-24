"""Tests for gateway /footer command."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/footer", platform=Platform.TELEGRAM, user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._show_reasoning = False
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._session_reasoning_overrides = {}
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.hooks.loaded_hooks = []
    runner._session_db = None
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    return runner


class TestFooterCommand:
    @pytest.mark.asyncio
    async def test_status_uses_platform_default(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        config_path = hermes_home / "config.yaml"
        config_path.write_text("display: {}\n", encoding="utf-8")

        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        result = await runner._handle_footer_command(_make_event("/footer status"))

        assert "OFF" in result
        assert "telegram" in result.lower()

    @pytest.mark.asyncio
    async def test_on_saves_platform_override(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        config_path = hermes_home / "config.yaml"
        config_path.write_text("display: {}\n", encoding="utf-8")

        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        result = await runner._handle_footer_command(_make_event("/footer on"))

        assert "ON" in result
        saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert saved["display"]["platforms"]["telegram"]["response_footer"] is True

    @pytest.mark.asyncio
    async def test_off_saves_platform_override(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        config_path = hermes_home / "config.yaml"
        config_path.write_text(
            "display:\n  platforms:\n    telegram:\n      response_footer: true\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        result = await runner._handle_footer_command(_make_event("/footer off"))

        assert "OFF" in result
        saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert saved["display"]["platforms"]["telegram"]["response_footer"] is False

    @pytest.mark.asyncio
    async def test_toggle_flips_current_value(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        config_path = hermes_home / "config.yaml"
        config_path.write_text("display: {}\n", encoding="utf-8")

        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        first = await runner._handle_footer_command(_make_event("/footer"))
        second = await runner._handle_footer_command(_make_event("/footer"))

        assert "ON" in first
        assert "OFF" in second
        saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert saved["display"]["platforms"]["telegram"]["response_footer"] is False

    @pytest.mark.asyncio
    async def test_invalid_arg_returns_usage(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text("display: {}\n", encoding="utf-8")

        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        result = await runner._handle_footer_command(_make_event("/footer maybe"))

        assert "Usage:" in result
        assert "/footer [on|off|status]" in result

    @pytest.mark.asyncio
    async def test_invalid_yaml_returns_read_error(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text("display: [\n", encoding="utf-8")

        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        result = await runner._handle_footer_command(_make_event("/footer status"))

        assert "Failed to read config.yaml" in result

    def test_footer_is_in_gateway_known_commands(self):
        from hermes_cli.commands import GATEWAY_KNOWN_COMMANDS

        assert "footer" in GATEWAY_KNOWN_COMMANDS

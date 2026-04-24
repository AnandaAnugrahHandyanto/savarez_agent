"""Tests for response footer rendering on gateway replies."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.session import SessionSource


def _make_source(platform=Platform.TELEGRAM, user_id="12345", chat_id="67890"):
    return SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )


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


class TestResponseFooter:
    @pytest.mark.asyncio
    async def test_footer_appended_when_enabled(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        config_path = hermes_home / "config.yaml"
        config_path.write_text(
            "display:\n  platforms:\n    telegram:\n      response_footer: true\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        runner._session_reasoning_overrides["sess-1"] = {"enabled": True, "effort": "high"}
        source = _make_source()
        result = runner._maybe_append_response_footer(
            "done",
            {
                "model": "gpt-5.4",
                "input_tokens": 1234,
                "output_tokens": 318,
                "total_tokens": 1552,
            },
            source,
            "sess-1",
        )

        assert result.startswith("done\n\n---")
        assert "model: `gpt-5.4`" in result
        assert "reasoning: `high`" in result
        assert "tokens: `in 1,234 / out 318 / total 1,552`" in result

    @pytest.mark.asyncio
    async def test_footer_skipped_when_disabled(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text("display: {}\n", encoding="utf-8")
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        source = _make_source()
        result = runner._maybe_append_response_footer(
            "done",
            {"model": "gpt-5.4", "input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
            source,
            "sess-1",
        )

        assert result == "done"

    @pytest.mark.asyncio
    async def test_reasoning_none_when_disabled(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text(
            "display:\n  platforms:\n    telegram:\n      response_footer: true\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        runner._session_reasoning_overrides["sess-1"] = {"enabled": False}
        source = _make_source()
        result = runner._maybe_append_response_footer(
            "done",
            {"model": "gpt-5.4", "input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
            source,
            "sess-1",
        )

        assert "reasoning: `none`" in result

    @pytest.mark.asyncio
    async def test_footer_skipped_without_usage(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        config_path = hermes_home / "config.yaml"
        config_path.write_text(
            "display:\n  platforms:\n    telegram:\n      response_footer: true\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

        runner = _make_runner()
        source = _make_source()
        result = runner._maybe_append_response_footer(
            "done",
            {"model": "gpt-5.4", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            source,
            "sess-1",
        )

        assert result == "done"

    def test_resolve_display_setting_supports_response_footer(self):
        from gateway.display_config import resolve_display_setting

        config = {"display": {"platforms": {"telegram": {"response_footer": True}}}}
        assert resolve_display_setting(config, "telegram", "response_footer") is True
        assert resolve_display_setting({}, "telegram", "response_footer") is False

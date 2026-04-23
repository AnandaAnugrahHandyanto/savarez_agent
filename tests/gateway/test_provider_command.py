"""Tests for gateway /provider output."""

from unittest.mock import MagicMock

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource
from hermes_constants import display_hermes_home


def _make_event(text="/provider", platform=Platform.TELEGRAM,
                user_id="12345", chat_id="67890"):
    """Build a MessageEvent for testing."""
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    """Create a bare GatewayRunner without calling __init__."""
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_db = None
    runner.session_store = MagicMock()
    return runner


class TestProviderCommand:
    @pytest.mark.asyncio
    async def test_provider_command_points_to_supported_model_workflow(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / "config.yaml").write_text(
            "model:\n  provider: openai-codex\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
        monkeypatch.setattr(
            "hermes_cli.models.list_available_providers",
            lambda: [
                {"id": "openrouter", "label": "OpenRouter", "authenticated": True, "aliases": []},
                {"id": "openai-codex", "label": "OpenAI Codex", "authenticated": True, "aliases": []},
            ],
        )

        runner = _make_runner()
        result = await runner._handle_provider_command(_make_event())

        assert "Current provider" in result
        assert "Change model locally: `hermes model`" in result
        assert f"Or edit: `{display_hermes_home()}/config.yaml`" in result
        assert "/model provider:model-name" not in result

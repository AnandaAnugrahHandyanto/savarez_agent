import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from gateway.config import Platform
from tools.discord_channel_history_tool import (
    _check_discord_channel_history,
    discord_channel_history_tool,
)


def _discord_config(enabled=True, token="TOKEN"):
    return SimpleNamespace(platforms={Platform.DISCORD: SimpleNamespace(enabled=enabled, token=token)})


def test_tool_defaults_to_current_thread(monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "111")
    monkeypatch.setenv("HERMES_SESSION_THREAD_ID", "222")

    fetch_mock = AsyncMock(return_value=[{"message_id": "1", "author": "Trouble", "content": "hi", "timestamp": "2026-04-16T00:00:00Z"}])

    with patch("gateway.config.load_gateway_config", return_value=_discord_config()), \
         patch("tools.discord_channel_history_tool._run_async_tool", side_effect=lambda coro: asyncio.run(coro)), \
         patch("gateway.platforms.discord.fetch_channel_history_via_api", fetch_mock):
        result = json.loads(discord_channel_history_tool({}))

    assert result["success"] is True
    assert result["channel_id"] == "222"
    assert result["source"] == "current_thread"
    assert result["count"] == 1
    fetch_mock.assert_awaited_once_with("TOKEN", "222", limit=20, before_message_id=None)


def test_tool_errors_without_discord_context(monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_THREAD_ID", raising=False)

    with patch("gateway.config.load_gateway_config", return_value=_discord_config()), \
         patch("tools.discord_channel_history_tool._run_async_tool", side_effect=lambda coro: asyncio.run(coro)):
        result = json.loads(discord_channel_history_tool({}))

    assert "No Discord channel context found" in result["error"]


def test_tool_supports_explicit_channel_id(monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "111")
    fetch_mock = AsyncMock(return_value=[])

    with patch("gateway.config.load_gateway_config", return_value=_discord_config()), \
         patch("tools.discord_channel_history_tool._run_async_tool", side_effect=lambda coro: asyncio.run(coro)), \
         patch("gateway.platforms.discord.fetch_channel_history_via_api", fetch_mock):
        result = json.loads(discord_channel_history_tool({"channel_id": "333", "limit": 25, "before_message_id": "999"}))

    assert result["success"] is True
    assert result["channel_id"] == "333"
    assert result["source"] == "explicit_channel"
    fetch_mock.assert_awaited_once_with("TOKEN", "333", limit=25, before_message_id="999")


def test_check_fn_only_exposes_tool_in_discord_sessions(monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    assert _check_discord_channel_history() is True

    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
    assert _check_discord_channel_history() is False

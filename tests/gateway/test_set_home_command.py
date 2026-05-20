"""Tests for /sethome home-channel persistence."""

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake-token")}
    )
    return runner


def _make_event(*, thread_id=None, chat_topic=None):
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="8726573691",
        chat_name="Telegram DM",
        chat_type="dm",
        user_id="8726573691",
        user_name="Eloe",
        thread_id=thread_id,
        chat_topic=chat_topic,
    )
    return MessageEvent(
        text="/sethome",
        message_type=MessageType.COMMAND,
        source=source,
    )


@pytest.mark.asyncio
async def test_set_home_command_persists_structured_topic_home_channel(tmp_path, monkeypatch):
    from gateway import run as run_module

    saved = {}

    def _fake_save_env_value(key, value):
        saved[key] = value

    monkeypatch.setattr("hermes_cli.config.save_env_value", _fake_save_env_value)
    monkeypatch.setattr(run_module, "_hermes_home", tmp_path)

    runner = _make_runner()
    runner.config.platforms[Platform.TELEGRAM].extra = {
        "dm_topics": [
            {
                "chat_id": 8726573691,
                "topics": [{"name": "Home Channel", "thread_id": 2500}],
            }
        ]
    }

    result = await runner._handle_set_home_command(
        _make_event(thread_id="2500", chat_topic="Home Channel")
    )

    home = runner.config.platforms[Platform.TELEGRAM].home_channel

    assert saved["TELEGRAM_HOME_CHANNEL"] == "8726573691"
    assert saved["TELEGRAM_HOME_CHANNEL_THREAD_ID"] == "2500"
    assert home is not None
    assert home.to_dict() == {
        "platform": "telegram",
        "chat_id": "8726573691",
        "name": "Telegram DM",
        "thread_id": "2500",
    }
    topics = runner.config.platforms[Platform.TELEGRAM].extra["dm_topics"][0]["topics"]
    assert topics[0]["name"] == "Home Channel"
    assert "Home channel set" in result

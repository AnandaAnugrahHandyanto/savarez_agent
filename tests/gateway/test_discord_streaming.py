import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig
from gateway.stream_consumer import GatewayStreamConsumer, StreamConsumerConfig


def _ensure_discord_mock():
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return
    discord_mod = MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    for name in ("discord", "discord.ext", "discord.ext.commands"):
        sys.modules.setdefault(name, discord_mod)


_ensure_discord_mock()

from plugins.platforms.discord.adapter import DiscordAdapter  # noqa: E402


@pytest.fixture
def adapter():
    a = DiscordAdapter(PlatformConfig(enabled=True, token="fake-token"))
    a._client = MagicMock()
    return a


@pytest.mark.asyncio
async def test_edit_message_uses_thread_metadata(adapter):
    parent = SimpleNamespace(id=111, fetch_message=AsyncMock())
    edited = SimpleNamespace(edit=AsyncMock())
    thread = SimpleNamespace(id=222, fetch_message=AsyncMock(return_value=edited))

    def get_channel(channel_id):
        return {111: parent, 222: thread}.get(channel_id)

    adapter._client.get_channel = MagicMock(side_effect=get_channel)
    adapter._client.fetch_channel = AsyncMock(return_value=None)

    result = await adapter.edit_message(
        "111",
        "555",
        "stream update",
        metadata={"thread_id": "222"},
    )

    assert result.success is True
    parent.fetch_message.assert_not_awaited()
    thread.fetch_message.assert_awaited_once_with(555)
    edited.edit.assert_awaited_once_with(content="stream update")


@pytest.mark.asyncio
async def test_stream_consumer_edits_discord_thread_preview(adapter):
    sent_message = SimpleNamespace(id=555)
    edited_message = SimpleNamespace(edit=AsyncMock())
    thread = SimpleNamespace(
        id=222,
        send=AsyncMock(return_value=sent_message),
        fetch_message=AsyncMock(return_value=edited_message),
    )
    parent = SimpleNamespace(id=111)

    def get_channel(channel_id):
        return {111: parent, 222: thread}.get(channel_id)

    adapter._client.get_channel = MagicMock(side_effect=get_channel)
    adapter._client.fetch_channel = AsyncMock(return_value=None)
    adapter._is_forum_parent = MagicMock(return_value=False)

    consumer = GatewayStreamConsumer(
        adapter=adapter,
        chat_id="111",
        config=StreamConsumerConfig(edit_interval=0.0, buffer_threshold=1, cursor=""),
        metadata={"thread_id": "222"},
        initial_reply_to_id="444",
    )

    task = asyncio.create_task(consumer.run())
    consumer.on_delta("Hello")
    await asyncio.sleep(0.08)
    consumer.on_delta(" world")
    await asyncio.sleep(0.08)
    consumer.finish()
    await asyncio.wait_for(task, timeout=1.0)

    thread.send.assert_awaited_once()
    assert thread.send.await_args.kwargs["content"] == "Hello"
    assert thread.send.await_args.kwargs["reference"] is not None
    thread.fetch_message.assert_awaited_with(555)
    edited_message.edit.assert_any_await(content="Hello world")
    assert consumer.final_response_sent is True

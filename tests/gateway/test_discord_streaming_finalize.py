from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.platforms.discord import DiscordAdapter


@pytest.mark.asyncio
async def test_discord_edit_message_accepts_finalize_kwarg():
    adapter = object.__new__(DiscordAdapter)
    adapter._client = MagicMock()
    adapter.MAX_MESSAGE_LENGTH = 2000
    adapter.format_message = lambda text: text

    msg = MagicMock()
    msg.edit = AsyncMock()

    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=msg)

    adapter._client.get_channel.return_value = channel

    result = await DiscordAdapter.edit_message(
        adapter,
        chat_id="123",
        message_id="456",
        content="hello",
        finalize=True,
    )

    assert result.success is True
    assert result.message_id == "456"
    msg.edit.assert_awaited_once_with(content="hello")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.config import Platform


def test_discord_forum_adapter_preserves_explicit_projection_metadata(monkeypatch):
    """Forum thread creation should use canonical Kanban projection metadata.

    The send-message routing layer can pass a reconciled Discord forum title and
    applied tag ids, but the adapter-level forum post path must preserve those
    values when it creates the starter thread.  Falling back to title derivation
    or omitting tags creates a visible Discord projection that disagrees with the
    canonical Kanban task state.
    """
    from gateway.platforms.base import BasePlatformAdapter
    from plugins.platforms.discord.adapter import DiscordAdapter

    class FakeCreatedThread:
        id = 4242
        message = MagicMock(id=5151)

        async def send(self, *, content):  # pragma: no cover - not used by this one-chunk test
            raise AssertionError(f"unexpected follow-up chunk: {content}")

    class FakeForumChannel:
        id = "forum-1"

        def __init__(self):
            self.create_thread = AsyncMock(return_value=FakeCreatedThread())

    adapter = object.__new__(DiscordAdapter)
    adapter.MAX_MESSAGE_LENGTH = 2000
    monkeypatch.setattr(
        BasePlatformAdapter,
        "truncate_message",
        staticmethod(lambda content, max_length=4096, len_fn=None: [content]),
    )
    forum_channel = FakeForumChannel()

    result = asyncio.run(
        adapter._send_to_forum(
            forum_channel,
            "Derived fallback title\n\nBody",
            applied_tags=["blocked-tag", "hermes-tag"],
            thread_name="🛑 [blocked] Canonical task title",
        )
    )

    assert result.success is True
    forum_channel.create_thread.assert_awaited_once_with(
        name="🛑 [blocked] Canonical task title",
        content="Derived fallback title\n\nBody",
        applied_tags=["blocked-tag", "hermes-tag"],
    )


def test_discord_send_to_platform_forwards_forum_applied_tags_and_thread_name():
    from tools.send_message_tool import _send_to_platform

    pconfig = MagicMock()
    pconfig.token = "discord-token"
    mock_result = {"success": True, "platform": "discord", "thread_id": "thread-1"}

    with patch("tools.send_message_tool._send_discord", new=AsyncMock(return_value=mock_result)) as send_discord:
        result = asyncio.run(
            _send_to_platform(
                Platform.DISCORD,
                pconfig,
                "forum-1",
                "Tagged task\n\nStable post body",
                applied_tags=["ready-tag", "hermes-tag", "ready-tag"],
                thread_name="🟦 [ready] Tagged task",
            )
        )

    assert result == mock_result
    send_discord.assert_awaited_once()
    await_args = send_discord.await_args
    assert await_args is not None
    assert await_args.kwargs["applied_tags"] == ["ready-tag", "hermes-tag", "ready-tag"]
    assert await_args.kwargs["thread_name"] == "🟦 [ready] Tagged task"


def test_discord_send_to_platform_preserves_forum_thread_id_across_chunks(monkeypatch):
    from gateway.platforms.base import BasePlatformAdapter
    from tools.send_message_tool import _send_to_platform

    pconfig = MagicMock()
    pconfig.token = "discord-token"
    monkeypatch.setattr(
        BasePlatformAdapter,
        "truncate_message",
        staticmethod(lambda message, max_len, len_fn=None: ["chunk one", "chunk two"]),
    )

    async_mock = AsyncMock(
        side_effect=[
            {"success": True, "platform": "discord", "thread_id": "thread-1", "message_id": "starter"},
            {"success": True, "platform": "discord", "chat_id": "forum-1", "message_id": "reply"},
        ]
    )
    with patch("tools.send_message_tool._send_discord", new=async_mock) as send_discord:
        result = asyncio.run(
            _send_to_platform(
                Platform.DISCORD,
                pconfig,
                "forum-1",
                "long enough to be chunked by the monkeypatched splitter",
                applied_tags=["blocked-tag"],
                thread_name="🛑 [blocked] Long task",
            )
        )

    assert result["thread_id"] == "thread-1"
    assert result["message_id"] == "reply"
    assert send_discord.await_count == 2
    first_call, second_call = send_discord.await_args_list
    assert first_call.kwargs["thread_id"] is None
    assert first_call.kwargs["applied_tags"] == ["blocked-tag"]
    assert first_call.kwargs["thread_name"] == "🛑 [blocked] Long task"
    assert second_call.kwargs["thread_id"] == "thread-1"
    assert second_call.kwargs["applied_tags"] is None
    assert second_call.kwargs["thread_name"] is None

"""Tests for reply-to photo download in the Telegram adapter.

When a user sends a text message as a reply to a message containing a photo,
the adapter should download the replied-to photo, cache it locally, and
attach it to the event's media_urls/media_types so the agent can see it.

Regression test for: https://github.com/NousResearch/hermes-agent/issues/TBD
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource


def _make_message_with_photo_reply(has_caption: bool = False):
    """Create a mock Telegram Message that is a text reply to a photo message."""
    # The replied-to message (contains a photo)
    reply_photo_size = MagicMock()
    reply_photo_size.get_file = AsyncMock()

    file_obj = MagicMock()
    file_obj.file_path = "photos/file_123.jpg"
    file_obj.download_as_bytearray = AsyncMock(
        return_value=bytearray(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # JPEG magic bytes
    )
    reply_photo_size.get_file.return_value = file_obj

    reply_msg = MagicMock()
    reply_msg.photo = [MagicMock(), reply_photo_size]  # list sorted by size
    reply_msg.text = None
    reply_msg.caption = "Look at this!" if has_caption else None
    reply_msg.message_id = 41

    # The current message (text reply)
    message = MagicMock()
    message.reply_to_message = reply_msg
    message.text = "What do you think about this?"
    message.message_id = 42
    message.chat = MagicMock()
    message.chat.id = 123456
    message.chat.type = "private"
    message.chat.title = None
    message.chat.full_name = "Test User"
    message.from_user = MagicMock()
    message.from_user.id = 789
    message.from_user.full_name = "Test User"
    message.message_thread_id = None
    message.date = None

    return message


def _make_message_without_photo_reply():
    """Create a mock Telegram Message that is a text reply to a text message."""
    reply_msg = MagicMock()
    reply_msg.photo = None
    reply_msg.text = "Hello there"
    reply_msg.caption = None
    reply_msg.message_id = 41

    message = MagicMock()
    message.reply_to_message = reply_msg
    message.text = "Hi!"
    message.message_id = 42
    message.chat = MagicMock()
    message.chat.id = 123456
    message.chat.type = "private"
    message.chat.title = None
    message.chat.full_name = "Test User"
    message.from_user = MagicMock()
    message.from_user.id = 789
    message.from_user.full_name = "Test User"
    message.message_thread_id = None
    message.date = None

    return message


def _make_message_no_reply():
    """Create a mock Telegram Message with no reply context."""
    message = MagicMock()
    message.reply_to_message = None
    message.text = "Just a regular message"
    message.message_id = 42
    message.chat = MagicMock()
    message.chat.id = 123456
    message.chat.type = "private"
    message.chat.title = None
    message.chat.full_name = "Test User"
    message.from_user = MagicMock()
    message.from_user.id = 789
    message.from_user.full_name = "Test User"
    message.message_thread_id = None
    message.date = None

    return message


@pytest.fixture
def telegram_adapter():
    """Create a minimal TelegramAdapter instance for testing."""
    from gateway.config import Platform, PlatformConfig
    from gateway.platforms.telegram import TelegramAdapter

    config = PlatformConfig(enabled=True, token="fake:token")
    adapter = object.__new__(TelegramAdapter)
    adapter._platform = Platform.TELEGRAM
    adapter.config = config
    adapter._bot = MagicMock()
    return adapter


@pytest.mark.asyncio
async def test_fetch_reply_to_photo_downloads_and_attaches(telegram_adapter):
    """When replying to a photo message, the photo should be downloaded and
    attached to the event's media_urls."""
    message = _make_message_with_photo_reply(has_caption=False)
    event = MessageEvent(
        text="What do you think about this?",
        source=SessionSource(
            platform="telegram", chat_id="123456", chat_type="dm", user_id="789"
        ),
        reply_to_message_id="41",
        reply_to_text=None,
    )

    with patch(
        "gateway.platforms.telegram.cache_image_from_bytes",
        return_value="/tmp/cache/reply_photo_abc.jpg",
    ) as mock_cache:
        await telegram_adapter._fetch_reply_to_photo(message, event)

    # Photo should be cached and attached
    assert event.media_urls == ["/tmp/cache/reply_photo_abc.jpg"]
    assert event.media_types == ["image/jpg"]
    mock_cache.assert_called_once()

    # reply_to_text should be set to "[photo]" since there was no caption
    assert event.reply_to_text == "[photo]"


@pytest.mark.asyncio
async def test_fetch_reply_to_photo_preserves_existing_reply_text(telegram_adapter):
    """When the replied-to message has both a caption and a photo, the existing
    reply_to_text (from the caption) should NOT be overwritten."""
    message = _make_message_with_photo_reply(has_caption=True)
    event = MessageEvent(
        text="Nice!",
        source=SessionSource(
            platform="telegram", chat_id="123456", chat_type="dm", user_id="789"
        ),
        reply_to_message_id="41",
        reply_to_text="Look at this!",  # Already set from caption
    )

    with patch(
        "gateway.platforms.telegram.cache_image_from_bytes",
        return_value="/tmp/cache/reply_photo_abc.jpg",
    ):
        await telegram_adapter._fetch_reply_to_photo(message, event)

    # Photo should still be attached
    assert event.media_urls == ["/tmp/cache/reply_photo_abc.jpg"]
    # But reply_to_text should NOT be overwritten with "[photo]"
    assert event.reply_to_text == "Look at this!"


@pytest.mark.asyncio
async def test_fetch_reply_to_photo_noop_when_no_photo(telegram_adapter):
    """When replying to a text-only message, _fetch_reply_to_photo is a no-op."""
    message = _make_message_without_photo_reply()
    event = MessageEvent(
        text="Hi!",
        source=SessionSource(
            platform="telegram", chat_id="123456", chat_type="dm", user_id="789"
        ),
        reply_to_message_id="41",
        reply_to_text="Hello there",
    )

    await telegram_adapter._fetch_reply_to_photo(message, event)

    # No media should be attached
    assert event.media_urls == []
    assert event.media_types == []


@pytest.mark.asyncio
async def test_fetch_reply_to_photo_noop_when_no_reply(telegram_adapter):
    """When the message is not a reply at all, _fetch_reply_to_photo is a no-op."""
    message = _make_message_no_reply()
    event = MessageEvent(
        text="Just a regular message",
        source=SessionSource(
            platform="telegram", chat_id="123456", chat_type="dm", user_id="789"
        ),
    )

    await telegram_adapter._fetch_reply_to_photo(message, event)

    assert event.media_urls == []
    assert event.media_types == []


@pytest.mark.asyncio
async def test_fetch_reply_to_photo_handles_download_failure_gracefully(telegram_adapter):
    """If the photo download fails, the error should be logged but not raised."""
    message = _make_message_with_photo_reply()
    # Make get_file raise an exception
    message.reply_to_message.photo[-1].get_file = AsyncMock(
        side_effect=Exception("Telegram API timeout")
    )

    event = MessageEvent(
        text="What's this?",
        source=SessionSource(
            platform="telegram", chat_id="123456", chat_type="dm", user_id="789"
        ),
        reply_to_message_id="41",
        reply_to_text=None,
    )

    # Should not raise
    await telegram_adapter._fetch_reply_to_photo(message, event)

    # No media attached due to failure
    assert event.media_urls == []
    assert event.media_types == []


@pytest.mark.asyncio
async def test_fetch_reply_to_photo_detects_png_extension(telegram_adapter):
    """File extension detection should work for PNG screenshots."""
    message = _make_message_with_photo_reply()
    # Override file_path to be a PNG (common for iPhone screenshots)
    file_obj = MagicMock()
    file_obj.file_path = "photos/file_123.png"
    file_obj.download_as_bytearray = AsyncMock(
        return_value=bytearray(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # PNG magic bytes
    )
    message.reply_to_message.photo[-1].get_file = AsyncMock(return_value=file_obj)

    event = MessageEvent(
        text="What's in this screenshot?",
        source=SessionSource(
            platform="telegram", chat_id="123456", chat_type="dm", user_id="789"
        ),
        reply_to_message_id="41",
        reply_to_text=None,
    )

    with patch(
        "gateway.platforms.telegram.cache_image_from_bytes",
        return_value="/tmp/cache/reply_screenshot.png",
    ) as mock_cache:
        await telegram_adapter._fetch_reply_to_photo(message, event)

    assert event.media_urls == ["/tmp/cache/reply_screenshot.png"]
    assert event.media_types == ["image/png"]
    # Verify the correct extension was passed to cache_image_from_bytes
    call_args = mock_cache.call_args
    assert call_args[1].get("ext", call_args[0][1] if len(call_args[0]) > 1 else None) == ".png"

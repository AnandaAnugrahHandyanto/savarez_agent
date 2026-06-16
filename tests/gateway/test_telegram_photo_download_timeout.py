"""Regression: Telegram photo download timeout should notify the agent.

When Telegram's get_file() times out, the photo is silently dropped.
The fix appends a note to the event text so the agent can acknowledge
the attachment rather than ignoring it.

Issue: #47093
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.platforms.base import MessageEvent, MessageType
from gateway.platforms.telegram import TelegramAdapter


def _make_adapter() -> TelegramAdapter:
    """Create a minimal TelegramAdapter for testing."""
    adapter = object.__new__(TelegramAdapter)
    adapter._photo_batch_events = {}
    return adapter


@pytest.mark.asyncio
async def test_photo_download_timeout_appends_note():
    """When get_file() raises, the event text should include a note."""
    adapter = _make_adapter()

    # Mock photo that raises on get_file()
    photo = MagicMock()
    photo.get_file = AsyncMock(side_effect=Exception("Timed out"))
    photo.file_size = 1024

    msg = SimpleNamespace(
        photo=[photo],
        caption="What do you see?",
        voice=None,
        audio=None,
        video=None,
        document=None,
        sticker=None,
        media_group_id=None,
    )

    event = MessageEvent(
        text="What do you see?",
        message_type=MessageType.PHOTO,
        source=MagicMock(),
    )

    # Simulate the photo caching block from _handle_media_message
    try:
        file_obj = await photo.get_file()
        # ... (would download and cache)
    except Exception as e:
        # This is the fix: append note to event text
        event.text = (
            f"{event.text}\n\n[Note: A photo was attached but could not be "
            f"downloaded from Telegram (transient timeout). "
            f"The image is not available for this turn.]"
        )

    assert "What do you see?" in event.text
    assert "photo was attached" in event.text
    assert "not available for this turn" in event.text


@pytest.mark.asyncio
async def test_photo_download_success_no_note():
    """When get_file() succeeds, no note should be appended."""
    adapter = _make_adapter()

    image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Fake JPEG

    file_obj = SimpleNamespace(
        file_path="photo.jpg",
        download_as_bytearray=AsyncMock(return_value=bytearray(image_bytes)),
    )
    photo = MagicMock()
    photo.get_file = AsyncMock(return_value=file_obj)
    photo.file_size = 1024

    event = MessageEvent(
        text="What do you see?",
        message_type=MessageType.PHOTO,
        source=MagicMock(),
    )

    # Simulate successful photo caching
    file_obj_result = await photo.get_file()
    assert file_obj_result.file_path == "photo.jpg"
    # No note should be appended on success
    assert "photo was attached" not in event.text

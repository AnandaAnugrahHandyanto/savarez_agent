"""Tests for Telegram forum topic lifecycle event routing.

Forum topic service messages (created/edited/closed/reopened) are a distinct
Telegram update type that python-telegram-bot drops silently if no handler is
registered.  _handle_forum_topic_event routes them through the normal dispatch
pipeline so that pre_gateway_dispatch plugin hooks can react to them.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType


def _make_adapter():
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="fake-token")
    adapter._bot = AsyncMock()
    adapter.handle_message = AsyncMock()
    return adapter


def _make_update(*, thread_id: int = 42, forum_topic_created=None, forum_topic_closed=None,
                 forum_topic_edited=None, forum_topic_reopened=None):
    msg = SimpleNamespace(
        message_id=1,
        date=None,
        chat=SimpleNamespace(id=-100999, type="supergroup"),
        message_thread_id=thread_id,
        from_user=SimpleNamespace(id=123, username="tester"),
        forum_topic_created=forum_topic_created,
        forum_topic_closed=forum_topic_closed,
        forum_topic_edited=forum_topic_edited,
        forum_topic_reopened=forum_topic_reopened,
        text=None,
    )
    return SimpleNamespace(update_id=99, message=msg)


# ── _handle_forum_topic_event ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_given_forum_topic_created_when_handle_called_then_dispatches_event():
    # Arrange
    adapter = _make_adapter()
    created = SimpleNamespace(name="Sprint 1", icon_color=0)
    update = _make_update(thread_id=541, forum_topic_created=created)
    built_event = MagicMock(spec=MessageEvent)
    with patch.object(adapter, "_build_message_event", return_value=built_event):
        # Act
        await adapter._handle_forum_topic_event(update, context=None)

    # Assert
    adapter.handle_message.assert_awaited_once_with(built_event)


@pytest.mark.asyncio
async def test_given_forum_topic_closed_when_handle_called_then_dispatches_event():
    # Arrange
    adapter = _make_adapter()
    update = _make_update(thread_id=541, forum_topic_closed=SimpleNamespace())
    built_event = MagicMock(spec=MessageEvent)
    with patch.object(adapter, "_build_message_event", return_value=built_event):
        # Act
        await adapter._handle_forum_topic_event(update, context=None)

    # Assert
    adapter.handle_message.assert_awaited_once_with(built_event)


@pytest.mark.asyncio
async def test_given_forum_topic_edited_when_handle_called_then_dispatches_event():
    # Arrange
    adapter = _make_adapter()
    edited = SimpleNamespace(name="Sprint 1 (renamed)")
    update = _make_update(thread_id=541, forum_topic_edited=edited)
    built_event = MagicMock(spec=MessageEvent)
    with patch.object(adapter, "_build_message_event", return_value=built_event):
        # Act
        await adapter._handle_forum_topic_event(update, context=None)

    # Assert
    adapter.handle_message.assert_awaited_once_with(built_event)


@pytest.mark.asyncio
async def test_given_no_message_when_handle_called_then_skips_silently():
    # Arrange
    adapter = _make_adapter()
    update = SimpleNamespace(update_id=99, message=None)

    # Act
    await adapter._handle_forum_topic_event(update, context=None)

    # Assert
    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_given_forum_topic_event_when_build_message_event_called_then_uses_text_type():
    # Arrange
    adapter = _make_adapter()
    update = _make_update(thread_id=570, forum_topic_created=SimpleNamespace(name="Feature X"))
    captured = {}

    def capture(msg, msg_type, **kwargs):
        captured["msg_type"] = msg_type
        captured["update_id"] = kwargs.get("update_id")
        return MagicMock(spec=MessageEvent)

    with patch.object(adapter, "_build_message_event", side_effect=capture):
        # Act
        await adapter._handle_forum_topic_event(update, context=None)

    # Assert
    assert captured["msg_type"] == MessageType.TEXT
    assert captured["update_id"] == 99

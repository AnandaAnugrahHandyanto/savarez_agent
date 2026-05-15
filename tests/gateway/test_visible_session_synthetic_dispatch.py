"""Tests for trusted synthetic visible-session dispatch."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult
from gateway.session import SessionSource, build_session_key


class _StubAdapter(BasePlatformAdapter):
    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="sent")

    async def get_chat_info(self, chat_id):
        return {}


def _source(thread_id="14"):
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1003933169427",
        chat_name="Hermes Sessions",
        chat_type="group",
        user_id="6605861022",
        user_name="alice",
        thread_id=thread_id,
    )


def _adapter():
    adapter = _StubAdapter(PlatformConfig(enabled=True, token="token"), Platform.TELEGRAM)
    adapter._send_with_retry = AsyncMock(return_value=SendResult(success=True, message_id="msg1"))
    return adapter


@pytest.mark.asyncio
async def test_send_only_synthetic_dispatch_posts_to_thread_without_agent():
    adapter = _adapter()
    adapter._message_handler = AsyncMock(return_value="agent response")

    session_key = await adapter.dispatch_synthetic_message(
        text="visible header",
        source=_source(),
        mode="send_only",
    )

    assert session_key == build_session_key(_source())
    adapter._message_handler.assert_not_called()
    adapter._send_with_retry.assert_awaited_once_with(
        chat_id="-1003933169427",
        content="visible header",
        reply_to=None,
        metadata={"thread_id": "14"},
    )


@pytest.mark.asyncio
async def test_queue_synthetic_dispatch_appends_pending_without_interrupting_active_session():
    adapter = _adapter()
    adapter._message_handler = AsyncMock(return_value="agent response")
    source = _source()
    session_key = build_session_key(source)
    interrupt_guard = asyncio.Event()
    adapter._active_sessions[session_key] = interrupt_guard

    returned = await adapter.dispatch_synthetic_message(
        text="queued child prompt",
        source=source,
        mode="queue",
    )

    assert returned == session_key
    assert adapter._pending_messages[session_key].text == "queued child prompt"
    assert adapter._pending_messages[session_key].internal is True
    assert interrupt_guard.is_set() is False
    adapter._message_handler.assert_not_called()
    assert session_key not in adapter._session_tasks


@pytest.mark.asyncio
async def test_interrupt_synthetic_dispatch_uses_normal_handle_message_path():
    adapter = _adapter()
    first_seen = asyncio.Event()

    async def handler(event: MessageEvent):
        assert event.internal is True
        assert event.text == "run now"
        first_seen.set()
        return "ok"

    adapter._message_handler = handler

    session_key = await adapter.dispatch_synthetic_message(
        text="run now",
        source=_source(),
        mode="interrupt",
    )

    assert session_key == build_session_key(_source())
    await asyncio.wait_for(first_seen.wait(), timeout=1.0)
    await adapter.cancel_background_tasks()


@pytest.mark.asyncio
async def test_steer_synthetic_dispatch_rewrites_to_steer_command():
    adapter = _adapter()
    seen_texts = []

    async def handler(event: MessageEvent):
        seen_texts.append(event.text)
        return "ok"

    adapter._message_handler = handler

    await adapter.dispatch_synthetic_message(
        text="adjust course",
        source=_source(),
        mode="steer",
    )

    await asyncio.sleep(0)
    assert seen_texts == ["/steer adjust course"]
    await adapter.cancel_background_tasks()

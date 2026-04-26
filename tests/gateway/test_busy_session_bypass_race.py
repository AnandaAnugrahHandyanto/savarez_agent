import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource, build_session_key


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        user_name="tester",
        chat_id="c1",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=_make_source(),
        message_id="m1",
    )


def _make_runner_and_adapter():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._busy_ack_ts = {}
    runner._draining = False
    runner._restart_requested = False
    runner._update_prompt_pending = {}
    runner._is_user_authorized = lambda _source: True
    runner.hooks = SimpleNamespace(emit=AsyncMock())
    runner.config = {}

    adapter = MagicMock()
    adapter._pending_messages = {}
    adapter._active_sessions = {}
    runner.adapters = {Platform.TELEGRAM: adapter}

    runner._handle_message_with_agent = AsyncMock(return_value="SHOULD_NOT_RUN")
    return runner, adapter


@pytest.mark.asyncio
async def test_busy_bypass_queue_uses_busy_semantics_without_running_agent():
    runner, adapter = _make_runner_and_adapter()
    event = _make_event("/queue remember this")
    session_key = build_session_key(event.source)
    adapter._active_sessions[session_key] = asyncio.Event()
    setattr(event, "_busy_session_bypass", True)

    result = await runner._handle_message(event)

    assert result == "Queued for the next turn."
    runner._handle_message_with_agent.assert_not_awaited()
    assert session_key in adapter._pending_messages
    assert adapter._pending_messages[session_key].text == "remember this"


@pytest.mark.asyncio
async def test_busy_bypass_queue_preserves_photo_media_without_running_agent():
    runner, adapter = _make_runner_and_adapter()
    event = MessageEvent(
        text="/queue look at this image",
        message_type=MessageType.PHOTO,
        source=_make_source(),
        message_id="m-photo",
        media_urls=["/tmp/photo-a.jpg"],
        media_types=["image/jpeg"],
    )
    session_key = build_session_key(event.source)
    adapter._active_sessions[session_key] = asyncio.Event()
    setattr(event, "_busy_session_bypass", True)

    result = await runner._handle_message(event)

    assert result == "Queued for the next turn."
    queued = adapter._pending_messages[session_key]
    assert queued.text == "look at this image"
    assert queued.message_type == MessageType.PHOTO
    assert queued.media_urls == ["/tmp/photo-a.jpg"]
    assert queued.media_types == ["image/jpeg"]
    runner._handle_message_with_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_busy_bypass_queue_allows_media_without_prompt_text():
    runner, adapter = _make_runner_and_adapter()
    event = MessageEvent(
        text="/queue",
        message_type=MessageType.DOCUMENT,
        source=_make_source(),
        message_id="m-doc",
        media_urls=["/tmp/file.pdf"],
        media_types=["application/pdf"],
    )
    session_key = build_session_key(event.source)
    adapter._active_sessions[session_key] = asyncio.Event()
    setattr(event, "_busy_session_bypass", True)

    result = await runner._handle_message(event)

    assert result == "Queued for the next turn."
    queued = adapter._pending_messages[session_key]
    assert queued.text == ""
    assert queued.message_type == MessageType.DOCUMENT
    assert queued.media_urls == ["/tmp/file.pdf"]
    assert queued.media_types == ["application/pdf"]
    runner._handle_message_with_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_busy_bypass_model_rejects_without_running_agent():
    runner, adapter = _make_runner_and_adapter()
    event = _make_event("/model gpt-5")
    session_key = build_session_key(event.source)
    adapter._active_sessions[session_key] = asyncio.Event()
    setattr(event, "_busy_session_bypass", True)

    result = await runner._handle_message(event)

    assert result == "Agent is running — wait or /stop first, then switch models."
    runner._handle_message_with_agent.assert_not_awaited()
    assert adapter._pending_messages == {}

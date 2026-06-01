from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, SessionSource
from gateway.platforms.telegram import TelegramAdapter
from gateway.run import GatewayRunner


@pytest.mark.asyncio
async def test_telegram_send_skips_typing_refresh_for_final_notify_response():
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=123))
    )
    adapter.send_typing = AsyncMock()

    result = await adapter.send("12345", "resposta final", metadata={"notify": True})

    assert result.success is True
    adapter._bot.send_message.assert_awaited_once()
    adapter.send_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_telegram_send_keeps_typing_refresh_when_metadata_is_none():
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=321))
    )
    adapter.send_typing = AsyncMock()

    result = await adapter.send("12345", "andamento", metadata=None)

    assert result.success is True
    adapter._bot.send_message.assert_awaited_once()
    adapter.send_typing.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_send_keeps_typing_refresh_for_intermediate_message():
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=456))
    )
    adapter.send_typing = AsyncMock()

    result = await adapter.send("12345", "andamento", metadata={})

    assert result.success is True
    adapter._bot.send_message.assert_awaited_once()
    adapter.send_typing.assert_awaited_once()


@pytest.mark.asyncio
async def test_busy_handler_clears_stale_adapter_guard_when_runner_has_no_agent():
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._running_agents = {}
    runner._draining = False
    runner._busy_input_mode = "interrupt"
    runner._busy_text_mode = "interrupt"
    runner._is_user_authorized = lambda source: True

    adapter = SimpleNamespace(
        cancel_session_processing=AsyncMock(),
        _start_session_processing=lambda event, session_key: setattr(
            adapter, "started", (event, session_key)
        ),
    )
    runner.adapters[Platform.TELEGRAM] = adapter

    event = MessageEvent(
        text="nova mensagem",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="8367618544",
            user_id="8367618544",
            chat_type="dm",
        ),
    )

    handled = await runner._handle_active_session_busy_message(event, "telegram:8367618544")

    assert handled is True
    adapter.cancel_session_processing.assert_awaited_once_with(
        "telegram:8367618544",
        release_guard=True,
        discard_pending=True,
    )
    assert adapter.started == (event, "telegram:8367618544")


@pytest.mark.asyncio
async def test_busy_handler_does_not_restart_if_stale_guard_cancel_fails():
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._running_agents = {}
    runner._draining = False
    runner._busy_input_mode = "interrupt"
    runner._busy_text_mode = "interrupt"
    runner._is_user_authorized = lambda source: True

    adapter = SimpleNamespace(
        cancel_session_processing=AsyncMock(side_effect=RuntimeError("boom")),
        _start_session_processing=AsyncMock(),
    )
    runner.adapters[Platform.TELEGRAM] = adapter

    event = MessageEvent(
        text="nova mensagem",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="8367618544",
            user_id="8367618544",
            chat_type="dm",
        ),
    )

    handled = await runner._handle_active_session_busy_message(event, "telegram:8367618544")

    assert handled is False
    adapter.cancel_session_processing.assert_awaited_once_with(
        "telegram:8367618544",
        release_guard=True,
        discard_pending=True,
    )
    adapter._start_session_processing.assert_not_awaited()

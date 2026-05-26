from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _make_event() -> MessageEvent:
    source = SessionSource(
        platform=Platform.SLACK,
        user_id="U123",
        chat_id="C123",
        user_name="tester",
        chat_type="group",
        thread_id="1716412345.6789",
    )
    return MessageEvent(text="/stop", source=source, message_id="1716412350.0001")


def _make_runner(event: MessageEvent):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {Platform.SLACK: MagicMock(stop_typing=AsyncMock())}
    runner._running_agents = {}
    runner._interrupt_and_clear_session = AsyncMock()
    runner._voice_mode = {}

    session_entry = SessionEntry(
        session_key=build_session_key(event.source),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.SLACK,
        chat_type="group",
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    return runner


@pytest.mark.asyncio
async def test_stop_command_clears_slack_status_without_active_agent():
    event = _make_event()
    runner = _make_runner(event)

    result = await runner._handle_stop_command(event)

    runner.adapters[Platform.SLACK].stop_typing.assert_awaited_once_with(
        "C123",
        metadata={"thread_id": "1716412345.6789"},
    )
    assert "active" in result.lower()

"""Tests for gateway /start onboarding command."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/start"):
    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="12345",
        chat_id="67890",
        chat_type="dm",
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner.config = {}
    runner.session_store = None
    runner._voice_mode = {}
    runner._update_prompt_pending = {}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._failed_platforms = {}
    runner._draining = False
    runner._is_user_authorized = MagicMock(return_value=True)
    runner._session_key_for_source = MagicMock(return_value="agent:main:telegram:dm:67890")
    runner._handle_message_with_agent = AsyncMock(return_value="agent should not run")
    return runner


@pytest.mark.asyncio
async def test_start_command_returns_onboarding_without_agent_loop():
    runner = _make_runner()

    result = await runner._handle_message(_make_event("/start"))

    assert result is not None
    assert "Hermes" in result
    assert "/sethome" in result
    runner._handle_message_with_agent.assert_not_awaited()

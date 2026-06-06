"""Regression: slash commands must not be silently dropped in busy queue mode.

Issue #40683 — when busy_text_mode="queue" and effective_mode != "steer",
the busy handler returned False immediately, causing slash commands like
/steer, /stop, /new to fall through to _handle_message as plain text and
get queued for the next turn instead of being dispatched as commands.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource


def _make_event(text: str) -> MessageEvent:
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="123", chat_type="dm")
    return MessageEvent(text=text, message_type=MessageType.TEXT, source=source)


def _make_runner():
    """Return a minimal GatewayRunner-like object for testing the busy handler."""
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}
    runner._draining = False
    runner._busy_input_mode = "interrupt"
    runner._busy_text_mode = "queue"
    runner._busy_ack_ts = {}
    runner.adapters = {}
    runner._is_user_authorized = MagicMock(return_value=True)
    runner._agent_has_active_subagents = MagicMock(return_value=False)
    runner._queue_or_replace_pending_event = MagicMock()
    return runner


class TestSlashCommandsNotDroppedInQueueMode:
    """Slash commands must reach the dispatcher even in busy queue mode."""

    @pytest.mark.asyncio
    async def test_steer_not_dropped(self):
        runner = _make_runner()
        event = _make_event("/steer change approach")
        session_key = "telegram:123:dm"

        result = await runner._handle_active_session_busy_message(event, session_key)

        # False means "not handled here, let dispatcher take it" — which is
        # correct for commands that need the full dispatcher. The key assertion
        # is that _queue_or_replace_pending_event was NOT called (command not queued).
        runner._queue_or_replace_pending_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_plain_text_still_queued(self):
        runner = _make_runner()
        event = _make_event("hello world")
        session_key = "telegram:123:dm"

        result = await runner._handle_active_session_busy_message(event, session_key)

        assert result is False  # plain text: let default path handle (queue)

    @pytest.mark.asyncio
    async def test_unknown_command_still_queued(self):
        runner = _make_runner()
        event = _make_event("/unknownxyz")
        session_key = "telegram:123:dm"

        result = await runner._handle_active_session_busy_message(event, session_key)

        assert result is False  # unknown command: queue it

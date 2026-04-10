"""Tests for /side gateway slash command.

/side runs a lightweight side-question task without interrupting the main
session. The side question uses session context, does not persist history,
and returns its answer back to the same chat.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/side", platform=Platform.TELEGRAM,
                user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._background_tasks = set()

    mock_store = MagicMock()
    runner.session_store = mock_store

    from gateway.hooks import HookRegistry
    runner.hooks = HookRegistry()

    return runner


class TestHandleSideCommand:
    @pytest.mark.asyncio
    async def test_no_question_shows_usage(self):
        runner = _make_runner()
        event = _make_event(text="/side")
        result = await runner._handle_side_command(event)
        assert "Usage:" in result
        assert "/side" in result

    @pytest.mark.asyncio
    async def test_empty_question_shows_usage(self):
        runner = _make_runner()
        event = _make_event(text="/side   ")
        result = await runner._handle_side_command(event)
        assert "Usage:" in result

    @pytest.mark.asyncio
    async def test_valid_question_starts_task(self):
        runner = _make_runner()
        created_tasks = []

        def capture_task(coro, *args, **kwargs):
            coro.close()
            mock_task = MagicMock()
            created_tasks.append(mock_task)
            return mock_task

        with patch("gateway.run.asyncio.create_task", side_effect=capture_task):
            event = _make_event(text="/side what does /sethome do?")
            result = await runner._handle_side_command(event)

        assert "💬" in result
        assert "/side:" in result
        assert "side_" in result
        assert len(created_tasks) == 1


class TestSideCommandRegistration:
    @pytest.mark.asyncio
    async def test_side_in_help_output(self):
        runner = _make_runner()
        event = _make_event(text="/help")
        result = await runner._handle_help_command(event)
        assert "/side" in result

    def test_side_is_known_command(self):
        from hermes_cli.commands import GATEWAY_KNOWN_COMMANDS
        assert "side" in GATEWAY_KNOWN_COMMANDS

    def test_side_in_commands_dict(self):
        from hermes_cli.commands import COMMANDS
        assert "/side" in COMMANDS

    def test_side_in_session_category(self):
        from hermes_cli.commands import COMMANDS_BY_CATEGORY
        assert "/side" in COMMANDS_BY_CATEGORY["Session"]

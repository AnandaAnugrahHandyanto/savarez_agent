"""Tests for gateway /commands pagination and discovery text."""

from unittest.mock import AsyncMock, MagicMock

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="/commands", platform=Platform.TELEGRAM, user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._show_reasoning = False
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.hooks.loaded_hooks = []
    runner._session_db = None
    runner._get_or_create_gateway_honcho = lambda session_key: (None, None)
    return runner


class TestCommandsCommand:
    @pytest.mark.asyncio
    async def test_help_mentions_commands_pagination(self):
        runner = _make_runner()

        result = await runner._handle_help_command(_make_event("/help"))

        assert "Use `/commands` for a paginated list" in result

    @pytest.mark.asyncio
    async def test_commands_first_page_is_paginated(self):
        runner = _make_runner()

        result = await runner._handle_commands_command(_make_event("/commands"))

        assert "page 1/" in result
        assert "Use `/commands 1` or `/commands 2`" in result
        assert "`/new` -- Start a new session" in result

    @pytest.mark.asyncio
    async def test_commands_invalid_page_returns_usage(self):
        runner = _make_runner()

        result = await runner._handle_commands_command(_make_event("/commands nope"))

        assert result == "Usage: `/commands [page]`"

    @pytest.mark.asyncio
    async def test_commands_out_of_range_clamps_page(self):
        runner = _make_runner()

        result = await runner._handle_commands_command(_make_event("/commands 999"))

        assert "Requested page 999 was out of range" in result

"""Runner-level tests for slash commands while an agent is already running."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, SendResult
from gateway.run import GatewayRunner
from gateway.session import SessionSource, build_session_key


class _PendingAdapter:
    def __init__(self):
        self._pending_messages = {}

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="1")


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="dm",
        user_id="user-1",
        user_name="tester",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=_make_source(),
        message_id="m1",
    )


def _make_runner() -> GatewayRunner:
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.adapters = {Platform.TELEGRAM: _PendingAdapter()}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._pending_model_notes = {}
    runner._update_prompt_pending = {}
    runner._voice_mode = {}
    runner._draining = False
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._session_db = MagicMock()
    runner.session_store = MagicMock()
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=[])
    runner.pairing_store = MagicMock()
    runner._is_user_authorized = lambda _source: True
    runner._queue_during_drain_enabled = lambda: False
    return runner


class TestBusySessionExecImmediateCommands:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("cmd", "canonical", "handler_attr"),
        [
            ("/help", "help", "_handle_help_command"),
            ("/commands", "commands", "_handle_commands_command"),
            ("/profile", "profile", "_handle_profile_command"),
            ("/provider", "provider", "_handle_provider_command"),
            ("/usage", "usage", "_handle_usage_command"),
            ("/insights", "insights", "_handle_insights_command"),
            ("/sethome", "sethome", "_handle_set_home_command"),
            ("/set-home", "sethome", "_handle_set_home_command"),
            ("/voice", "voice", "_handle_voice_command"),
            ("/yolo", "yolo", "_handle_yolo_command"),
            ("/btw side question", "btw", "_handle_btw_command"),
        ],
    )
    async def test_exec_immediate_command_returns_without_interrupt(self, cmd, canonical, handler_attr):
        runner = _make_runner()
        source = _make_source()
        session_key = build_session_key(source)
        running_agent = MagicMock()
        runner._running_agents[session_key] = running_agent
        setattr(runner, handler_attr, AsyncMock(return_value=f"handled:{canonical}"))

        result = await runner._handle_message(_make_event(cmd))

        assert result == f"handled:{canonical}"
        running_agent.interrupt.assert_not_called()
        assert runner._pending_messages == {}


class TestBusySessionRejectCommands:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("cmd", "expected"),
        [
            ("/model", "Agent is running — wait or /stop first, then switch models."),
            ("/retry", "Agent is running — wait or /stop first."),
            ("/undo", "Agent is running — wait or /stop first."),
            ("/title", "Agent is running — wait or /stop first."),
            ("/branch", "Agent is running — wait or /stop first."),
            ("/fork", "Agent is running — wait or /stop first."),
            ("/compress", "Agent is running — wait or /stop first."),
            ("/rollback", "Agent is running — wait or /stop first."),
            ("/resume", "Agent is running — wait or /stop first."),
            ("/reasoning", "Agent is running — wait or /stop first."),
            ("/fast", "Agent is running — wait or /stop first."),
            ("/personality", "Agent is running — wait or /stop first."),
            ("/update", "Agent is running — wait or /stop first."),
            ("/reload-mcp", "Agent is running — wait or /stop first."),
            ("/reload_mcp", "Agent is running — wait or /stop first."),
        ],
    )
    async def test_reject_command_returns_helpful_message_without_interrupt(self, cmd, expected):
        runner = _make_runner()
        source = _make_source()
        session_key = build_session_key(source)
        running_agent = MagicMock()
        runner._running_agents[session_key] = running_agent

        result = await runner._handle_message(_make_event(cmd))

        assert result == expected
        running_agent.interrupt.assert_not_called()
        assert runner._pending_messages == {}

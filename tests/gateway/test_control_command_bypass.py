"""Tests for control-command bypass in _handle_active_session_busy_message (#26813).

Verifies that /stop, /interrupt, /cancel (and their plain-text equivalents)
always interrupt a running agent, even when busy_input_mode is "steer" or "queue".
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs so we can import gateway code without heavy deps
# ---------------------------------------------------------------------------
import sys, types

_tg = types.ModuleType("telegram")
_tg.constants = types.ModuleType("telegram.constants")
_ct = MagicMock()
_ct.SUPERGROUP = "supergroup"
_ct.GROUP = "group"
_ct.PRIVATE = "private"
_tg.constants.ChatType = _ct
sys.modules.setdefault("telegram", _tg)
sys.modules.setdefault("telegram.constants", _tg.constants)
sys.modules.setdefault("telegram.ext", types.ModuleType("telegram.ext"))

from gateway.platforms.base import (
    MessageEvent,
    MessageType,
    SessionSource,
    build_session_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(text="/stop", chat_id="123", platform_val="telegram"):
    source = SessionSource(
        platform=MagicMock(value=platform_val),
        chat_id=chat_id,
        chat_type="private",
        user_id="user1",
    )
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=source,
        message_id="msg1",
    )


def _make_runner():
    from gateway.run import GatewayRunner, _AGENT_PENDING_SENTINEL

    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._busy_ack_ts = {}
    runner._draining = False
    runner.adapters = {}
    runner.config = MagicMock()
    runner.session_store = None
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.pairing_store = MagicMock()
    runner.pairing_store.is_approved.return_value = True
    runner._is_user_authorized = lambda _source: True
    return runner, _AGENT_PENDING_SENTINEL


def _make_adapter(platform_val="telegram"):
    adapter = MagicMock()
    adapter._pending_messages = {}
    adapter._send_with_retry = AsyncMock()
    adapter.config = MagicMock()
    adapter.config.extra = {}
    adapter.platform = MagicMock(value=platform_val)
    return adapter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestControlCommandBypass:
    """Control commands must bypass steer/queue and force an interrupt."""

    @pytest.mark.asyncio
    async def test_stop_in_steer_mode_interrupts(self):
        """/stop in steer mode → agent.interrupt() called, steer() NOT called."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="/stop")
        sk = build_session_key(event.source)

        agent = MagicMock()
        agent.steer = MagicMock(return_value=True)
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_called_once_with("/stop")
        agent.steer.assert_not_called()

    @pytest.mark.asyncio
    async def test_interrupt_in_steer_mode_interrupts(self):
        """/interrupt in steer mode → forced interrupt."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="/interrupt")
        sk = build_session_key(event.source)

        agent = MagicMock()
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_called_once_with("/interrupt")
        agent.steer.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_in_queue_mode_interrupts(self):
        """/cancel in queue mode → forced interrupt (not queued)."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "queue"
        adapter = _make_adapter()

        event = _make_event(text="/cancel")
        sk = build_session_key(event.source)

        agent = MagicMock()
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        with patch("gateway.run.merge_pending_message_event") as mock_merge:
            await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_called_once_with("/cancel")
        # The control command must NOT be queued for next turn
        mock_merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_plain_stop_in_steer_mode_interrupts(self):
        """Plain 'stop' (no slash) in steer mode → also forced interrupt (Feishu case)."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="stop")
        sk = build_session_key(event.source)

        agent = MagicMock()
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_called_once_with("stop")
        agent.steer.assert_not_called()

    @pytest.mark.asyncio
    async def test_plain_interrupt_in_queue_mode_interrupts(self):
        """Plain 'interrupt' in queue mode → forced interrupt."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "queue"
        adapter = _make_adapter()

        event = _make_event(text="interrupt")
        sk = build_session_key(event.source)

        agent = MagicMock()
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        with patch("gateway.run.merge_pending_message_event"):
            await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_called_once_with("interrupt")

    @pytest.mark.asyncio
    async def test_non_control_text_still_stears(self):
        """Normal text in steer mode → still steered (not intercepted)."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="also check the tests")
        sk = build_session_key(event.source)

        agent = MagicMock()
        agent.steer = MagicMock(return_value=True)
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        with patch("gateway.run.merge_pending_message_event"):
            await runner._handle_active_session_busy_message(event, sk)

        agent.steer.assert_called_once_with("also check the tests")
        agent.interrupt.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_control_text_in_queue_still_queues(self):
        """Normal text in queue mode → still queued (not interrupted)."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "queue"
        adapter = _make_adapter()

        event = _make_event(text="add this later")
        sk = build_session_key(event.source)

        agent = MagicMock()
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        with patch("gateway.run.merge_pending_message_event") as mock_merge:
            await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_not_called()
        mock_merge.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_with_mention_suffix(self):
        """/stop@botname in steer mode → forced interrupt (mention stripped)."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="/stop@hermes_bot")
        sk = build_session_key(event.source)

        agent = MagicMock()
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        await runner._handle_active_session_busy_message(event, sk)

        agent.interrupt.assert_called_once()
        agent.steer.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_pending_sentinel_no_crash(self):
        """/stop when agent is still pending (sentinel) → no crash, no interrupt call."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="/stop")
        sk = build_session_key(event.source)

        runner._running_agents[sk] = sentinel
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        # Should not raise; interrupt is skipped because agent is sentinel
        await runner._handle_active_session_busy_message(event, sk)

    @pytest.mark.asyncio
    async def test_control_command_ack_sent(self):
        """Control command interrupt should still send busy ack."""
        runner, sentinel = _make_runner()
        runner._busy_input_mode = "steer"
        adapter = _make_adapter()

        event = _make_event(text="/stop")
        sk = build_session_key(event.source)

        agent = MagicMock()
        agent.get_activity_summary.return_value = {
            "api_call_count": 1,
            "max_iterations": 60,
            "current_tool": None,
            "last_activity_ts": time.time(),
            "last_activity_desc": "thinking",
            "seconds_since_activity": 0.5,
        }
        runner._running_agents[sk] = agent
        runner._running_agents_ts[sk] = time.time()
        runner.adapters[event.source.platform] = adapter

        await runner._handle_active_session_busy_message(event, sk)

        # Busy ack should have been sent
        adapter._send_with_retry.assert_called_once()

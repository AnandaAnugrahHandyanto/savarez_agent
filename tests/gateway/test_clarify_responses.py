"""Tests for gateway clarify response handling."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=_make_source(),
        message_id="m1",
    )


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    adapter.resume_typing_for_chat = MagicMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._busy_ack_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._background_tasks = set()
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._draining = False
    runner._update_prompt_pending = {}
    runner._queue_during_drain_enabled = lambda: False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    return runner


class _ClarifyAwareAdapter:
    def __init__(self):
        self.send = AsyncMock()
        self.resume_typing_for_chat = MagicMock()
        self._clear_clarify_card_state = MagicMock()

    def clear_clarify_card_state(self, clarify_id: int) -> None:
        self._clear_clarify_card_state(clarify_id)


def _clear_clarify_state():
    from tools import clarify_state as mod

    mod._gateway_queues.clear()


class TestGatewayClarifyResponses:
    def setup_method(self):
        _clear_clarify_state()

    @pytest.mark.asyncio
    async def test_handle_clarify_response_resolves_pending_question(self):
        from tools.clarify_state import _ClarifyEntry, _gateway_queues

        runner = _make_runner()
        source = _make_source()
        session_key = runner._session_key_for_source(source)
        entry = _ClarifyEntry(clarify_id=1, question="Pick", choices=["Alpha", "Beta"])
        _gateway_queues[session_key] = [entry]

        result = await runner._handle_clarify_response(_make_event("2"))

        assert "继续处理" in result
        assert entry.event.is_set()
        assert entry.result == "Beta"
        runner.adapters[Platform.TELEGRAM].resume_typing_for_chat.assert_called_once_with("c1")

    @pytest.mark.asyncio
    async def test_handle_clarify_response_clears_card_state_for_text_reply(self):
        from tools.clarify_state import _ClarifyEntry, _gateway_queues

        runner = _make_runner()
        runner.adapters[Platform.TELEGRAM] = _ClarifyAwareAdapter()
        source = _make_source()
        session_key = runner._session_key_for_source(source)
        entry = _ClarifyEntry(clarify_id=42, question="Pick", choices=["Alpha", "Beta"])
        _gateway_queues[session_key] = [entry]

        await runner._handle_clarify_response(_make_event("Alpha"))

        runner.adapters[Platform.TELEGRAM]._clear_clarify_card_state.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_running_session_routes_text_to_clarify_instead_of_interrupt(self):
        from tools.clarify_state import _ClarifyEntry, _gateway_queues

        runner = _make_runner()
        event = _make_event("Option A")
        session_key = runner._session_key_for_source(event.source)
        _gateway_queues[session_key] = [_ClarifyEntry(clarify_id=1, question="Pick", choices=["Option A", "Option B"])]

        running_agent = MagicMock()
        runner._running_agents[session_key] = running_agent
        runner._running_agents_ts[session_key] = 0

        with patch.object(runner, "_handle_clarify_response", new_callable=AsyncMock, return_value="resolved") as mock_handle:
            result = await runner._handle_message(event)

        assert result == "resolved"
        mock_handle.assert_awaited_once()
        running_agent.interrupt.assert_not_called()

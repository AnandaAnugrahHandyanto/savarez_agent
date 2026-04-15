"""Tests for gateway /status behavior and token persistence."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


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


def _make_runner(session_entry: SessionEntry):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    return runner


@pytest.mark.asyncio
async def test_status_command_reports_running_agent_without_interrupt(monkeypatch):
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=321,
    )
    runner = _make_runner(session_entry)
    running_agent = MagicMock()
    runner._running_agents[build_session_key(_make_source())] = running_agent

    result = await runner._handle_message(_make_event("/status"))

    assert "**Session ID:** `sess-1`" in result
    assert "**Tokens:** 321" in result
    assert "**Agent Running:** Yes ⚡" in result
    assert "**Title:**" not in result
    running_agent.interrupt.assert_not_called()
    assert runner._pending_messages == {}


@pytest.mark.asyncio
async def test_status_command_includes_session_title_when_present():
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=321,
    )
    runner = _make_runner(session_entry)
    runner._session_db.get_session_title.return_value = "My titled session"

    result = await runner._handle_message(_make_event("/status"))

    assert "**Session ID:** `sess-1`" in result
    assert "**Title:** My titled session" in result


@pytest.mark.asyncio
async def test_handle_message_persists_agent_token_counts(monkeypatch):
    import gateway.run as gateway_run

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    runner.session_store.load_transcript.return_value = [{"role": "user", "content": "earlier"}]
    runner._run_agent = AsyncMock(
        return_value={
            "final_response": "ok",
            "messages": [],
            "tools": [],
            "history_offset": 0,
            "last_prompt_tokens": 80,
            "input_tokens": 120,
            "output_tokens": 45,
            "model": "openai/test-model",
        }
    )

    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"})
    monkeypatch.setattr(
        "agent.model_metadata.get_model_context_length",
        lambda *_args, **_kwargs: 100000,
    )

    result = await runner._handle_message(_make_event("hello"))

    assert result == "ok"
    runner.session_store.update_session.assert_called_once_with(
        session_entry.session_key,
        last_prompt_tokens=80,
    )


@pytest.mark.asyncio
async def test_now_command_interrupts_running_agent_and_queues_follow_up():
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-now",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=321,
    )
    runner = _make_runner(session_entry)
    # _queue_or_replace_pending_event writes to adapter._pending_messages via
    # merge_pending_message_event; give the mock adapter a real dict so the
    # merge helper can store the event.
    runner.adapters[Platform.TELEGRAM]._pending_messages = {}
    running_agent = MagicMock()
    session_key = build_session_key(_make_source())
    runner._running_agents[session_key] = running_agent

    result = await runner._handle_message(_make_event("/now continue the draft"))

    running_agent.interrupt.assert_called_once_with("continue the draft")
    adapter_pending = runner.adapters[Platform.TELEGRAM]._pending_messages
    assert session_key in adapter_pending
    assert adapter_pending[session_key].text == "continue the draft"
    # The legacy str-map must stay untouched — writing a MessageEvent there is
    # a type violation and crashes the interrupt-concatenation path.
    assert session_key not in runner._pending_messages
    assert "Interrupted" in result and "continue the draft" in result


@pytest.mark.asyncio
async def test_now_command_rejects_empty_prompt():
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-now-empty",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    runner.adapters[Platform.TELEGRAM]._pending_messages = {}
    running_agent = MagicMock()
    session_key = build_session_key(_make_source())
    runner._running_agents[session_key] = running_agent

    result = await runner._handle_message(_make_event("/now"))

    assert "Usage" in result
    running_agent.interrupt.assert_not_called()
    assert runner.adapters[Platform.TELEGRAM]._pending_messages == {}


@pytest.mark.asyncio
async def test_now_command_queues_without_interrupt_during_sentinel():
    from gateway.run import _AGENT_PENDING_SENTINEL

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-now-sentinel",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    runner.adapters[Platform.TELEGRAM]._pending_messages = {}
    session_key = build_session_key(_make_source())
    runner._running_agents[session_key] = _AGENT_PENDING_SENTINEL

    result = await runner._handle_message(_make_event("/now finish this"))

    adapter_pending = runner.adapters[Platform.TELEGRAM]._pending_messages
    assert session_key in adapter_pending
    assert adapter_pending[session_key].text == "finish this"
    assert "Queued" in result and "finish this" in result


@pytest.mark.asyncio
async def test_btw_command_does_not_interrupt_running_agent():
    """/btw must spawn its side-agent path without touching the running agent."""
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-btw",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_runner(session_entry)
    runner.adapters[Platform.TELEGRAM]._pending_messages = {}
    running_agent = MagicMock()
    session_key = build_session_key(_make_source())
    runner._running_agents[session_key] = running_agent

    sentinel_response = "💬 /btw dispatched"
    runner._handle_btw_command = AsyncMock(return_value=sentinel_response)

    result = await runner._handle_message(_make_event("/btw who owns sanitization?"))

    assert result == sentinel_response
    runner._handle_btw_command.assert_awaited_once()
    # Running agent must be untouched — no interrupt, no pending text leak.
    running_agent.interrupt.assert_not_called()
    assert session_key in runner._running_agents
    assert runner.adapters[Platform.TELEGRAM]._pending_messages == {}
    assert runner._pending_messages == {}



@pytest.mark.asyncio
async def test_status_command_bypasses_active_session_guard():
    """When an agent is running, /status must be dispatched immediately via
    base.handle_message — not queued or treated as an interrupt (#5046)."""
    import asyncio
    from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType
    from gateway.session import build_session_key
    from gateway.config import Platform, PlatformConfig, GatewayConfig

    source = _make_source()
    session_key = build_session_key(source)

    handler_called_with = []

    async def fake_handler(event):
        handler_called_with.append(event)
        return "📊 **Hermes Gateway Status**\n**Agent Running:** Yes ⚡"

    # Concrete subclass to avoid abstract method errors
    class _ConcreteAdapter(BasePlatformAdapter):
        platform = Platform.TELEGRAM

        async def connect(self): pass
        async def disconnect(self): pass
        async def send(self, chat_id, content, **kwargs): pass
        async def get_chat_info(self, chat_id): return {}

    platform_config = PlatformConfig(enabled=True, token="***")
    adapter = _ConcreteAdapter(platform_config, Platform.TELEGRAM)
    adapter.set_message_handler(fake_handler)

    sent = []

    async def fake_send_with_retry(chat_id, content, reply_to=None, metadata=None):
        sent.append(content)

    adapter._send_with_retry = fake_send_with_retry

    # Simulate an active session
    interrupt_event = asyncio.Event()
    adapter._active_sessions[session_key] = interrupt_event

    event = MessageEvent(
        text="/status",
        source=source,
        message_id="m1",
        message_type=MessageType.COMMAND,
    )
    await adapter.handle_message(event)

    assert handler_called_with, "/status handler was never called (event was queued or dropped)"
    assert sent, "/status response was never sent"
    assert "Agent Running" in sent[0]
    assert not interrupt_event.is_set(), "/status incorrectly triggered an agent interrupt"
    assert session_key not in adapter._pending_messages, "/status was incorrectly queued"

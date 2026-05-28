"""Tests for hook-produced runtime context injection in gateway/run.py."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner, _runtime_context_prefix_from_hook_context
from gateway.session import SessionEntry, SessionSource, build_session_key


def test_runtime_context_prefix_renders_brain_context_then_suggested_skills():
    prefix = _runtime_context_prefix_from_hook_context(
        {
            "brain_context": "  [Brain context: TEST]  ",
            "suggested_skills": "[SUGGESTED_SKILLS: brain-first-lookup.]",
        }
    )

    assert prefix == "[Brain context: TEST]\n\n[SUGGESTED_SKILLS: brain-first-lookup.]"


def test_runtime_context_prefix_skips_empty_and_non_string_values():
    prefix = _runtime_context_prefix_from_hook_context(
        {
            "brain_context": "   ",
            "suggested_skills": ["brain-first-lookup"],
        }
    )

    assert prefix == ""


def test_runtime_context_prefix_skips_oversized_values():
    prefix = _runtime_context_prefix_from_hook_context(
        {
            "brain_context": "x" * (8 * 1024 + 1),
            "suggested_skills": "[SUGGESTED_SKILLS: brain-first-lookup.]",
        }
    )

    assert prefix == "[SUGGESTED_SKILLS: brain-first-lookup.]"


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="208214988",
        chat_id="208214988",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner() -> GatewayRunner:
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    adapter.send_image_file = AsyncMock()
    adapter._bot = None
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), emit_collect=AsyncMock(return_value=[]))
    runner.session_store = MagicMock()
    runner.session_store._generate_session_key.side_effect = lambda source: build_session_key(
        source,
        group_sessions_per_user=getattr(runner.config, "group_sessions_per_user", True),
        thread_sessions_per_user=getattr(runner.config, "thread_sessions_per_user", False),
    )
    runner.session_store.get_or_create_session.side_effect = lambda source, force_new=False: SessionEntry(
        session_key=build_session_key(
            source,
            group_sessions_per_user=getattr(runner.config, "group_sessions_per_user", True),
            thread_sessions_per_user=getattr(runner.config, "thread_sessions_per_user", False),
        ),
        session_id="sess-runtime-context",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        origin=source,
    )
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._queued_events = {}
    runner._busy_ack_ts = {}
    runner._session_model_overrides = {}
    runner._pending_model_notes = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._draining = False
    runner._busy_input_mode = "interrupt"
    runner._is_user_authorized = lambda _source: True
    runner._session_key_for_source = lambda source: build_session_key(
        source,
        group_sessions_per_user=getattr(runner.config, "group_sessions_per_user", True),
        thread_sessions_per_user=getattr(runner.config, "thread_sessions_per_user", False),
    )
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    runner._invalidate_session_run_generation = MagicMock()
    runner._begin_session_run_generation = MagicMock(return_value=1)
    runner._is_session_run_current = MagicMock(return_value=True)
    runner._read_user_config = lambda: {"approvals": {"destructive_slash_confirm": False}}
    runner._release_running_agent_state = MagicMock()
    runner._evict_cached_agent = MagicMock()
    runner._clear_session_boundary_security_state = MagicMock()
    runner._set_session_reasoning_override = MagicMock()
    runner._format_session_info = MagicMock(return_value="")
    return runner


@pytest.mark.asyncio
async def test_agent_start_brain_context_reaches_agent_message(monkeypatch):
    import gateway.run as gateway_run

    runner = _make_runner()
    captured = {}

    async def emit(_event_type, context):
        context["brain_context"] = "[Brain context: TEST]"

    async def run_agent(*_args, **kwargs):
        captured["message"] = kwargs["message"]
        return {"success": True, "final_response": "ok", "messages": []}

    runner.hooks.emit = AsyncMock(side_effect=emit)
    runner._run_agent = AsyncMock(side_effect=run_agent)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"})

    result = await runner._handle_message(_make_event("user text"))

    assert result == "ok"
    assert captured["message"].startswith("[Brain context: TEST]\n\nuser text")


@pytest.mark.asyncio
async def test_agent_start_suggested_skills_reaches_agent_message(monkeypatch):
    import gateway.run as gateway_run

    runner = _make_runner()
    captured = {}

    async def emit(_event_type, context):
        context["suggested_skills"] = "[SUGGESTED_SKILLS: brain-first-lookup.]"

    async def run_agent(*_args, **kwargs):
        captured["message"] = kwargs["message"]
        return {"success": True, "final_response": "ok", "messages": []}

    runner.hooks.emit = AsyncMock(side_effect=emit)
    runner._run_agent = AsyncMock(side_effect=run_agent)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"})

    result = await runner._handle_message(_make_event("user text"))

    assert result == "ok"
    assert captured["message"].startswith("[SUGGESTED_SKILLS: brain-first-lookup.]\n\nuser text")


@pytest.mark.asyncio
async def test_agent_start_hook_error_keeps_original_message(monkeypatch):
    import gateway.run as gateway_run

    runner = _make_runner()
    captured = {}

    async def run_agent(*_args, **kwargs):
        captured["message"] = kwargs["message"]
        return {"success": True, "final_response": "ok", "messages": []}

    async def emit(event_type, _context):
        if event_type == "agent:start":
            raise RuntimeError("boom")

    runner.hooks.emit = AsyncMock(side_effect=emit)
    runner._run_agent = AsyncMock(side_effect=run_agent)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"})

    result = await runner._handle_message(_make_event("user text"))

    assert result == "ok"
    assert captured["message"] == "user text"

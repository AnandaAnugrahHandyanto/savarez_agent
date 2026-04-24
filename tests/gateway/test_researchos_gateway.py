from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _make_source(*, platform: Platform = Platform.TELEGRAM, chat_type: str = "dm") -> SessionSource:
    return SessionSource(
        platform=platform,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type=chat_type,
    )


def _make_event(text: str, *, reply_to_text: str | None = None, platform: Platform = Platform.TELEGRAM, chat_type: str = "dm") -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(platform=platform, chat_type=chat_type), message_id="m1", reply_to_text=reply_to_text)


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")})
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
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
    runner._session_db = None
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
    runner._maybe_handle_people_manager_message = AsyncMock(return_value=None)
    runner._draining = False
    runner._run_agent = AsyncMock(side_effect=AssertionError("should not call agent for ResearchOS gateway hooks"))
    return runner


def _snapshot() -> dict:
    return {
        "week_id": "2026-W17",
        "lifecycle_state": "awaiting_session",
        "gates": {
            "prep_gate_passed": True,
            "live_gate_passed": False,
            "followup_gate_passed": False,
        },
        "prep": {"status": "prep_ready"},
        "live_session": {"status": "not_started"},
        "followup": {"status": "not_started"},
        "schedule": {"rescheduled_to": None, "target_followup_time": None},
    }


@pytest.mark.asyncio
async def test_researchos_status_command_dispatches_without_agent():
    runner = _make_runner()
    runner._get_researchos_status_snapshot = AsyncMock(return_value=_snapshot())

    result = await runner._handle_message(_make_event("/researchos status"))

    assert "ResearchOS status — 2026-W17" in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_researchos_reschedule_command_accepts_natural_time_phrase():
    runner = _make_runner()

    async def _fake_run(script_name, *args):
        if script_name == "mark_session_state.py":
            assert args[0] == "--text"
            assert args[1] == "reschedule to tomorrow 4pm"
            return 0, "2026-W17 -> rescheduled", ""
        if script_name == "workflow_status.py":
            return 0, json.dumps(_snapshot()), ""
        raise AssertionError(f"unexpected script call: {script_name} {args}")

    runner._run_researchos_script = _fake_run

    result = await runner._handle_message(_make_event("/researchos reschedule tomorrow 4pm"))

    assert "Recorded ResearchOS action: reschedule" in result
    assert "ResearchOS status — 2026-W17" in result


@pytest.mark.asyncio
async def test_researchos_reply_shortcut_updates_state_from_telegram_reply():
    runner = _make_runner()

    async def _fake_run(script_name, *args):
        if script_name == "parse_session_intent.py":
            return 0, json.dumps({
                "intent": "start",
                "confidence": "high",
                "normalized_text": "start now",
                "resolved_timestamp": None,
            }), ""
        if script_name == "mark_session_state.py":
            return 0, "2026-W17 -> live_session_in_progress", ""
        if script_name == "workflow_status.py":
            snap = _snapshot()
            snap["lifecycle_state"] = "live_session_in_progress"
            snap["live_session"] = {"status": "in_progress"}
            return 0, json.dumps(snap), ""
        raise AssertionError(f"unexpected script call: {script_name} {args}")

    runner._run_researchos_script = _fake_run

    result = await runner._handle_message(
        _make_event(
            "start now",
            reply_to_text="Weekly research session still unresolved. Reply with: start now, reschedule, or cancel this week.",
        )
    )

    assert "Recorded ResearchOS action from chat: start" in result
    assert "Live status: in_progress" in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_researchos_reply_shortcut_requires_contextual_reply():
    runner = _make_runner()
    runner._run_researchos_script = AsyncMock(side_effect=AssertionError("should not run researchos scripts without contextual reply"))

    result = await runner._maybe_handle_researchos_message(_make_event("resume"))

    assert result is None


@pytest.mark.asyncio
async def test_researchos_command_restricted_to_telegram_dm():
    runner = _make_runner()
    runner._run_researchos_script = AsyncMock(side_effect=AssertionError("should not run researchos scripts outside telegram dm"))

    result = await runner._handle_message(_make_event("/researchos status", platform=Platform.DISCORD, chat_type="channel"))

    assert result == "ResearchOS commands are only available in Telegram DM."

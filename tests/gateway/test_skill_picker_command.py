"""Tests for the gateway /skill picker command."""

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
        chat_id="12345",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner(adapter=None):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    if adapter is None:
        adapter = MagicMock()
        adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )

    source = _make_source()
    session_entry = SessionEntry(
        session_key=build_session_key(source),
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
    from gateway.run import GatewayRunner as _GR
    runner._session_key_for_source = _GR._session_key_for_source.__get__(runner, _GR)
    return runner


@pytest.mark.asyncio
async def test_skill_picker_handler_sends_inline_picker(monkeypatch):
    import agent.skill_commands as skill_commands_mod

    monkeypatch.setattr(
        skill_commands_mod,
        "get_skill_commands",
        lambda: {
            "/youtube-content": {
                "name": "youtube-content",
                "description": "YouTube transcripts to summaries",
            },
            "/github-pr-workflow": {
                "name": "github-pr-workflow",
                "description": "GitHub PR lifecycle",
            },
        },
    )

    adapter = MagicMock()
    adapter.send_skill_picker = AsyncMock(return_value=SimpleNamespace(success=True))
    runner = _make_runner(adapter=adapter)

    out = await runner._handle_skill_picker_command(_make_event("/skill youtube"))

    assert out is None
    adapter.send_skill_picker.assert_awaited_once()
    chat_id, matches = adapter.send_skill_picker.call_args.args[:2]
    assert chat_id == "12345"
    assert [m["command"] for m in matches] == ["/youtube-content"]
    assert adapter.send_skill_picker.call_args.kwargs["query"] == "youtube"


@pytest.mark.asyncio
async def test_skill_picker_falls_back_to_text_when_adapter_has_no_picker(monkeypatch):
    import agent.skill_commands as skill_commands_mod

    monkeypatch.setattr(
        skill_commands_mod,
        "get_skill_commands",
        lambda: {
            "/youtube-content": {
                "name": "youtube-content",
                "description": "YouTube transcripts to summaries",
            },
        },
    )

    runner = _make_runner(adapter=SimpleNamespace(send=AsyncMock()))
    out = await runner._handle_skill_picker_command(_make_event("/skill youtube"))

    assert "Skill matches" in out
    assert "/youtube_content" in out
    assert "YouTube transcripts" in out


@pytest.mark.asyncio
async def test_dispatcher_routes_skill_picker(monkeypatch):
    import gateway.run as gateway_run

    runner = _make_runner()
    sentinel = "skill handler reached"
    runner._handle_skill_picker_command = AsyncMock(return_value=sentinel)  # type: ignore[attr-defined]

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/skill youtube"))
    assert result == sentinel

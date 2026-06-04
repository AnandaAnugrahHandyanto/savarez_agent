"""Tests for /autopilot rollover gateway command."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource
from hermes_cli.commands import resolve_command


def _make_event(text="/autopilot rollover"):
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        user_id="67890",
        user_name="tester",
        chat_type="dm",
    )
    return MessageEvent(text=text, source=source, message_id="msg-1")


def _make_runner(history=None):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    entry = SimpleNamespace(session_id="20260525_120000_deadbeef", session_key="telegram:12345")
    store = MagicMock()
    store.get_or_create_session.return_value = entry
    store.load_transcript.return_value = [
        {"role": "user", "content": "Gate C 진행하자"},
        {"role": "assistant", "content": "staging에서 이어가겠습니다."},
    ] if history is None else history
    runner.session_store = store
    runner.adapters = {}
    cast(Any, runner)._handle_reset_command = AsyncMock(return_value="새 세션 생성 완료")
    cast(Any, runner)._handle_message = AsyncMock(return_value="resume dispatched")
    return runner


def test_autopilot_command_is_registered():
    command = resolve_command("autopilot")

    assert command is not None
    assert command.name == "autopilot"
    assert command.gateway_only is True


@pytest.mark.asyncio
async def test_autopilot_rollover_writes_handoff_resets_and_dispatches_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    runner = _make_runner()

    result = await cast(Any, runner)._handle_autopilot_command(_make_event())

    assert "Autopilot rollover staging 완료" in result
    assert "resume dispatched" in result
    latest_files = list((tmp_path / "handoffs" / "latest").glob("*.md"))
    assert latest_files, "rollover must write a latest handoff before reset"
    cast(Any, runner.session_store.load_transcript).assert_called_once_with("20260525_120000_deadbeef")
    reset_handler = cast(Any, runner)._handle_reset_command
    reset_handler.assert_awaited_once()
    reset_event = reset_handler.await_args.args[0]
    assert reset_event.text.startswith("/new")
    assert reset_event.internal is True
    message_handler = cast(Any, runner)._handle_message
    message_handler.assert_awaited_once()
    resume_event = message_handler.await_args.args[0]
    assert resume_event.text == "handoff 읽고 이어가"
    assert resume_event.source == _make_event().source
    assert resume_event.internal is True


@pytest.mark.asyncio
async def test_autopilot_rollover_uses_recent_nonempty_session_when_current_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    db = MagicMock()
    db.list_sessions_rich.return_value = [
        {
            "id": "20260526_000000_empty",
            "source": "telegram",
            "user_id": "67890",
            "message_count": 0,
        },
        {
            "id": "20260525_230000_useful",
            "source": "telegram",
            "user_id": "67890",
            "message_count": 2,
        },
    ]
    db.get_messages_as_conversation.return_value = [
        {"role": "user", "content": "Gate D 진행하자"},
        {"role": "assistant", "content": "Gate D live 반영 확인 완료했습니다."},
    ]
    runner = _make_runner(history=[])
    runner.session_store._db = db

    result = await cast(Any, runner)._handle_autopilot_command(_make_event())

    assert "Autopilot rollover staging 완료" in result
    latest_files = list((tmp_path / "handoffs" / "latest").glob("*.md"))
    assert latest_files
    summary = latest_files[0].read_text(encoding="utf-8")
    assert "handoff context recovered from previous session 20260525_230000_useful" in summary
    assert "Gate D live 반영 확인 완료했습니다." in summary
    db.list_sessions_rich.assert_called_once_with(
        source="telegram",
        limit=12,
        include_children=True,
        order_by_last_active=True,
    )
    db.get_messages_as_conversation.assert_called_once_with("20260525_230000_useful")


@pytest.mark.asyncio
async def test_autopilot_rollover_requires_rollover_subcommand(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    runner = _make_runner()

    result = await cast(Any, runner)._handle_autopilot_command(_make_event("/autopilot"))

    assert "Usage: /autopilot rollover" in result
    cast(Any, runner)._handle_reset_command.assert_not_awaited()
    cast(Any, runner)._handle_message.assert_not_awaited()

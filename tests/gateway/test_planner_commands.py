"""Tests for planner gateway commands backed by planner_store."""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.adapters = {}
    runner._voice_mode = {}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._busy_ack_ts = {}
    runner._update_prompt_pending = {}
    runner._draining = False
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key="agent:main:telegram:dm:c1:u1",
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner._session_db = None
    runner.pairing_store = MagicMock()
    runner._is_user_authorized = lambda _source: True
    return runner


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            user_id="u1",
            chat_id="c1",
            user_name="tester",
            chat_type="dm",
        ),
        message_id="m1",
    )


class TestPlannerGatewayCommands:
    @pytest.mark.asyncio
    async def test_today_command_formats_summary(self):
        runner = _make_runner()
        event = _make_event("/today")
        payload = {
            "success": True,
            "action": "today",
            "date": "2026-04-21",
            "events": [{"id": "evt_1", "title": "Созвон", "start_at": "2026-04-21T11:00:00+03:00"}],
            "reminders": [{"id": "rem_1", "text": "Позвонить", "remind_at": "2026-04-21T12:00:00+03:00"}],
            "tasks_due_today": [{"id": "task_1", "text": "Отправить отчёт", "due_time": "18:00", "priority": "high"}],
            "overdue_tasks": [{"id": "task_2", "text": "Оплатить интернет", "due_date": "2026-04-20"}],
        }

        with patch("gateway.run.planner_store_tool", return_value=json.dumps(payload)):
            result = await runner._handle_today_command(event)

        assert "План на сегодня" in result
        assert "Созвон" in result
        assert "Позвонить" in result
        assert "Отправить отчёт" in result
        assert "Оплатить интернет" in result

    @pytest.mark.asyncio
    async def test_inbox_command_formats_entries(self):
        runner = _make_runner()
        event = _make_event("/inbox")
        payload = {
            "success": True,
            "action": "inbox",
            "tasks": [
                {"id": "task_1", "text": "Купить лампу", "status": "todo"},
                {"id": "task_2", "text": "Записаться к врачу", "status": "todo"},
            ],
            "recent_notes": [{"id": "note_1", "text": "Идея про planner"}],
        }

        with patch("gateway.run.planner_store_tool", return_value=json.dumps(payload)):
            result = await runner._handle_inbox_command(event)

        assert "Инбокс" in result
        assert "Купить лампу" in result
        assert "Записаться к врачу" in result
        assert "Идея про planner" in result

    @pytest.mark.asyncio
    async def test_done_command_marks_item(self):
        runner = _make_runner()
        event = _make_event("/done task_123")
        payload = {
            "success": True,
            "action": "done",
            "item": {"id": "task_123", "text": "Купить лампу", "status": "done"},
        }

        with patch("gateway.run.planner_store_tool", return_value=json.dumps(payload)) as mocked:
            result = await runner._handle_done_command(event)

        assert "Готово" in result
        assert "task_123" in result
        assert "Купить лампу" in result
        call_args = mocked.call_args.args[0]
        assert call_args["action"] == "done"
        assert call_args["id"] == "task_123"

    @pytest.mark.asyncio
    async def test_review_command_formats_summary(self):
        runner = _make_runner()
        event = _make_event("/review")
        payload = {
            "success": True,
            "action": "review",
            "date": "2026-04-21",
            "completed_today": [{"id": "task_1", "text": "Закрыть тикет"}],
            "carryover": [{"id": "task_2", "text": "Подготовить КП"}],
        }

        with patch("gateway.run.planner_store_tool", return_value=json.dumps(payload)):
            result = await runner._handle_review_command(event)

        assert "Итоги дня" in result
        assert "Закрыть тикет" in result
        assert "Подготовить КП" in result

    @pytest.mark.asyncio
    async def test_handle_message_dispatches_today_command(self):
        runner = _make_runner()
        event = _make_event("/today")
        runner._handle_today_command = AsyncMock(return_value="ok")

        result = await runner._handle_message(event)

        assert result == "ok"
        runner._handle_today_command.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_handle_message_dispatches_inbox_command(self):
        runner = _make_runner()
        event = _make_event("/inbox")
        runner._handle_inbox_command = AsyncMock(return_value="ok")

        result = await runner._handle_message(event)

        assert result == "ok"
        runner._handle_inbox_command.assert_awaited_once_with(event)

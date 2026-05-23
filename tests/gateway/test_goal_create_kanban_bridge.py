"""Tests for the gateway /goal create Kanban bridge."""

from __future__ import annotations

import asyncio

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli import goals


class _FakeSessionEntry:
    session_id = "sid-gateway-goal-create"


class _FakeSessionStore:
    def __init__(self):
        self.entry = _FakeSessionEntry()

    def get_or_create_session(self, source):
        return self.entry

    def _generate_session_key(self, source):
        return "agent:main:discord:channel:goal-create"


def test_gateway_goal_create_routes_to_kanban_without_setting_goal(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    goals._DB_CACHE.clear()

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="token")}
    )
    runner.session_store = _FakeSessionStore()
    runner.adapters = {}
    runner._queued_events = {}

    event = MessageEvent(
        text="/goal create ship kanban bridge --assignee orchestrator",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.DISCORD,
            chat_id="chat-goal-create",
            chat_type="channel",
            user_id="user-goal-create",
        ),
        message_id="msg-goal-create",
    )

    try:
        response = asyncio.run(GatewayRunner._handle_goal_command(runner, event))

        assert "Goal task:" in response
        from hermes_cli import kanban_db as kb

        with kb.connect() as conn:
            tasks = kb.list_tasks(conn, status="triage")
        assert len(tasks) == 1
        assert tasks[0].assignee == "orchestrator"
        assert tasks[0].session_id == "sid-gateway-goal-create"
        assert goals.GoalManager("sid-gateway-goal-create").state is None
    finally:
        goals._DB_CACHE.clear()

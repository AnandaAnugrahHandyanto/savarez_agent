from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    kb.create_board("hemogry")
    return home


def make_runner():
    runner = object.__new__(GatewayRunner)
    runner.config = {
        "kanban": {
            "frontdoor_pm_routing": {
                "enabled": True,
                "board": "hemogry",
                "assignee": "hemogrypm",
                "channel_ids": ["ops-channel"],
            }
        }
    }
    runner.session_store = SimpleNamespace(
        get_or_create_session=lambda source: SimpleNamespace(session_id="sess-1")
    )
    runner._kanban_notifier_profile = "gateway-profile"
    return runner


def make_event(text: str, *, channel_id: str = "ops-channel") -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.DISCORD,
            chat_id=channel_id,
            chat_name="hemogry-ops",
            chat_type="channel",
            user_id="user-1",
            user_name="정설민",
            thread_id="thread-1",
            parent_chat_id="parent-1",
            guild_id="guild-1",
            message_id="msg-1",
        ),
    )


@pytest.mark.asyncio
async def test_frontdoor_noop_text_returns_none_and_creates_no_task(kanban_home):
    runner = make_runner()
    event = make_event("고마워. 이건 그냥 확인 답장")

    out = await GatewayRunner._maybe_handle_frontdoor_pm_routing(runner, event)

    assert out is None
    conn = kb.connect(board="hemogry")
    try:
        assert kb.list_tasks(conn) == []
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_frontdoor_user_allowlist_blocks_unlisted_user(kanban_home):
    runner = make_runner()
    config = cast(dict[str, Any], runner.config)  # test double uses a plain dict here.
    config["kanban"]["frontdoor_pm_routing"]["user_ids"] = ["trusted-user"]
    event = make_event(
        "AGENTS.md 기반으로 Hemogry Discord frontdoor routing harness를 구현하고 Kanban PM graph로 연결해줘"
    )

    out = await GatewayRunner._maybe_handle_frontdoor_pm_routing(runner, event)

    assert out is None
    conn = kb.connect(board="hemogry")
    try:
        assert kb.list_tasks(conn) == []
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_frontdoor_nontrivial_hemogry_request_creates_pm_triage_decision(kanban_home):
    runner = make_runner()
    event = make_event(
        "AGENTS.md 기반으로 Hemogry Discord frontdoor routing harness를 구현하고 Kanban PM graph로 연결해줘"
    )

    out = await GatewayRunner._maybe_handle_frontdoor_pm_routing(runner, event)

    assert out is not None
    assert "frontdoor" in out.lower()
    assert "hemogrypm" in out

    conn = kb.connect(board="hemogry")
    try:
        tasks = kb.list_tasks(conn)
        assert len(tasks) == 1
        task = tasks[0]
        assert task.assignee == "hemogrypm"
        assert task.status == "triage"
        assert "AGENTS.md" in (task.body or "")
        events = kb.list_events(conn, task.id)
        decision_events = [e for e in events if e.kind == "frontdoor_routing_decision"]
        assert decision_events
        assert decision_events[-1].payload["classification"] == "pm-kanban-routing"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_frontdoor_created_card_preserves_origin_subscription(kanban_home):
    runner = make_runner()
    event = make_event("Hemogry kanban gateway harness 구현 작업을 PM이 specialist graph로 분해해줘")

    await GatewayRunner._maybe_handle_frontdoor_pm_routing(runner, event)

    conn = kb.connect(board="hemogry")
    try:
        task = kb.list_tasks(conn)[0]
        subs = kb.list_notify_subs(conn, task.id)
        assert len(subs) == 1
        assert subs[0]["platform"] == "discord"
        assert subs[0]["chat_id"] == "ops-channel"
        assert subs[0]["thread_id"] == "thread-1"

        origin_events = [e for e in kb.list_events(conn, task.id) if e.kind == "origin_recorded"]
        assert origin_events
        origin = origin_events[-1].payload["origin"]
        assert origin["platform"] == "discord"
        assert origin["thread_id"] == "thread-1"
        assert origin["guild_id"] == "guild-1"
        assert origin["source_session_id"] == "sess-1"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_frontdoor_safety_gated_request_records_decision_without_card(kanban_home):
    runner = make_runner()
    event = make_event("production data와 credential을 읽어서 Hemogry gateway deploy까지 바로 진행해줘")

    out = await GatewayRunner._maybe_handle_frontdoor_pm_routing(runner, event)

    assert out is not None
    assert "approval" in out.lower() or "승인" in out
    conn = kb.connect(board="hemogry")
    try:
        assert kb.list_tasks(conn) == []
    finally:
        conn.close()

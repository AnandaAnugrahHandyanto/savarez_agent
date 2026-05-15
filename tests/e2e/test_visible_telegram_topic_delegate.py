"""E2E integration for visible Telegram topic delegate flow using fake adapter plumbing."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform
from gateway.session import SessionEntry, build_session_key
from tests.e2e.conftest import make_adapter, make_event, make_runner


PARENT_CHAT = "-1003933169427"
CHILD_THREAD = "14"
PARENT_THREAD = "1"


@pytest.mark.asyncio
async def test_visible_topic_delegate_spawn_and_follow_up_routes_to_same_child_thread(tmp_path):
    runner = make_runner(Platform.TELEGRAM)
    adapter = make_adapter(Platform.TELEGRAM, runner)

    runner._visible_session_registry_path = tmp_path / "visible_sessions.json"
    runner._session_model_overrides = {}
    runner._session_reasoning_overrides = {}

    def _make_entry(source, force_new=False):
        return SessionEntry(
            session_key=build_session_key(source),
            session_id=f"sess-{source.thread_id or 'root'}",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            platform=source.platform,
            chat_type=source.chat_type or "group",
            origin=source,
            display_name=source.chat_name,
        )

    runner.session_store.get_or_create_session = MagicMock(side_effect=_make_entry)

    adapter.create_visible_thread = AsyncMock(
        return_value={
            "platform": "telegram",
            "chat_id": PARENT_CHAT,
            "thread_id": CHILD_THREAD,
            "topic_name": "Delegate Smoke",
            "target": f"telegram:{PARENT_CHAT}:{CHILD_THREAD}",
        }
    )
    adapter.dispatch_synthetic_message = AsyncMock(return_value=f"agent:main:telegram:group:{PARENT_CHAT}:{CHILD_THREAD}")

    spawn_event = make_event(
        Platform.TELEGRAM,
        "/spawn-topic Delegate Smoke :: Reply exactly: VISIBLE_TOPIC_OK",
        chat_id=PARENT_CHAT,
        user_id="6605861022",
        chat_type="group",
    )
    spawn_event.source.chat_name = "Hermes Sessions General"
    spawn_event.source.thread_id = PARENT_THREAD

    adapter.send.reset_mock()
    await adapter.handle_message(spawn_event)
    await asyncio.sleep(0.3)

    assert adapter.send.called
    spawn_response = adapter.send.call_args[1].get("content") or adapter.send.call_args[0][1]
    assert "Spawned visible topic delegate" in spawn_response
    assert f"telegram:{PARENT_CHAT}:{CHILD_THREAD}" in spawn_response

    follow_event = make_event(
        Platform.TELEGRAM,
        f"/prompt-topic telegram:{PARENT_CHAT}:{CHILD_THREAD} :: focus tests first",
        chat_id=PARENT_CHAT,
        user_id="6605861022",
        chat_type="group",
    )
    follow_event.source.chat_name = "Hermes Sessions General"
    follow_event.source.thread_id = PARENT_THREAD

    adapter.send.reset_mock()
    await adapter.handle_message(follow_event)
    await asyncio.sleep(0.3)

    assert adapter.send.called
    follow_response = adapter.send.call_args[1].get("content") or adapter.send.call_args[0][1]
    assert "Queued follow-up for visible topic delegate" in follow_response
    assert f"telegram:{PARENT_CHAT}:{CHILD_THREAD}" in follow_response

    adapter.create_visible_thread.assert_awaited_once_with(PARENT_CHAT, "Delegate Smoke")

    assert adapter.dispatch_synthetic_message.await_count == 4
    first, second, third, fourth = adapter.dispatch_synthetic_message.await_args_list
    assert first.kwargs["mode"] == "send_only"
    assert second.kwargs["mode"] == "send_only"
    assert third.kwargs["mode"] == "interrupt"
    assert fourth.kwargs["mode"] == "queue"
    assert "Seed prompt from parent to this child agent" in second.kwargs["text"]
    assert "Reply exactly: VISIBLE_TOPIC_OK" in second.kwargs["text"]
    assert third.kwargs["text"] == "Reply exactly: VISIBLE_TOPIC_OK"
    assert fourth.kwargs["text"] == "focus tests first"

    for call in (first, second, third, fourth):
        assert call.kwargs["source"].thread_id == CHILD_THREAD

    runner._handle_message_with_agent.assert_not_awaited()

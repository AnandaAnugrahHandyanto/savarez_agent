import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform, PlatformConfig


@pytest.mark.asyncio
async def test_handle_text_message_applies_structured_todo_reply(tmp_path):
    from gateway.platforms.telegram import TelegramAdapter

    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text('{"version":1,"created":"2026-04-14","updated":"2026-04-14","tasks":[]}', encoding="utf-8")

    adapter = object.__new__(TelegramAdapter)
    adapter._platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="***", extra={"todo_tasks_path": str(tasks_path)})
    adapter.send = AsyncMock()
    adapter._should_process_message = lambda message, is_command=False: True
    adapter._enqueue_text_event = MagicMock()

    reply_message = SimpleNamespace(text="Cronjob Response: test\n\nReply format\nadd: ...\ndoing: ...", caption=None)
    message = SimpleNamespace(
        text="add: pick up meds\ndoing: file taxes",
        reply_to_message=reply_message,
        message_id=42,
        chat=SimpleNamespace(id=123),
        message_thread_id=225873,
    )
    update = SimpleNamespace(message=message)

    await adapter._handle_text_message(update, None)

    adapter._enqueue_text_event.assert_not_called()
    adapter.send.assert_awaited_once()
    send_kwargs = adapter.send.await_args.kwargs
    assert send_kwargs["chat_id"] == "123"
    assert send_kwargs["reply_to"] == "42"
    assert send_kwargs["metadata"] == {"thread_id": "225873"}
    assert "Updated to-do list" in send_kwargs["content"]

    saved = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert [task["title"] for task in saved["tasks"]] == ["pick up meds", "file taxes"]
    assert [task["status"] for task in saved["tasks"]] == ["todo", "doing"]


@pytest.mark.asyncio
async def test_handle_text_message_still_enqueues_normal_text():
    from gateway.platforms.telegram import TelegramAdapter
    from gateway.platforms.base import MessageType

    adapter = object.__new__(TelegramAdapter)
    adapter._platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="***")
    adapter._should_process_message = lambda message, is_command=False: True
    adapter._enqueue_text_event = MagicMock()
    adapter._clean_bot_trigger_text = lambda text: text
    adapter._build_message_event = lambda message, msg_type: SimpleNamespace(text=message.text, message_type=msg_type)
    adapter._maybe_handle_structured_todo_reply = AsyncMock(return_value=False)

    message = SimpleNamespace(text="normal message", reply_to_message=None)
    update = SimpleNamespace(message=message)

    await adapter._handle_text_message(update, None)

    adapter._maybe_handle_structured_todo_reply.assert_awaited_once_with(message)
    adapter._enqueue_text_event.assert_called_once()
    event = adapter._enqueue_text_event.call_args.args[0]
    assert event.text == "normal message"
    assert event.message_type == MessageType.TEXT

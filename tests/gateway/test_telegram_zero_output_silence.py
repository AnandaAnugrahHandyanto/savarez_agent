import asyncio
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    SendResult,
    _is_telegram_group_no_action_event,
)
from gateway.session import SessionSource


class DummyTelegramAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="***"), Platform.TELEGRAM)
        self.sent = []
        self.processing_events = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SendResult(success=True, message_id=f"msg-{len(self.sent)}")

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}

    async def _run_processing_hook(self, hook_name, event, outcome=None):
        self.processing_events.append((hook_name, outcome))

    async def _keep_typing(self, chat_id, interval=2.0, metadata=None, stop_event=None):
        await asyncio.Event().wait()


def _source(*, chat_type="group", platform=Platform.TELEGRAM):
    return SessionSource(
        platform=platform,
        user_id="user-1",
        chat_id="chat-1",
        user_name="Christine",
        chat_type=chat_type,
    )


def _event(text: str, *, chat_type="group", platform=Platform.TELEGRAM):
    return MessageEvent(
        text=text,
        source=_source(chat_type=chat_type, platform=platform),
        message_id="m1",
    )


async def _drain(adapter: DummyTelegramAdapter):
    for _ in range(50):
        if not adapter._session_tasks:
            return
        if all(task.done() for task in adapter._session_tasks.values()):
            return
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_casual_telegram_group_message_is_hard_silent_in_adapter_send_path():
    adapter = DummyTelegramAdapter()
    handler = AsyncMock(return_value="No action taken")
    adapter.set_message_handler(handler)

    event = _event("Just testing whether this casual message stays quiet.")
    await adapter.handle_message(event)
    await _drain(adapter)
    await adapter.cancel_background_tasks()

    handler.assert_not_called()
    assert adapter.sent == []
    assert adapter.processing_events == []
    sent_text = "\n".join(item["content"] for item in adapter.sent)
    assert "No action taken" not in sent_text
    assert "Staying quiet" not in sent_text
    assert "Staying quiet-ish" not in sent_text
    assert "compacting context" not in sent_text.lower()
    assert "compression" not in sent_text.lower()
    assert "auto-reset" not in sent_text.lower()


@pytest.mark.asyncio
async def test_actionable_telegram_group_message_still_responds_normally():
    adapter = DummyTelegramAdapter()
    handler = AsyncMock(return_value="Ready for review.")
    adapter.set_message_handler(handler)

    await adapter.handle_message(_event("JIMMY: please review this"))
    await _drain(adapter)
    await adapter.cancel_background_tasks()

    handler.assert_called_once()
    assert [item["content"] for item in adapter.sent] == ["Ready for review."]


@pytest.mark.asyncio
async def test_gateway_runner_suppresses_casual_group_message_before_agent_dispatch():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._run_agent = AsyncMock(side_effect=AssertionError("agent should not run"))

    result = await runner._handle_message(
        _event("Just testing whether this casual message stays quiet.")
    )

    assert result is None
    runner._run_agent.assert_not_called()


def test_classifier_preserves_dm_and_actionable_messages():
    assert _is_telegram_group_no_action_event(_event("hello", chat_type="dm")) is False
    assert _is_telegram_group_no_action_event(_event("JIMMY: please review this")) is False
    assert _is_telegram_group_no_action_event(_event("BLOCKER: branch unclear")) is False
    assert _is_telegram_group_no_action_event(_event("hello", platform=Platform.DISCORD)) is False
    assert _is_telegram_group_no_action_event(
        _event("Just testing whether this casual message stays quiet.")
    ) is True

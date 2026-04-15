import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.dingtalk import DingTalkAdapter, _IncomingHandler


@pytest.mark.asyncio
async def test_run_stream_awaits_async_sdk_start():
    adapter = DingTalkAdapter(PlatformConfig(enabled=True, extra={}))
    calls = []

    class FakeStreamClient:
        async def start(self):
            calls.append("started")
            adapter._running = False

    adapter._stream_client = FakeStreamClient()
    adapter._running = True

    await asyncio.wait_for(adapter._run_stream(), timeout=0.2)

    assert calls == ["started"]


@pytest.mark.asyncio
async def test_incoming_handler_process_awaits_adapter_message_handling():
    adapter = DingTalkAdapter(PlatformConfig(enabled=True, extra={}))
    adapter._on_message = AsyncMock()
    handler = _IncomingHandler(adapter)
    message = object()

    code, text = await handler.process(message)

    adapter._on_message.assert_awaited_once_with(message)
    assert code == 200
    assert text == "OK"


@pytest.mark.asyncio
async def test_incoming_handler_converts_callback_message_data_to_chatbot_message():
    adapter = DingTalkAdapter(PlatformConfig(enabled=True, extra={}))
    adapter._on_message = AsyncMock()
    handler = _IncomingHandler(adapter)
    callback_message = SimpleNamespace(
        data={
            "msgId": "m1",
            "conversationId": "cid-1",
            "conversationType": "1",
            "senderId": "$:LWCP_v1:$abc123openuserid",
            "senderStaffId": "03341631400920119088",
            "senderNick": "tester",
            "sessionWebhook": "https://api.dingtalk.com/v1.0/im/robot/messages",
            "msgtype": "text",
            "text": {"content": "hello"},
        }
    )

    code, text = await handler.process(callback_message)

    inbound = adapter._on_message.await_args.args[0]
    assert inbound.message_id == "m1"
    assert inbound.sender_id == "$:LWCP_v1:$abc123openuserid"
    assert inbound.sender_staff_id == "03341631400920119088"
    assert inbound.text.content == "hello"
    assert code == 200
    assert text == "OK"


@pytest.mark.asyncio
async def test_on_message_caches_session_webhook_for_multiple_dingtalk_ids():
    adapter = DingTalkAdapter(PlatformConfig(enabled=True, extra={}))
    adapter.handle_message = AsyncMock()

    message = SimpleNamespace(
        message_id="m1",
        text={"content": "hello"},
        conversation_id="cid-1",
        conversation_type="1",
        sender_id="$:LWCP_v1:$abc123openuserid",
        sender_nick="tester",
        sender_staff_id="03341631400920119088",
        session_webhook="https://oapi.dingtalk.com/robot/sendBySession?session=abc",
        conversation_title=None,
        create_at=None,
    )

    await adapter._on_message(message)

    assert adapter._session_webhooks["cid-1"] == message.session_webhook
    assert adapter._session_webhooks[message.sender_id] == message.session_webhook
    assert adapter._session_webhooks[message.sender_staff_id] == message.session_webhook
    event = adapter.handle_message.await_args.args[0]
    assert event.metadata == {"session_webhook": message.session_webhook}

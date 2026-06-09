"""Delivery reliability regression tests for gateway final replies."""

import asyncio
from types import SimpleNamespace
import unittest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, SendResult
from gateway.session import SessionSource


class _SlowFinalSendAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True), Platform.FEISHU)
        self.started = asyncio.Event()
        self.sent = asyncio.Event()
        self.metadata = None

    async def connect(self):
        return True

    async def disconnect(self):
        return None

    async def get_chat_info(self, chat_id: str):
        return {}

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None):
        return SendResult(True, message_id="om_visible")

    async def send_typing(self, chat_id: str, metadata=None):
        return None

    async def _send_with_retry(
        self,
        chat_id: str,
        content: str,
        reply_to=None,
        metadata=None,
        max_retries: int = 2,
        base_delay: float = 2.0,
    ):
        self.started.set()
        await asyncio.sleep(0.05)
        self.metadata = metadata
        self.sent.set()
        return SendResult(True, message_id="om_visible")


class TestFinalResponseDeliveryReliability(unittest.IsolatedAsyncioTestCase):
    async def test_final_response_send_drains_after_cancellation(self):
        adapter = _SlowFinalSendAdapter()

        async def handler(event):
            return "final response"

        adapter.set_message_handler(handler)
        event = MessageEvent(
            text="hello",
            source=SessionSource(
                platform=Platform.FEISHU,
                chat_id="oc_chat",
                chat_type="group",
                user_id="ou_user",
                message_id="om_inbound",
            ),
            message_id="om_inbound",
        )

        task = asyncio.create_task(adapter._process_message_background(event, "feishu:oc_chat"))
        await adapter.started.wait()
        task.cancel()
        await task

        self.assertTrue(adapter.sent.is_set())
        metadata = adapter.metadata
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertTrue(metadata["notify"])
        self.assertRegex(metadata["delivery_uuid"], r"^[0-9a-f-]{36}$")


class TestFeishuStableDeliveryUuid(unittest.IsolatedAsyncioTestCase):
    async def test_send_raw_message_uses_delivery_uuid_for_reply(self):
        from gateway.platforms.feishu import FeishuAdapter

        adapter = object.__new__(FeishuAdapter)
        captured = {}

        def build_reply_body(**kwargs):
            captured["body"] = kwargs
            return kwargs

        adapter._build_reply_message_body = build_reply_body
        adapter._build_reply_message_request = lambda message_id, request_body: SimpleNamespace(
            message_id=message_id,
            body=request_body,
        )
        adapter._client = SimpleNamespace(
            im=SimpleNamespace(
                v1=SimpleNamespace(
                    message=SimpleNamespace(
                        reply=lambda request: SimpleNamespace(success=lambda: True, data=SimpleNamespace(message_id="om_reply"))
                    )
                )
            )
        )

        await adapter._send_raw_message(
            chat_id="oc_chat",
            msg_type="text",
            payload='{"text":"hello"}',
            reply_to="om_parent",
            metadata={"delivery_uuid": "stable-delivery-id"},
        )

        self.assertEqual(captured["body"]["uuid_value"], "stable-delivery-id")

    async def test_send_raw_message_uses_delivery_uuid_for_create(self):
        from gateway.platforms.feishu import FeishuAdapter

        adapter = object.__new__(FeishuAdapter)
        captured = {}

        def build_create_body(**kwargs):
            captured["body"] = kwargs
            return kwargs

        adapter._build_create_message_body = build_create_body
        adapter._build_create_message_request = lambda receive_id_type, request_body: SimpleNamespace(
            receive_id_type=receive_id_type,
            body=request_body,
        )
        adapter._client = SimpleNamespace(
            im=SimpleNamespace(
                v1=SimpleNamespace(
                    message=SimpleNamespace(
                        create=lambda request: SimpleNamespace(success=lambda: True, data=SimpleNamespace(message_id="om_create"))
                    )
                )
            )
        )

        await adapter._send_raw_message(
            chat_id="oc_chat",
            msg_type="text",
            payload='{"text":"hello"}',
            reply_to=None,
            metadata={"delivery_uuid": "stable-create-id"},
        )

        self.assertEqual(captured["body"]["uuid_value"], "stable-create-id")

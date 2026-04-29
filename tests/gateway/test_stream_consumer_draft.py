"""Tests for draft transport in GatewayStreamConsumer."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gateway.platforms.base import BasePlatformAdapter, PlatformConfig, Platform, SendResult
from gateway.stream_consumer import GatewayStreamConsumer, StreamConsumerConfig


class StubAdapter(BasePlatformAdapter):
    """Minimal adapter for testing draft transport."""

    def __init__(self, *, draft_supported=False, draft_results=None):
        super().__init__(PlatformConfig(enabled=True, token="***"), Platform.TELEGRAM)
        self._draft_supported = draft_supported
        self._draft_results = list(draft_results or [])
        self.sent = []
        self.edited = []
        self.drafts = []
        # Hide send_draft_message if draft not supported
        if not draft_supported:
            self.send_draft_message = None

    async def connect(self):
        return True

    async def disconnect(self):
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append((chat_id, content, metadata))
        return SendResult(success=True, message_id="m1")

    async def edit_message(self, chat_id, message_id, content, *, finalize=False):
        self.edited.append((chat_id, message_id, content))
        return SendResult(success=True, message_id=message_id)

    async def send_typing(self, chat_id, metadata=None):
        return None

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}

    async def send_draft_message(self, chat_id, draft_id, content):
        if not self._draft_supported:
            raise NotImplementedError("draft not supported")
        self.drafts.append((chat_id, draft_id, content))
        if self._draft_results:
            return SendResult(success=self._draft_results.pop(0))
        return SendResult(success=True)


class TestDraftTransportResolution:
    """Verify _resolve_draft_mode logic."""

    def _make_consumer(self, adapter, transport="auto", chat_type="dm"):
        cfg = StreamConsumerConfig(transport=transport, edit_interval=0.01, buffer_threshold=1, cursor=" ▉")
        return GatewayStreamConsumer(
            adapter=adapter,
            chat_id="123",
            config=cfg,
            metadata={"chat_type": chat_type},
        )

    def test_auto_dm_with_draft_support_uses_draft(self):
        adapter = StubAdapter(draft_supported=True)
        c = self._make_consumer(adapter, transport="auto", chat_type="dm")
        assert c._draft_mode is True

    def test_auto_group_chat_uses_edit(self):
        adapter = StubAdapter(draft_supported=True)
        c = self._make_consumer(adapter, transport="auto", chat_type="group")
        assert c._draft_mode is False

    def test_auto_no_draft_support_uses_edit(self):
        adapter = StubAdapter(draft_supported=False)
        c = self._make_consumer(adapter, transport="auto", chat_type="dm")
        assert c._draft_mode is False

    def test_force_draft_with_support(self):
        adapter = StubAdapter(draft_supported=True)
        c = self._make_consumer(adapter, transport="draft", chat_type="group")
        assert c._draft_mode is True

    def test_force_draft_without_support_falls_back(self):
        adapter = StubAdapter(draft_supported=False)
        c = self._make_consumer(adapter, transport="draft", chat_type="dm")
        assert c._draft_mode is False

    def test_force_edit_disables_draft(self):
        adapter = StubAdapter(draft_supported=True)
        c = self._make_consumer(adapter, transport="edit", chat_type="dm")
        assert c._draft_mode is False

    def test_off_disables_draft(self):
        adapter = StubAdapter(draft_supported=True)
        c = self._make_consumer(adapter, transport="off", chat_type="dm")
        assert c._draft_mode is False


class TestDraftStreamingEndToEnd:
    """Verify draft transport delivers tokens via send_draft_message."""

    @pytest.mark.asyncio
    async def test_draft_transport_used_for_dm(self):
        adapter = StubAdapter(draft_supported=True)
        consumer = GatewayStreamConsumer(
            adapter=adapter,
            chat_id="123",
            config=StreamConsumerConfig(transport="auto", edit_interval=0.01, buffer_threshold=1, cursor=" ▉"),
            metadata={"chat_type": "dm"},
        )

        consumer.on_delta("Hel")
        consumer.on_delta("lo")
        consumer.finish()
        await consumer.run()

        # Draft mode should use send_draft_message, not send or edit
        assert len(adapter.drafts) >= 1
        # Final text should be "Hello" (cursor stripped)
        assert adapter.drafts[-1][2] == "Hello"
        # Consumer sends real message to dismiss draft immediately
        assert consumer.final_response_sent is True

    @pytest.mark.asyncio
    async def test_edit_transport_used_for_group(self):
        adapter = StubAdapter(draft_supported=True)
        consumer = GatewayStreamConsumer(
            adapter=adapter,
            chat_id="456",
            config=StreamConsumerConfig(transport="auto", edit_interval=0.01, buffer_threshold=1, cursor=" ▉"),
            metadata={"chat_type": "group"},
        )

        consumer.on_delta("abc")
        consumer.finish()
        await consumer.run()

        # Edit mode: no drafts, uses send
        assert adapter.drafts == []
        assert consumer.already_sent is True
        assert len(adapter.sent) == 1

    @pytest.mark.asyncio
    async def test_draft_failure_falls_back_to_edit(self):
        adapter = StubAdapter(draft_supported=True, draft_results=[False])
        consumer = GatewayStreamConsumer(
            adapter=adapter,
            chat_id="789",
            config=StreamConsumerConfig(transport="draft", edit_interval=0.01, buffer_threshold=1, cursor=" ▉"),
            metadata={"chat_type": "dm"},
        )

        consumer.on_delta("fallback")
        consumer.finish()
        await consumer.run()

        # Draft was attempted but failed (returned success=False)
        assert len(adapter.drafts) >= 1
        # Consumer still sends real message to dismiss draft (best-effort)
        assert consumer.final_response_sent is True

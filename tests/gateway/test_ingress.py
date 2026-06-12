"""Tests for shared HTTP-ingress helpers."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gateway.config import PlatformConfig
from gateway.ingress import (
    IngressEnvelope,
    build_ingress_message_event,
    schedule_ingress_envelope,
    schedule_ingress_event,
)
from gateway.platforms.webhook import WebhookAdapter


def _make_adapter() -> WebhookAdapter:
    config = PlatformConfig(enabled=True, extra={"host": "127.0.0.1", "port": 0, "routes": {}})
    return WebhookAdapter(config)


class TestBuildIngressMessageEvent:
    def test_builds_message_event_with_route_identity(self):
        adapter = _make_adapter()
        envelope = IngressEnvelope(
            text="hello from ingress",
            message_id="evt-1",
            chat_id="webhook:ci:evt-1",
            chat_name="webhook/ci",
            chat_type="webhook",
            user_id="webhook:ci",
            user_name="ci",
            raw_payload={"ref": "main"},
        )

        event = build_ingress_message_event(adapter, envelope)

        assert event.text == "hello from ingress"
        assert event.message_id == "evt-1"
        assert event.raw_message == {"ref": "main"}
        assert event.source.platform == adapter.platform
        assert event.source.chat_id == "webhook:ci:evt-1"
        assert event.source.chat_name == "webhook/ci"
        assert event.source.chat_type == "webhook"
        assert event.source.user_id == "webhook:ci"
        assert event.source.user_name == "ci"


class TestScheduleIngressEvent:
    @pytest.mark.asyncio
    async def test_tracks_background_task_until_completion(self):
        adapter = _make_adapter()
        captured = []

        async def _capture(event):
            captured.append(event)

        adapter.handle_message = _capture
        event = build_ingress_message_event(
            adapter,
            IngressEnvelope(
                text="hello",
                message_id="evt-2",
                chat_id="webhook:test:evt-2",
                raw_payload={"ok": True},
            ),
        )

        task = schedule_ingress_event(adapter, event)
        assert task in adapter._background_tasks

        await task
        await asyncio.sleep(0)

        assert captured == [event]
        assert task not in adapter._background_tasks

    @pytest.mark.asyncio
    async def test_schedule_envelope_builds_and_dispatches_event(self):
        adapter = _make_adapter()
        adapter.handle_message = AsyncMock()
        envelope = IngressEnvelope(
            text="dispatch me",
            message_id="evt-3",
            chat_id="webhook:test:evt-3",
            chat_name="webhook/test",
            user_id="webhook:test",
            user_name="test",
            raw_payload={"value": 3},
            internal=True,
        )

        task = schedule_ingress_envelope(adapter, envelope)
        await task

        adapter.handle_message.assert_awaited_once()
        await_args = adapter.handle_message.await_args
        assert await_args is not None
        dispatched_event = await_args.args[0]
        assert dispatched_event.text == "dispatch me"
        assert dispatched_event.message_id == "evt-3"
        assert dispatched_event.internal is True
        assert dispatched_event.source.chat_id == "webhook:test:evt-3"
        assert dispatched_event.raw_message == {"value": 3}

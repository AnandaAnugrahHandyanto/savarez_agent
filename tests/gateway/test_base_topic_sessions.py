"""Tests for BasePlatformAdapter topic-aware session handling."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, ProcessingOutcome, SendResult
from gateway.session import SessionSource, build_session_key


class DummyTelegramAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake-token"), Platform.TELEGRAM)
        self.sent = []
        self.typing = []
        self.processing_hooks = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        self.sent.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SendResult(success=True, message_id="1")

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        self.typing.append({"chat_id": chat_id, "metadata": metadata})
        return None

    async def get_chat_info(self, chat_id: str):
        return {"id": chat_id}

    async def on_processing_start(self, event: MessageEvent) -> None:
        self.processing_hooks.append(("start", event.message_id))

    async def on_processing_complete(self, event: MessageEvent, outcome: ProcessingOutcome) -> None:
        self.processing_hooks.append(("complete", event.message_id, outcome))


def _make_event(chat_id: str, thread_id: str, message_id: str = "1") -> MessageEvent:
    return MessageEvent(
        text="hello",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            chat_type="group",
            thread_id=thread_id,
        ),
        message_id=message_id,
    )


def _make_gateway_runner(adapter: BasePlatformAdapter):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._busy_ack_ts = {}
    runner._draining = False
    runner._restart_requested = False
    runner._update_prompt_pending = {}
    runner._is_user_authorized = lambda _source: True
    runner.hooks = SimpleNamespace(emit=AsyncMock())
    runner.config = {}
    runner.adapters = {adapter.platform: adapter}
    runner._handle_message_with_agent = AsyncMock(return_value="SHOULD_NOT_RUN")
    return runner


class TestBasePlatformTopicSessions:
    @pytest.mark.asyncio
    async def test_handle_message_does_not_interrupt_different_topic(self, monkeypatch):
        adapter = DummyTelegramAdapter()
        adapter.set_message_handler(lambda event: asyncio.sleep(0, result=None))

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        scheduled = []

        def fake_create_task(coro):
            scheduled.append(coro)
            coro.close()
            return SimpleNamespace()

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        await adapter.handle_message(_make_event("-1001", "11"))

        assert len(scheduled) == 1
        assert adapter._pending_messages == {}

    @pytest.mark.asyncio
    async def test_handle_message_interrupts_same_topic(self, monkeypatch):
        adapter = DummyTelegramAdapter()
        adapter.set_message_handler(lambda event: asyncio.sleep(0, result=None))

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        scheduled = []

        def fake_create_task(coro):
            scheduled.append(coro)
            coro.close()
            return SimpleNamespace()

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        pending_event = _make_event("-1001", "10", message_id="2")
        await adapter.handle_message(pending_event)

        assert scheduled == []
        assert adapter.get_pending_message(build_session_key(pending_event.source)) == pending_event

    @pytest.mark.asyncio
    async def test_busy_queue_command_bypasses_active_session_guard(self):
        adapter = DummyTelegramAdapter()
        adapter._busy_session_handler = AsyncMock(return_value=True)
        handled = []

        async def handler(event):
            handled.append(event.text)
            return "Queued for the next turn."

        adapter.set_message_handler(handler)

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        queue_event = MessageEvent(
            text="/queue remember this",
            source=active_event.source,
            message_id="2",
        )
        await adapter.handle_message(queue_event)

        assert handled == ["/queue remember this"]
        adapter._busy_session_handler.assert_not_awaited()
        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Queued for the next turn.",
                "reply_to": "2",
                "metadata": {"thread_id": "10"},
            }
        ]
        assert adapter._pending_messages == {}
        assert not adapter._active_sessions[build_session_key(active_event.source)].is_set()

    @pytest.mark.asyncio
    async def test_busy_queue_alias_bypasses_active_session_guard(self):
        adapter = DummyTelegramAdapter()
        adapter._busy_session_handler = AsyncMock(return_value=True)
        handled = []

        async def handler(event):
            handled.append(event.text)
            return "Queued via alias."

        adapter.set_message_handler(handler)

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        queue_event = MessageEvent(
            text="/q remember this too",
            source=active_event.source,
            message_id="3",
        )
        await adapter.handle_message(queue_event)

        assert handled == ["/q remember this too"]
        adapter._busy_session_handler.assert_not_awaited()
        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Queued via alias.",
                "reply_to": "3",
                "metadata": {"thread_id": "10"},
            }
        ]
        assert adapter._pending_messages == {}
        assert not adapter._active_sessions[build_session_key(active_event.source)].is_set()

    @pytest.mark.asyncio
    async def test_busy_model_command_bypasses_active_session_guard(self):
        adapter = DummyTelegramAdapter()
        adapter._busy_session_handler = AsyncMock(return_value=True)
        handled = []

        async def handler(event):
            handled.append(event.text)
            return "Agent is running — wait or /stop first, then switch models."

        adapter.set_message_handler(handler)

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        model_event = MessageEvent(
            text="/model gpt-5",
            source=active_event.source,
            message_id="4",
        )
        await adapter.handle_message(model_event)

        assert handled == ["/model gpt-5"]
        adapter._busy_session_handler.assert_not_awaited()
        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Agent is running — wait or /stop first, then switch models.",
                "reply_to": "4",
                "metadata": {"thread_id": "10"},
            }
        ]
        assert adapter._pending_messages == {}
        assert not adapter._active_sessions[build_session_key(active_event.source)].is_set()

    @pytest.mark.asyncio
    async def test_busy_queue_reaches_runner_busy_semantics_during_handoff(self):
        adapter = DummyTelegramAdapter()
        runner = _make_gateway_runner(adapter)
        adapter.set_message_handler(runner._handle_message)

        source = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="-1001",
            chat_type="group",
            thread_id="10",
            user_id="u1",
            user_name="tester",
        )
        session_key = build_session_key(source)
        adapter._active_sessions[session_key] = asyncio.Event()

        queue_event = MessageEvent(
            text="/queue remember this",
            source=source,
            message_id="5a",
        )
        await adapter.handle_message(queue_event)

        runner._handle_message_with_agent.assert_not_awaited()
        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Queued for the next turn.",
                "reply_to": "5a",
                "metadata": {"thread_id": "10"},
            }
        ]
        assert session_key in adapter._pending_messages
        assert adapter._pending_messages[session_key].text == "remember this"

    @pytest.mark.asyncio
    async def test_busy_queue_alias_reaches_runner_busy_semantics_during_handoff(self):
        adapter = DummyTelegramAdapter()
        runner = _make_gateway_runner(adapter)
        adapter.set_message_handler(runner._handle_message)

        source = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="-1001",
            chat_type="group",
            thread_id="10",
            user_id="u1",
            user_name="tester",
        )
        session_key = build_session_key(source)
        adapter._active_sessions[session_key] = asyncio.Event()

        queue_event = MessageEvent(
            text="/q remember this too",
            source=source,
            message_id="5",
        )
        await adapter.handle_message(queue_event)

        runner._handle_message_with_agent.assert_not_awaited()
        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Queued for the next turn.",
                "reply_to": "5",
                "metadata": {"thread_id": "10"},
            }
        ]
        assert session_key in adapter._pending_messages
        assert adapter._pending_messages[session_key].text == "remember this too"

    @pytest.mark.asyncio
    async def test_busy_model_reaches_runner_busy_semantics_during_handoff(self):
        adapter = DummyTelegramAdapter()
        runner = _make_gateway_runner(adapter)
        adapter.set_message_handler(runner._handle_message)

        source = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="-1001",
            chat_type="group",
            thread_id="10",
            user_id="u1",
            user_name="tester",
        )
        session_key = build_session_key(source)
        adapter._active_sessions[session_key] = asyncio.Event()

        model_event = MessageEvent(
            text="/model gpt-5",
            source=source,
            message_id="6",
        )
        await adapter.handle_message(model_event)

        runner._handle_message_with_agent.assert_not_awaited()
        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Agent is running — wait or /stop first, then switch models.",
                "reply_to": "6",
                "metadata": {"thread_id": "10"},
            }
        ]
        assert adapter._pending_messages == {}

    @pytest.mark.asyncio
    async def test_process_message_background_replies_in_same_topic(self):
        adapter = DummyTelegramAdapter()
        typing_calls = []

        async def handler(_event):
            await asyncio.sleep(0)
            return "ack"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            typing_calls.append({"chat_id": _chat_id, "metadata": metadata})
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "ack",
                "reply_to": "1",
                "metadata": {"thread_id": "17585"},
            }
        ]
        assert typing_calls == [
            {
                "chat_id": "-1001",
                "metadata": {"thread_id": "17585"},
            }
        ]
        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.SUCCESS),
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_marks_total_send_failure_unsuccessful(self):
        adapter = DummyTelegramAdapter()

        async def handler(_event):
            await asyncio.sleep(0)
            return "ack"

        async def failing_send(*_args, **_kwargs):
            return SendResult(success=False, error="send failed")

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter.send = failing_send
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.FAILURE),
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_marks_exception_unsuccessful(self):
        adapter = DummyTelegramAdapter()

        async def handler(_event):
            await asyncio.sleep(0)
            raise RuntimeError("boom")

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.FAILURE),
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_marks_cancellation_unsuccessful(self):
        adapter = DummyTelegramAdapter()
        release = asyncio.Event()

        async def handler(_event):
            await release.wait()
            return "ack"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        task = asyncio.create_task(adapter._process_message_background(event, build_session_key(event.source)))
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.FAILURE),
        ]

    @pytest.mark.asyncio
    async def test_cancel_background_tasks_marks_expected_cancellation_cancelled(self):
        adapter = DummyTelegramAdapter()
        release = asyncio.Event()

        async def handler(_event):
            await release.wait()
            return "ack"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter.handle_message(event)
        await asyncio.sleep(0)

        await adapter.cancel_background_tasks()

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.CANCELLED),
        ]

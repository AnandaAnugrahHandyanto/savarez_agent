"""Tests for BasePlatformAdapter eager typing.

Eager typing fires a ``send_typing`` indicator the moment ``handle_message`` is
called so the user sees a typing bubble during the agent's "thinking" phase —
before the ``_keep_typing`` loop spawned inside ``_process_message_background``
takes over.  These tests cover:

* the eager loop fires within ~100ms of webhook/handle_message entry
* the eager task is cancelled before ``_keep_typing`` starts (no double-fire)
* the eager task is cancelled on early-exit paths of ``handle_message``
* the feature defaults to disabled and respects ``eager_typing: false``
* adapters that do not override ``send_typing`` (Email / SMS / Webhook)
  silently skip the eager loop regardless of the config flag
"""

import asyncio
import time
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    Platform,
    PlatformConfig,
    SendResult,
)


class _SlowAgentAdapter(BasePlatformAdapter):
    """Adapter that overrides send_typing so eager typing is enabled."""

    def __init__(self, extra: Optional[dict] = None):
        if extra is None:
            extra = {"eager_typing": True}
        super().__init__(
            PlatformConfig(enabled=True, token="t", extra=extra),
            Platform.TELEGRAM,
        )
        self.typing_calls: list[tuple[float, str]] = []
        self.stop_typing_calls: list[str] = []
        self._start_time = time.monotonic()

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="m1")

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        self.typing_calls.append((time.monotonic() - self._start_time, chat_id))

    async def stop_typing(self, chat_id: str) -> None:
        self.stop_typing_calls.append(chat_id)

    async def get_chat_info(self, chat_id):
        return {"id": chat_id, "type": "dm"}


class _NoTypingAdapter(BasePlatformAdapter):
    """Adapter that does NOT override send_typing — eager typing must no-op."""

    def __init__(self):
        super().__init__(
            PlatformConfig(enabled=True, token="t", extra={"eager_typing": True}),
            Platform.EMAIL,
        )
        self.send_typing_called = False

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="m1")

    async def get_chat_info(self, chat_id):
        return {"id": chat_id, "type": "dm"}


def _make_event(chat_id: str = "user-1", text: str = "hi") -> MessageEvent:
    adapter = _SlowAgentAdapter()
    source = adapter.build_source(chat_id=chat_id, chat_type="dm", user_id=chat_id)
    return MessageEvent(text=text, message_type=MessageType.TEXT, source=source)


class TestEagerTypingFiresImmediately:
    @pytest.mark.asyncio
    async def test_send_typing_called_within_100ms_of_handle_message(self):
        """The whole point of eager typing — the user must see a bubble fast,
        before the agent has done any meaningful work."""
        adapter = _SlowAgentAdapter()

        async def slow_handler(event):
            await asyncio.sleep(2.0)
            return "done"

        adapter.set_message_handler(slow_handler)

        event = _make_event()
        task = asyncio.create_task(adapter.handle_message(event))
        try:
            await asyncio.sleep(0.1)
            assert adapter.typing_calls, (
                "expected send_typing to fire within 100ms of handle_message entry"
            )
            first_call_at = adapter.typing_calls[0][0]
            assert first_call_at < 0.15, (
                f"first send_typing fired at {first_call_at*1000:.1f}ms — too slow"
            )
            assert adapter.typing_calls[0][1] == "user-1"
        finally:
            await adapter.cancel_background_tasks()
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    @pytest.mark.asyncio
    async def test_eager_task_cancelled_before_keep_typing_starts(self):
        """The eager task must be cancelled inside _process_message_background
        before _keep_typing kicks in, so the two never double-fire."""
        adapter = _SlowAgentAdapter()
        keep_typing_started = asyncio.Event()
        eager_task_at_kt_start: list[Optional[asyncio.Task]] = []

        original_keep_typing = adapter._keep_typing

        async def tracking_keep_typing(*args, **kwargs):
            eager_task_at_kt_start.append(
                adapter._eager_typing_tasks.get(event.source.chat_id)
            )
            keep_typing_started.set()
            return await original_keep_typing(*args, **kwargs)

        adapter._keep_typing = tracking_keep_typing

        async def quick_handler(evt):
            await asyncio.sleep(0.3)
            return "done"

        adapter.set_message_handler(quick_handler)
        event = _make_event(chat_id="kt-test")
        task = asyncio.create_task(adapter.handle_message(event))
        try:
            await asyncio.wait_for(keep_typing_started.wait(), timeout=2.0)
            assert eager_task_at_kt_start[0] is None, (
                "eager typing task was still in _eager_typing_tasks dict when "
                "_keep_typing started — they would double-fire"
            )
        finally:
            await adapter.cancel_background_tasks()
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass


class TestEagerTypingConfig:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        """Without explicit opt-in the eager loop must not be created —
        backward-compat: deployments that don't set eager_typing see the
        existing _keep_typing behavior only."""
        adapter = _SlowAgentAdapter(extra={})
        assert adapter._eager_typing_enabled() is False
        result = await adapter._start_eager_typing("chat-default")
        assert result is None, (
            "_start_eager_typing returned a task despite eager_typing being "
            "absent from config.extra — default must be disabled"
        )
        assert "chat-default" not in adapter._eager_typing_tasks

    @pytest.mark.asyncio
    async def test_explicit_false_disables(self):
        adapter = _SlowAgentAdapter(extra={"eager_typing": False})
        assert adapter._eager_typing_enabled() is False
        result = await adapter._start_eager_typing("chat-off")
        assert result is None
        assert "chat-off" not in adapter._eager_typing_tasks

    @pytest.mark.asyncio
    async def test_no_op_when_send_typing_not_overridden(self):
        """Email / SMS / Webhook don't implement send_typing — eager typing
        must silently no-op even when eager_typing: true is set."""
        adapter = _NoTypingAdapter()
        assert adapter._eager_typing_enabled() is False
        result = await adapter._start_eager_typing("chat-1")
        assert result is None, (
            "eager typing returned a task on an adapter without send_typing — "
            "would log spam against a no-op send_typing"
        )

    @pytest.mark.asyncio
    async def test_interval_override_respected(self):
        adapter = _SlowAgentAdapter(
            extra={"eager_typing": True, "eager_typing_interval": 2.5}
        )
        assert adapter._eager_typing_interval() == 2.5

    @pytest.mark.asyncio
    async def test_max_iterations_override_respected(self):
        adapter = _SlowAgentAdapter(
            extra={"eager_typing": True, "eager_typing_max_iterations": 3}
        )
        assert adapter._eager_typing_max_iterations() == 3

    @pytest.mark.asyncio
    async def test_invalid_interval_falls_back_to_default(self):
        adapter = _SlowAgentAdapter(
            extra={"eager_typing": True, "eager_typing_interval": "not-a-number"}
        )
        assert adapter._eager_typing_interval() == BasePlatformAdapter.EAGER_TYPING_DEFAULT_INTERVAL


class TestEagerTypingLifecycle:
    @pytest.mark.asyncio
    async def test_idempotent_start_returns_existing_task(self):
        """An adapter that fires _start_eager_typing both from its webhook
        handler AND from handle_message (the canonical BlueBubbles pattern)
        must not spawn two competing tasks."""
        adapter = _SlowAgentAdapter()
        first = await adapter._start_eager_typing("chat-A")
        second = await adapter._start_eager_typing("chat-A")
        try:
            assert first is not None
            assert second is first, (
                "second _start_eager_typing call spawned a new task instead "
                "of returning the in-flight one — would race itself"
            )
        finally:
            await adapter._cancel_eager_typing("chat-A")

    @pytest.mark.asyncio
    async def test_cancel_eager_typing_clears_entry(self):
        adapter = _SlowAgentAdapter()
        task = await adapter._start_eager_typing("chat-B")
        assert task is not None
        assert "chat-B" in adapter._eager_typing_tasks
        await adapter._cancel_eager_typing("chat-B")
        assert "chat-B" not in adapter._eager_typing_tasks

    @pytest.mark.asyncio
    async def test_cancel_eager_typing_no_op_for_unknown_chat(self):
        adapter = _SlowAgentAdapter()
        await adapter._cancel_eager_typing("never-started")

    @pytest.mark.asyncio
    async def test_max_iterations_bounds_runaway_loop(self):
        """The eager loop must stop on its own after max_iterations, so a
        crash in the handler can't leave it running forever."""
        adapter = _SlowAgentAdapter(
            extra={
                "eager_typing": True,
                "eager_typing_interval": 0.05,
                "eager_typing_max_iterations": 3,
            }
        )
        task = await adapter._start_eager_typing("chat-C")
        assert task is not None
        await asyncio.wait_for(task, timeout=1.0)
        assert task.done()
        assert len(adapter.typing_calls) <= 3, (
            f"expected at most 3 typing calls within max_iterations, "
            f"got {len(adapter.typing_calls)}"
        )

    @pytest.mark.asyncio
    async def test_paused_chat_skips_eager_typing(self):
        adapter = _SlowAgentAdapter(
            extra={
                "eager_typing": True,
                "eager_typing_interval": 0.05,
                "eager_typing_max_iterations": 3,
            }
        )
        adapter._typing_paused.add("paused-chat")
        task = await adapter._start_eager_typing("paused-chat")
        assert task is not None
        await asyncio.wait_for(task, timeout=1.0)
        assert adapter.typing_calls == [], (
            f"eager send_typing fired on a paused chat: {adapter.typing_calls}"
        )

    @pytest.mark.asyncio
    async def test_handle_message_early_exit_cancels_eager(self):
        """If handle_message takes an early-exit path (no background task
        spawned), the finally block must cancel the eager task — otherwise
        it lingers for ~max_iterations * interval seconds firing useless
        send_typing calls."""
        adapter = _SlowAgentAdapter()

        async def handler(evt):
            return ""

        adapter.set_message_handler(handler)

        async def busy_handler(evt, session_key):
            return True

        adapter._busy_session_handler = busy_handler
        session_key = "agent:main:telegram:dm:early-exit-test"
        adapter._active_sessions[session_key] = asyncio.Event()

        event = MessageEvent(
            text="hi",
            message_type=MessageType.TEXT,
            source=adapter.build_source(
                chat_id="early-exit-test", chat_type="dm", user_id="early-exit-test"
            ),
        )
        from gateway.platforms.base import build_session_key as _bsk
        computed_key = _bsk(event.source, group_sessions_per_user=True, thread_sessions_per_user=False)
        adapter._active_sessions[computed_key] = asyncio.Event()

        await adapter.handle_message(event)
        assert "early-exit-test" not in adapter._eager_typing_tasks, (
            "eager task was not cancelled on the busy-session early-exit path"
        )

    @pytest.mark.asyncio
    async def test_cancel_calls_stop_typing_by_default(self):
        """Regression guard for the #6016 class of bug: every cancel path
        except the explicit handoff must call stop_typing so platforms
        with persistent typing state (Matrix's 30s set_typing(timeout),
        Discord's self-refreshing internal loop) don't leak a stale
        bubble.  Asserts that _cancel_eager_typing fires stop_typing
        when suppress_stop is left at its default (False)."""
        adapter = _SlowAgentAdapter(
            extra={
                "eager_typing": True,
                "eager_typing_interval": 5.0,
                "eager_typing_max_iterations": 12,
            }
        )
        task = await adapter._start_eager_typing("chat-stop")
        assert task is not None
        await asyncio.sleep(0.05)
        adapter.stop_typing_calls.clear()
        await adapter._cancel_eager_typing("chat-stop")
        assert "chat-stop" in adapter.stop_typing_calls, (
            "stop_typing was NOT called after _cancel_eager_typing — "
            "platforms with persistent typing state (Matrix, Discord) "
            "would leak a stale bubble"
        )

    @pytest.mark.asyncio
    async def test_handoff_cancel_suppresses_stop_typing(self):
        """The handoff site in _process_message_background passes
        suppress_stop=True because _keep_typing is about to re-fire
        send_typing immediately, and a stop_typing in between would
        cause a visible bubble flicker on Discord and Matrix.  This
        test pins that contract so future refactors don't accidentally
        drop the flag and reintroduce flicker."""
        adapter = _SlowAgentAdapter(
            extra={
                "eager_typing": True,
                "eager_typing_interval": 5.0,
                "eager_typing_max_iterations": 12,
            }
        )
        task = await adapter._start_eager_typing("chat-handoff")
        assert task is not None
        await asyncio.sleep(0.05)
        adapter.stop_typing_calls.clear()
        await adapter._cancel_eager_typing("chat-handoff", suppress_stop=True)
        assert adapter.stop_typing_calls == [], (
            f"stop_typing was called despite suppress_stop=True — "
            f"would cause typing-bubble flicker on Discord/Matrix at "
            f"the eager→_keep_typing handoff. calls={adapter.stop_typing_calls}"
        )

    @pytest.mark.asyncio
    async def test_handle_message_early_exit_calls_stop_typing(self):
        """End-to-end: when handle_message takes the busy-session early
        exit path, the final stop_typing must reach the adapter so
        Matrix's set_typing(timeout=30000) bubble doesn't linger for
        up to 30 seconds after the user's message is rejected."""
        adapter = _SlowAgentAdapter(
            extra={
                "eager_typing": True,
                "eager_typing_interval": 5.0,
                "eager_typing_max_iterations": 12,
            }
        )

        async def handler(evt):
            return ""

        adapter.set_message_handler(handler)

        async def busy_handler(evt, session_key):
            return True

        adapter._busy_session_handler = busy_handler

        event = MessageEvent(
            text="hi",
            message_type=MessageType.TEXT,
            source=adapter.build_source(
                chat_id="stop-on-busy", chat_type="dm", user_id="stop-on-busy"
            ),
        )
        from gateway.platforms.base import build_session_key as _bsk
        computed_key = _bsk(
            event.source,
            group_sessions_per_user=True,
            thread_sessions_per_user=False,
        )
        adapter._active_sessions[computed_key] = asyncio.Event()
        adapter.stop_typing_calls.clear()

        await adapter.handle_message(event)
        assert "stop-on-busy" in adapter.stop_typing_calls, (
            f"stop_typing was NOT called on the busy-session early-exit "
            f"path — eager bubble would linger. "
            f"stop_typing_calls={adapter.stop_typing_calls}"
        )

    @pytest.mark.asyncio
    async def test_loop_natural_exit_calls_stop_typing(self):
        """When the eager loop hits max_iterations and exits naturally
        (no explicit cancel — e.g. handle_message crashed before the
        finally block reached _cancel_eager_typing), the loop's own
        finally must still call stop_typing.  Without this, Discord's
        self-refreshing internal typing task would keep pinging forever."""
        adapter = _SlowAgentAdapter(
            extra={
                "eager_typing": True,
                "eager_typing_interval": 0.05,
                "eager_typing_max_iterations": 2,
            }
        )
        task = await adapter._start_eager_typing("chat-natural")
        assert task is not None
        await asyncio.wait_for(task, timeout=1.0)
        assert "chat-natural" in adapter.stop_typing_calls, (
            f"stop_typing was NOT called when the eager loop exited "
            f"on max_iterations — Discord's internal refresh loop "
            f"would keep pinging forever. "
            f"stop_typing_calls={adapter.stop_typing_calls}"
        )

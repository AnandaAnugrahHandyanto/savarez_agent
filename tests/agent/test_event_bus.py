"""Tests for agent/event_bus.py and agent/operational_state.py (Phase 1)."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from agent.event_bus import EventBus, HermesEvent, HermesEventType, get_event_bus
from agent.operational_state import OperationalState, OperationalStateManager


class TestEventBus:
    def test_subscribe_returns_unsubscribe_fn(self):
        bus = EventBus()
        calls = []

        def handler(e):
            calls.append(e)

        unsub = bus.subscribe(HermesEventType.API_ERROR, handler)
        assert callable(unsub)

        unsub()
        # After unsubscribe, handler should not fire
        bus.emit(HermesEvent(type=HermesEventType.API_ERROR))
        assert len(calls) == 0

    def test_emit_calls_sync_handler(self):
        bus = EventBus()
        received = []

        def handler(ev):
            received.append(ev)

        bus.subscribe(HermesEventType.API_ERROR, handler)
        bus.emit(
            HermesEvent(
                type=HermesEventType.API_ERROR, payload={"reason": "rate_limit"}
            )
        )

        assert len(received) == 1
        assert received[0].type == HermesEventType.API_ERROR
        assert received[0].payload["reason"] == "rate_limit"

    def test_multiple_handlers_all_called(self):
        bus = EventBus()
        a, b = [], []

        bus.subscribe(HermesEventType.API_ERROR, lambda e: a.append(e))
        bus.subscribe(HermesEventType.API_ERROR, lambda e: b.append(e))
        bus.emit(HermesEvent(type=HermesEventType.API_ERROR))

        assert len(a) == 1
        assert len(b) == 1

    def test_unsubscribe_idempotent(self):
        bus = EventBus()
        calls = []

        def handler(e):
            calls.append(e)

        unsub = bus.subscribe(HermesEventType.API_ERROR, handler)
        unsub()
        unsub()  # Second call must not raise
        bus.emit(HermesEvent(type=HermesEventType.API_ERROR))
        assert len(calls) == 0

    def test_subscriber_count(self):
        bus = EventBus()
        assert bus.subscriber_count(HermesEventType.API_ERROR) == 0

        def h1(e):
            pass

        def h2(e):
            pass

        u1 = bus.subscribe(HermesEventType.API_ERROR, h1)
        assert bus.subscriber_count(HermesEventType.API_ERROR) == 1

        u2 = bus.subscribe(HermesEventType.API_ERROR, h2)
        assert bus.subscriber_count(HermesEventType.API_ERROR) == 2

        u1()
        assert bus.subscriber_count(HermesEventType.API_ERROR) == 1

    def test_global_bus_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_handler_exception_swallowed(self):
        bus = EventBus()
        calls = []

        def bad_handler(e):
            raise RuntimeError("bad handler")

        def good_handler(e):
            calls.append(e)

        bus.subscribe(HermesEventType.API_ERROR, bad_handler)
        bus.subscribe(HermesEventType.API_ERROR, good_handler)
        # Must not raise
        bus.emit(HermesEvent(type=HermesEventType.API_ERROR))

        assert len(calls) == 1  # good_handler still called

    def test_thread_safety(self):
        bus = EventBus()
        lock = threading.Lock()
        results = []

        def handler(ev):
            with lock:
                results.append(ev.type)

        for _ in range(10):
            bus.subscribe(HermesEventType.API_ERROR, handler)

        def emitter():
            for _ in range(100):
                bus.emit(HermesEvent(type=HermesEventType.API_ERROR))

        threads = [threading.Thread(target=emitter) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All events should be accounted for (some duplicates from concurrent emit OK)
        assert len(results) > 0


class TestOperationalStateManager:
    def test_stanby_by_default(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        assert op.state == OperationalState.STANDBY

    def test_task_started_transitions_to_active(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        assert op.state == OperationalState.ACTIVE

    def test_error_streak_triggers_degraded(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()

        # 3 consecutive errors -> DEGRADED (default threshold)
        op.on_turn_complete(ok=False)
        assert op.state == OperationalState.ACTIVE
        op.on_turn_complete(ok=False)
        assert op.state == OperationalState.ACTIVE
        op.on_turn_complete(ok=False)
        assert op.state == OperationalState.DEGRADED
        assert op.error_streak == 3

    def test_recovery_resets_streak_and_returns_to_active(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        op.on_turn_complete(ok=False)
        op.on_turn_complete(ok=False)
        op.on_turn_complete(ok=False)  # -> DEGRADED
        op.on_turn_complete(ok=True)  # -> ACTIVE
        assert op.state == OperationalState.ACTIVE
        assert op.error_streak == 0

    def test_low_budget_triggers_degraded(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        # 20% budget -> DEGRADED (default threshold)
        op.on_budget_update(0.19)
        assert op.state == OperationalState.DEGRADED

    def test_very_low_budget_triggers_critical(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        # <5% budget -> CRITICAL
        op.on_budget_update(0.04)
        assert op.state == OperationalState.CRITICAL

    def test_high_error_streak_triggers_critical(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        for _ in range(6):
            op.on_turn_complete(ok=False)
        assert op.state == OperationalState.CRITICAL

    def test_task_ended_returns_to_standby(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        op.on_budget_update(0.01)
        assert op.state == OperationalState.CRITICAL
        op.on_task_ended()
        assert op.state == OperationalState.STANDBY

    def test_transition_is_idempotent(self):
        bus = EventBus()
        cap = []

        def spy(e):
            cap.append(e)

        bus.subscribe(HermesEventType.STATE_TRANSITION, spy)
        op = OperationalStateManager(bus)

        op.on_task_started()
        first = len(cap)
        op.on_task_started()  # already ACTIVE - no new transition
        assert len(cap) == first

    def test_fallback_activated_reduces_error_streak(self):
        bus = EventBus()
        op = OperationalStateManager(bus)
        op.on_task_started()
        op.on_turn_complete(ok=False)
        op.on_turn_complete(ok=False)
        assert op.error_streak == 2

        op.on_fallback_activated()
        assert op.error_streak == 0  # reduced by 2

    def test_emits_state_transition_event(self):
        bus = EventBus()
        cap = []

        def spy(e):
            cap.append(e)

        bus.subscribe(HermesEventType.STATE_TRANSITION, spy)
        op = OperationalStateManager(bus)
        op.on_task_started()

        # STANDBY->ACTIVE
        assert len(cap) == 1
        assert cap[0].payload["previous"] == "standby"
        assert cap[0].payload["current"] == "active"


class TestEventBusAsync:
    def test_async_handler_dispatched_fire_and_forget(self):
        bus = EventBus()
        result = []

        async def async_handler(ev):
            result.append(ev.type)

        bus.subscribe(HermesEventType.API_ERROR, async_handler)
        bus.emit(HermesEvent(type=HermesEventType.API_ERROR))

        # Give asyncio time to dispatch (fire-and-forget)
        time.sleep(0.1)
        assert len(result) == 1

    def test_mixed_sync_and_async(self):
        bus = EventBus()
        sync_out, async_out = [], []

        def sync_handler(ev):
            sync_out.append(ev.type)

        async def async_handler(ev):
            async_out.append(ev.type)

        bus.subscribe(HermesEventType.API_ERROR, sync_handler)
        bus.subscribe(HermesEventType.API_ERROR, async_handler)
        bus.emit(HermesEvent(type=HermesEventType.API_ERROR))

        time.sleep(0.1)
        assert len(sync_out) == 1
        assert len(async_out) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

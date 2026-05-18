"""Unit tests for the Honcho circuit breaker."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

import pytest

from plugins.memory.honcho.circuit_breaker import (
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
    HonchoCircuitBreaker,
    get_breaker,
    reset_breaker,
)


class _FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def advance(self, dt: float) -> None:
        self.t += dt

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> _FakeClock:
    return _FakeClock()


@pytest.fixture
def breaker(clock: _FakeClock) -> HonchoCircuitBreaker:
    wall = _FakeClock()
    wall.t = 1_700_000_000.0
    return HonchoCircuitBreaker(
        failure_threshold=3,
        cooldown_s=60.0,
        snapshot_path=None,
        now=clock,
        wall_now=wall,
    )


class TestBreakerStateTransitions:
    def test_starts_closed(self, breaker: HonchoCircuitBreaker) -> None:
        assert breaker.state == STATE_CLOSED
        assert breaker.allow() is True
        assert breaker.consecutive_failures == 0

    def test_failures_below_threshold_stay_closed(
        self, breaker: HonchoCircuitBreaker
    ) -> None:
        assert breaker.record_failure(ConnectionRefusedError("nope")) is False
        assert breaker.record_failure(TimeoutError("slow")) is False
        assert breaker.state == STATE_CLOSED
        assert breaker.allow() is True
        assert breaker.consecutive_failures == 2

    def test_threshold_failures_open_breaker(
        self, breaker: HonchoCircuitBreaker
    ) -> None:
        for i in range(2):
            assert breaker.record_failure(ConnectionRefusedError(f"fail-{i}")) is False
        # Third consecutive failure trips the breaker.
        assert breaker.record_failure(ConnectionRefusedError("fail-3")) is True
        assert breaker.state == STATE_OPEN
        assert breaker.allow() is False

    def test_success_resets_failure_counter(
        self, breaker: HonchoCircuitBreaker
    ) -> None:
        breaker.record_failure(TimeoutError("a"))
        breaker.record_failure(TimeoutError("b"))
        breaker.record_success()
        assert breaker.consecutive_failures == 0
        assert breaker.state == STATE_CLOSED
        # Need a fresh 3-failure run to trip.
        breaker.record_failure(TimeoutError("c"))
        breaker.record_failure(TimeoutError("d"))
        assert breaker.state == STATE_CLOSED

    def test_cooldown_elapsed_transitions_to_half_open(
        self, breaker: HonchoCircuitBreaker, clock: _FakeClock
    ) -> None:
        for _ in range(3):
            breaker.record_failure(ConnectionRefusedError("x"))
        assert breaker.state == STATE_OPEN
        # Within cooldown: still blocked.
        clock.advance(59.0)
        assert breaker.allow() is False
        assert breaker.state == STATE_OPEN
        # After cooldown: probe permitted.
        clock.advance(2.0)
        assert breaker.allow() is True
        assert breaker.state == STATE_HALF_OPEN
        # No more probes while half-open.
        assert breaker.allow() is False

    def test_half_open_success_closes(
        self, breaker: HonchoCircuitBreaker, clock: _FakeClock
    ) -> None:
        for _ in range(3):
            breaker.record_failure(TimeoutError("x"))
        clock.advance(61.0)
        breaker.allow()  # transition to half-open
        assert breaker.state == STATE_HALF_OPEN
        closed = breaker.record_success()
        assert closed is True
        assert breaker.state == STATE_CLOSED
        assert breaker.allow() is True

    def test_half_open_failure_reopens_with_fresh_cooldown(
        self, breaker: HonchoCircuitBreaker, clock: _FakeClock
    ) -> None:
        for _ in range(3):
            breaker.record_failure(TimeoutError("x"))
        clock.advance(61.0)
        breaker.allow()  # half-open
        assert breaker.state == STATE_HALF_OPEN
        reopened = breaker.record_failure(ConnectionRefusedError("still down"))
        assert reopened is True
        assert breaker.state == STATE_OPEN
        # Cooldown clock restarted: 30s later, still blocked.
        clock.advance(30.0)
        assert breaker.allow() is False


class TestBreakerLogging:
    def test_single_warn_on_open_transition(
        self,
        breaker: HonchoCircuitBreaker,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING, logger="plugins.memory.honcho.circuit_breaker")
        for i in range(3):
            breaker.record_failure(ConnectionRefusedError(f"e{i}"))
        # Subsequent rejected calls should NOT log new WARNs.
        for _ in range(10):
            assert breaker.allow() is False
        warns = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warns) == 1, [r.getMessage() for r in warns]
        assert "opening after 3 consecutive failures" in warns[0].getMessage()

    def test_info_on_close_transition(
        self,
        breaker: HonchoCircuitBreaker,
        clock: _FakeClock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO, logger="plugins.memory.honcho.circuit_breaker")
        for _ in range(3):
            breaker.record_failure(TimeoutError("x"))
        clock.advance(61.0)
        breaker.allow()  # half-open
        caplog.clear()
        breaker.record_success()
        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(infos) == 1
        assert "closing" in infos[0].getMessage()


class TestBreakerSnapshot:
    def test_snapshot_file_written_on_transition(
        self, tmp_path: Path, clock: _FakeClock
    ) -> None:
        snap = tmp_path / "honcho-circuit.json"
        b = HonchoCircuitBreaker(
            failure_threshold=2,
            cooldown_s=10.0,
            snapshot_path=snap,
            now=clock,
        )
        b.record_failure(ConnectionRefusedError("boom"))
        b.record_failure(ConnectionRefusedError("boom"))
        assert snap.exists()
        data = json.loads(snap.read_text())
        assert data["state"] == STATE_OPEN
        assert data["consecutive_failures"] == 2
        assert data["cooldown_s"] == 10.0
        assert "ConnectionRefusedError" in data["last_error"]

    def test_snapshot_survives_unwritable_dir(self, clock: _FakeClock) -> None:
        # Path under a file (cannot create dir) — must not raise.
        bad = Path("/dev/null/honcho-circuit.json")
        b = HonchoCircuitBreaker(
            failure_threshold=1,
            cooldown_s=1.0,
            snapshot_path=bad,
            now=clock,
        )
        b.record_failure(TimeoutError("x"))  # should not raise


class TestBreakerSingleton:
    def setup_method(self) -> None:
        reset_breaker()

    def teardown_method(self) -> None:
        reset_breaker()

    def test_get_breaker_returns_same_instance(self) -> None:
        b1 = get_breaker()
        b2 = get_breaker()
        assert b1 is b2

    def test_reset_breaker_clears_singleton(self) -> None:
        b1 = get_breaker()
        reset_breaker()
        b2 = get_breaker()
        assert b1 is not b2


class TestBreakerThreadSafety:
    def test_concurrent_failures_open_breaker_once(
        self, breaker: HonchoCircuitBreaker
    ) -> None:
        # 20 threads each record a failure. After 3, breaker opens; the rest
        # increment the counter but cannot re-trigger the open transition.
        transitions: list[bool] = []
        lock = threading.Lock()

        def hammer() -> None:
            opened = breaker.record_failure(ConnectionRefusedError("x"))
            with lock:
                transitions.append(opened)

        threads = [threading.Thread(target=hammer) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(transitions) == 1
        assert breaker.state == STATE_OPEN

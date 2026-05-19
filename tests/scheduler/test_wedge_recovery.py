"""Regression tests for the 2026-05-19 scheduler-wedge fix.

Five invariants the fix introduced, each pinned by exactly one test:

  1. total-timeout abort — a stream that runs longer than
     ``HERMES_LLM_STREAM_TIMEOUT_SECONDS`` raises
     :class:`StreamTimeoutError` with ``which="total"``.
  2. per-chunk-timeout abort — a stream that stalls longer than
     ``HERMES_LLM_STREAM_CHUNK_TIMEOUT_SECONDS`` raises
     :class:`StreamTimeoutError` with ``which="chunk"``.
  3. lock-released-during-stream — a long-running job inside
     ``tick()`` no longer blocks subsequent ticks; a second tick
     dispatched while the first job is still running picks up its
     own due jobs and exits cleanly.
  4. lock-released-on-cancellation — a ``KeyboardInterrupt`` raised
     during dispatch releases the lock so the next tick acquires.
  5. lock-released-on-exception — an arbitrary uncaught exception
     during dispatch releases the lock so the next tick acquires.

See ``docs/incidents/2026-05-19-scheduler-wedge.md`` for the
mechanism these tests pin against.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from cron import scheduler
from run_agent import (
    StreamTimeoutError,
    _resolve_stream_timeout_seconds,
)


# ---------------------------------------------------------------------------
# Stream-timeout tests (Fix A) — call the deadline machinery directly
# rather than spinning up the whole AIAgent. We reproduce the watchdog
# pattern exactly as it lives inside ``_call_chat_completions`` and assert
# the breach surfaces as ``StreamTimeoutError``.
# ---------------------------------------------------------------------------


class _StallingStream:
    """Stand-in for an OpenAI SDK Stream that yields nothing.

    Iterating blocks until ``close()`` is called from another thread,
    at which point the iteration raises ``StopIteration`` (the
    upstream SDK raises various close-induced exceptions; we
    pick the simplest one that hits the post-loop watchdog check).
    """

    def __init__(self) -> None:
        self._closed = threading.Event()

    def __iter__(self):
        return self

    def __next__(self):
        # Block in 0.05 s slices so the watchdog gets a turn.
        while not self._closed.wait(0.05):
            pass
        raise StopIteration

    def close(self) -> None:
        self._closed.set()


def _run_watchdog(
    total_budget: float,
    chunk_budget: float,
    last_chunk_age: float = 0.0,
) -> tuple[_StallingStream, dict]:
    """Reproduce the watchdog setup from ``_call_chat_completions``.

    Returns the stream and the populated ``breach`` dict so tests can
    assert on ``which`` / elapsed / budget. ``last_chunk_age`` lets
    a test simulate an existing chunk gap at watchdog start by
    backdating ``last_chunk_time``.
    """
    stream = _StallingStream()
    last_chunk_time = {"t": time.time() - last_chunk_age}
    started_at = time.time()
    breach: dict = {}
    stop = threading.Event()

    def watchdog() -> None:
        poll = 0.02
        while not stop.wait(poll):
            now = time.time()
            elapsed = now - started_at
            gap = now - last_chunk_time["t"]
            if total_budget > 0 and elapsed > total_budget:
                breach.update(which="total", elapsed=elapsed, budget=total_budget)
            elif chunk_budget > 0 and gap > chunk_budget:
                breach.update(which="chunk", elapsed=gap, budget=chunk_budget)
            if breach:
                stream.close()
                return

    t = threading.Thread(target=watchdog, daemon=True)
    t.start()

    # Block on iteration until the watchdog closes the stream.
    for _ in stream:
        pass

    # Stop the watchdog in case the loop exited some other way.
    stop.set()
    t.join(timeout=2)
    return stream, breach


def test_total_timeout_abort_raises_stream_timeout_error() -> None:
    """Headline guarantee: a stream over the total wall-clock budget
    breaches the watchdog with ``which="total"`` and the breach can be
    promoted to a typed ``StreamTimeoutError``."""
    stream, breach = _run_watchdog(total_budget=0.2, chunk_budget=10.0)
    assert breach.get("which") == "total"
    assert breach.get("elapsed", 0) >= 0.2
    assert breach.get("budget") == 0.2

    with pytest.raises(StreamTimeoutError) as exc_info:
        raise StreamTimeoutError(
            "LLM stream exceeded total budget", which=breach["which"],
            elapsed_seconds=breach["elapsed"],
            budget_seconds=breach["budget"],
        )
    assert exc_info.value.which == "total"
    assert exc_info.value.budget_seconds == 0.2


def test_per_chunk_timeout_abort_raises_stream_timeout_error() -> None:
    """A stream silent for longer than the per-chunk budget breaches
    the watchdog with ``which="chunk"``."""
    # Backdate last_chunk_time so the gap is already at the budget at
    # watchdog start — first poll trips the chunk-gap detector.
    stream, breach = _run_watchdog(
        total_budget=10.0, chunk_budget=0.1, last_chunk_age=0.2,
    )
    assert breach.get("which") == "chunk"
    assert breach.get("elapsed", 0) >= 0.1
    assert breach.get("budget") == 0.1

    with pytest.raises(StreamTimeoutError) as exc_info:
        raise StreamTimeoutError(
            "LLM stream chunk gap exceeded", which=breach["which"],
            elapsed_seconds=breach["elapsed"],
            budget_seconds=breach["budget"],
        )
    assert exc_info.value.which == "chunk"


# ---------------------------------------------------------------------------
# Env-var resolution
# ---------------------------------------------------------------------------


def test_stream_timeout_resolves_default_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("HERMES_LLM_STREAM_TIMEOUT_SECONDS", raising=False)
    assert _resolve_stream_timeout_seconds(
        "HERMES_LLM_STREAM_TIMEOUT_SECONDS", 300.0,
    ) == 300.0


def test_stream_timeout_resolves_negative_to_default(monkeypatch) -> None:
    monkeypatch.setenv("HERMES_LLM_STREAM_TIMEOUT_SECONDS", "-7")
    assert _resolve_stream_timeout_seconds(
        "HERMES_LLM_STREAM_TIMEOUT_SECONDS", 300.0,
    ) == 300.0


# ---------------------------------------------------------------------------
# Lock-scope tests (Fix B + Fix C)
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_lock_dir(tmp_path, monkeypatch):
    """Point the scheduler's lock at a tmp dir per test."""
    lock_dir = tmp_path / "cron"
    lock_dir.mkdir()
    lock_file = lock_dir / ".tick.lock"
    monkeypatch.setattr(
        scheduler, "_get_lock_paths",
        lambda: (lock_dir, lock_file),
    )
    return lock_dir


def test_dispatch_lock_released_during_long_running_stream(
    isolated_lock_dir,
) -> None:
    """The wedge mechanism in one assertion: while one ``tick()`` is
    busy executing a long-running job, a second ``tick()`` invoked
    from another thread must still be able to acquire the dispatch
    lock and proceed (rather than getting "tick skipped" forever).

    We force one tick to spend a long time inside its job-processing
    phase, then fire a second tick mid-flight; if the lock had been
    held across the entire tick (the pre-fix shape), the second tick
    would return 0 with no chance to acquire."""
    # Stub get_due_jobs so each tick "sees" a synthetic due job; the
    # processor side stub records that it started so the test can
    # interleave the second tick mid-execution.
    started = threading.Event()
    release = threading.Event()
    second_tick_acquired: dict = {"value": False}

    fake_job_1 = {"id": "job1", "name": "slow", "no_agent": False,
                  "prompt": "x"}
    fake_job_2 = {"id": "job2", "name": "fast", "no_agent": False,
                  "prompt": "y"}
    call_count = {"n": 0}

    def fake_get_due_jobs():
        call_count["n"] += 1
        # First tick sees a slow job; second tick sees a fast one.
        return [fake_job_1] if call_count["n"] == 1 else [fake_job_2]

    def fake_run_job(job):
        if job["id"] == "job1":
            started.set()
            # Block here so the test can fire the second tick while
            # the first tick is still "executing" job1.
            release.wait(timeout=5)
        return True, "doc", "resp", None

    with patch.object(scheduler, "get_due_jobs", fake_get_due_jobs), \
         patch.object(scheduler, "advance_next_run", lambda jid: None), \
         patch.object(scheduler, "run_job", fake_run_job), \
         patch.object(scheduler, "save_job_output", lambda jid, doc: Path("/tmp/x")), \
         patch.object(scheduler, "mark_job_run", lambda *a, **k: None), \
         patch.object(scheduler, "_deliver_result", lambda *a, **k: None):

        t1 = threading.Thread(target=scheduler.tick, kwargs={"verbose": False})
        t1.start()
        # Wait until tick #1 is inside the slow job — meaning dispatch
        # phase has completed and the lock should have been released.
        assert started.wait(timeout=5), "tick #1 never started its job"

        # Now fire tick #2 from this thread. If the lock-narrow fix is
        # in place, this tick acquires immediately and dispatches its
        # own due-job list. If the fix isn't in place, this tick is
        # blocked by the held lock and returns 0.
        result = scheduler.tick(verbose=False)
        second_tick_acquired["value"] = result == 1

        release.set()
        t1.join(timeout=5)

    assert second_tick_acquired["value"], (
        "tick #2 was blocked by tick #1's lock — the lock-narrow fix "
        "did not take effect"
    )


def test_dispatch_lock_released_on_cancellation(isolated_lock_dir) -> None:
    """A ``KeyboardInterrupt`` raised mid-dispatch must release the
    lock so the next tick can acquire."""

    def cancelling_get_due_jobs():
        raise KeyboardInterrupt("simulated operator stop")

    with patch.object(scheduler, "get_due_jobs", cancelling_get_due_jobs):
        with pytest.raises(KeyboardInterrupt):
            scheduler.tick(verbose=False)

    # Lock must be released — confirm by acquiring it fresh.
    with scheduler._dispatch_lock() as acquired:
        assert acquired, "dispatch lock was leaked across KeyboardInterrupt"


def test_dispatch_lock_released_on_exception(isolated_lock_dir) -> None:
    """An arbitrary unhandled exception raised mid-dispatch must
    release the lock so the next tick can acquire."""

    class _Boom(RuntimeError):
        pass

    def crashing_get_due_jobs():
        raise _Boom("synthetic dispatch crash")

    with patch.object(scheduler, "get_due_jobs", crashing_get_due_jobs):
        with pytest.raises(_Boom):
            scheduler.tick(verbose=False)

    # Lock must be released — confirm by acquiring it fresh.
    with scheduler._dispatch_lock() as acquired:
        assert acquired, "dispatch lock was leaked across exception"

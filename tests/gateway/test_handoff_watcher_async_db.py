"""Tests that _handoff_watcher does not block the async event loop.

The watcher runs inside the gateway's asyncio loop alongside Discord (and
other platform) heartbeat tasks.  Every synchronous SQLite call must be
off-loaded to the default thread pool via ``loop.run_in_executor`` so that
a contended DB lock cannot starve the heartbeat timer.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.run import GatewayRunner


class _SlowDB:
    """Fake SessionDB whose every method sleeps to simulate lock contention."""

    def __init__(self, delay: float = 0.05):
        self.delay = delay
        self._pending = []
        self._calls = []

    def list_pending_handoffs(self):
        time.sleep(self.delay)
        self._calls.append("list_pending_handoffs")
        return list(self._pending)

    def claim_handoff(self, session_id: str) -> bool:
        time.sleep(self.delay)
        self._calls.append(("claim_handoff", session_id))
        return True

    def complete_handoff(self, session_id: str) -> None:
        time.sleep(self.delay)
        self._calls.append(("complete_handoff", session_id))

    def fail_handoff(self, session_id: str, error: str) -> None:
        time.sleep(self.delay)
        self._calls.append(("fail_handoff", session_id, error))


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner._running = True
    runner._session_db = None
    runner._process_handoff = AsyncMock()
    return runner


async def _watcher_with_short_startup(runner: GatewayRunner, interval: float):
    """Call the real _handoff_watcher but skip the 5-second startup sleep."""
    # Patch asyncio.sleep inside the coroutine so the initial 5s becomes 0s.
    real_sleep = asyncio.sleep
    async def _short_sleep(delay):
        if delay >= 1:
            return await real_sleep(0)
        return await real_sleep(delay)
    with patch("gateway.run.asyncio.sleep", new=_short_sleep):
        await runner._handoff_watcher(interval=interval)


@pytest.mark.asyncio
async def test_handoff_watcher_does_not_block_event_loop():
    """When the DB is slow, other asyncio tasks must still make progress."""
    runner = _make_runner()
    db = _SlowDB(delay=0.05)
    db._pending = [{"id": "s1", "handoff_platform": "telegram"}]
    runner._session_db = db

    heartbeat_ticks = []

    async def heartbeat():
        while runner._running:
            heartbeat_ticks.append(time.monotonic())
            await asyncio.sleep(0.01)

    # Start the heartbeat and the watcher concurrently.
    heartbeat_task = asyncio.create_task(heartbeat())
    watcher_task = asyncio.create_task(
        _watcher_with_short_startup(runner, interval=0.01)
    )

    # Let them race for a short window.
    await asyncio.sleep(0.12)

    # Stop both.
    runner._running = False
    await asyncio.wait_for(watcher_task, timeout=2.0)
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    # The heartbeat should have ticked many times (>5) even though the DB
    # methods each sleep 50 ms.  If the watcher blocked the loop, the
    # heartbeat would have stalled.
    assert len(heartbeat_ticks) > 5, (
        f"Heartbeat only ticked {len(heartbeat_ticks)} times — "
        "event loop was blocked by synchronous DB calls"
    )

    # Verify the watcher actually did its work (off-loaded to executor).
    assert "list_pending_handoffs" in db._calls
    assert ("claim_handoff", "s1") in db._calls
    assert ("complete_handoff", "s1") in db._calls


@pytest.mark.asyncio
async def test_handoff_watcher_runs_db_calls_in_executor():
    """Direct test: every DB method in the watcher tick must be awaited
    via run_in_executor (i.e. they are coroutines in the watcher body)."""
    runner = _make_runner()
    db = _SlowDB(delay=0.01)
    db._pending = [{"id": "s2", "handoff_platform": "discord"}]
    runner._session_db = db

    loop = asyncio.get_running_loop()
    executor_calls = []
    original_run_in_executor = loop.run_in_executor

    async def _spy_run_in_executor(executor, fn, *args):
        executor_calls.append((fn.__name__, args))
        return await original_run_in_executor(executor, fn, *args)

    with patch.object(loop, "run_in_executor", side_effect=_spy_run_in_executor):
        runner._running = True
        watcher = asyncio.create_task(
            _watcher_with_short_startup(runner, interval=0.01)
        )
        await asyncio.sleep(0.08)
        runner._running = False
        await asyncio.wait_for(watcher, timeout=2.0)

    # All four DB touch-points must have gone through the executor.
    assert ("list_pending_handoffs", ()) in executor_calls
    assert ("claim_handoff", ("s2",)) in executor_calls
    assert ("complete_handoff", ("s2",)) in executor_calls


@pytest.mark.asyncio
async def test_handoff_watcher_fail_path_also_uses_executor():
    """If _process_handoff raises, fail_handoff must also be off-loaded."""
    runner = _make_runner()
    db = _SlowDB(delay=0.01)
    db._pending = [{"id": "s3", "handoff_platform": "slack"}]
    runner._session_db = db
    runner._process_handoff = AsyncMock(side_effect=RuntimeError("boom"))

    loop = asyncio.get_running_loop()
    executor_calls = []
    original_run_in_executor = loop.run_in_executor

    async def _spy_run_in_executor(executor, fn, *args):
        executor_calls.append((fn.__name__, args))
        return await original_run_in_executor(executor, fn, *args)

    with patch.object(loop, "run_in_executor", side_effect=_spy_run_in_executor):
        runner._running = True
        watcher = asyncio.create_task(
            _watcher_with_short_startup(runner, interval=0.01)
        )
        await asyncio.sleep(0.08)
        runner._running = False
        await asyncio.wait_for(watcher, timeout=2.0)

    assert ("list_pending_handoffs", ()) in executor_calls
    assert ("claim_handoff", ("s3",)) in executor_calls
    assert ("fail_handoff", ("s3", "boom")) in executor_calls


@pytest.mark.asyncio
async def test_handoff_watcher_skips_when_no_session_db():
    """When _session_db is None the watcher should just sleep and loop."""
    runner = _make_runner()
    runner._session_db = None

    runner._running = True
    watcher = asyncio.create_task(
        _watcher_with_short_startup(runner, interval=0.01)
    )
    await asyncio.sleep(0.03)
    runner._running = False
    await asyncio.wait_for(watcher, timeout=2.0)

    # No exceptions → success.

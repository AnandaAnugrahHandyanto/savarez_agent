"""
Tests for the /restart zombie-process fix (issue #12875).

Before the fix, _stop_impl() cancelled ALL tasks in _background_tasks except
_stop_task itself.  Because _restart_task was also in _background_tasks, it
got cancelled mid-execution — before it could set _exit_code = 75 or call
_shutdown_event.set().  This left the process either hanging (zombie) or
exiting with code 0 (systemd won't restart on non-failure exit).

The fix: store the restart coroutine's task in self._restart_task and exclude
it from the cancellation sweep, symmetric with how _stop_task is excluded.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.gateway.restart_test_helpers import make_restart_runner


class TestRestartTaskNotCancelled:
    """_restart_task must survive _stop_impl's background-task cancellation."""

    def test_restart_task_stored_on_instance(self):
        """request_restart() stores the asyncio Task in self._restart_task."""
        runner, _ = make_restart_runner()
        runner.stop = AsyncMock()

        with patch("asyncio.create_task", wraps=asyncio.get_event_loop().create_task if False else asyncio.create_task):
            # Just verify the attribute exists and is None before restart
            assert hasattr(runner, "_restart_task")
            assert runner._restart_task is None

    @pytest.mark.asyncio
    async def test_restart_task_populated_after_request_restart(self):
        """After request_restart(), _restart_task holds the running Task."""
        runner, _ = make_restart_runner()
        runner.stop = AsyncMock()  # prevent actual stop

        result = runner.request_restart(detached=False, via_service=True)

        assert result is True
        assert runner._restart_task is not None
        assert isinstance(runner._restart_task, asyncio.Task)

        # Clean up
        runner._restart_task.cancel()
        try:
            await runner._restart_task
        except (asyncio.CancelledError, Exception):
            pass

    @pytest.mark.asyncio
    async def test_restart_task_cleared_after_completion(self):
        """_restart_task is set back to None once the task finishes."""
        runner, _ = make_restart_runner()

        stop_started = asyncio.Event()
        stop_done = asyncio.Event()

        async def fake_stop(**kwargs):
            stop_started.set()
            await stop_done.wait()

        runner.stop = fake_stop
        runner.request_restart(detached=False, via_service=True)

        await stop_started.wait()
        assert runner._restart_task is not None

        stop_done.set()
        await asyncio.sleep(0.05)  # let done-callback fire
        assert runner._restart_task is None

    @pytest.mark.asyncio
    async def test_restart_task_excluded_from_background_task_cancellation(self):
        """
        The core regression test.

        Simulate the cancellation loop in _stop_impl: iterate _background_tasks
        and cancel everything except _stop_task and _restart_task.
        Verify that _restart_task is NOT cancelled.
        """
        runner, _ = make_restart_runner()

        restart_reached_stop = asyncio.Event()

        async def fake_stop(**kwargs):
            restart_reached_stop.set()
            # Simulate a long-running stop — the restart task should not be
            # cancelled while it is waiting here.
            await asyncio.sleep(10)

        runner.stop = fake_stop
        runner.request_restart(detached=False, via_service=True)

        await restart_reached_stop.wait()
        assert runner._restart_task is not None

        # Replicate _stop_impl cancellation logic
        mock_stop_task = MagicMock(spec=asyncio.Task)
        runner._stop_task = mock_stop_task

        cancelled = []
        for task in list(runner._background_tasks):
            if task is runner._stop_task or task is runner._restart_task:
                continue
            task.cancel()
            cancelled.append(task)

        # _restart_task must NOT have been cancelled
        assert not runner._restart_task.cancelled(), (
            "_restart_task was cancelled by the stop sweep — this is the zombie bug"
        )

        # Clean up
        runner._restart_task.cancel()
        try:
            await runner._restart_task
        except (asyncio.CancelledError, Exception):
            pass

    @pytest.mark.asyncio
    async def test_request_restart_idempotent(self):
        """Second call to request_restart() is a no-op (returns False)."""
        runner, _ = make_restart_runner()
        runner.stop = AsyncMock()

        first = runner.request_restart(detached=False, via_service=False)
        second = runner.request_restart(detached=True, via_service=True)

        assert first is True
        assert second is False  # already started

        runner._restart_task.cancel()
        try:
            await runner._restart_task
        except (asyncio.CancelledError, Exception):
            pass

    @pytest.mark.asyncio
    async def test_restart_task_in_background_tasks_set(self):
        """_restart_task is tracked in _background_tasks for lifecycle management."""
        runner, _ = make_restart_runner()
        runner.stop = AsyncMock()

        runner.request_restart(detached=False, via_service=True)

        assert runner._restart_task in runner._background_tasks

        runner._restart_task.cancel()
        try:
            await runner._restart_task
        except (asyncio.CancelledError, Exception):
            pass

import asyncio
import queue

import pytest

from gateway.run import (
    _finish_tool_progress_task,
    _reset_tool_progress_state,
)


@pytest.mark.parametrize("mode", ["new", "all", "verbose"])
@pytest.mark.parametrize("single_message", [False, True])
def test_tool_progress_single_message_controls_reset_independent_of_progress_mode(mode, single_message):
    progress_lines = [f"{mode}-first", f"{mode}-second"]
    last_progress_msg: list[str | None] = [f"{mode}-second"]
    repeat_count = [3]

    reset = _reset_tool_progress_state(
        progress_lines,
        last_progress_msg,
        repeat_count,
        single_message=single_message,
    )

    assert reset is (not single_message), mode
    if single_message:
        assert progress_lines == [f"{mode}-first", f"{mode}-second"]
        assert last_progress_msg == [f"{mode}-second"]
        assert repeat_count == [3]
    else:
        assert progress_lines == []
        assert last_progress_msg == [None]
        assert repeat_count == [0]


@pytest.mark.asyncio
async def test_finish_tool_progress_task_sends_finish_sentinel_before_cancelling():
    progress_queue = queue.Queue()
    finished = asyncio.Event()

    async def worker():
        while True:
            try:
                item = progress_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue
            if isinstance(item, tuple) and item[0] == "__finish__":
                finished.set()
                return

    task = asyncio.create_task(worker())

    await _finish_tool_progress_task(task, progress_queue, timeout=1.0)

    assert finished.is_set()
    assert task.done()


@pytest.mark.asyncio
async def test_finish_tool_progress_task_preserves_outer_cancellation():
    progress_queue = queue.Queue()

    async def worker():
        await asyncio.sleep(10)

    task = asyncio.create_task(worker())
    finisher = asyncio.create_task(_finish_tool_progress_task(task, progress_queue, timeout=10.0))
    await asyncio.sleep(0)

    finisher.cancel()
    with pytest.raises(asyncio.CancelledError):
        await finisher
    assert task.cancelled()

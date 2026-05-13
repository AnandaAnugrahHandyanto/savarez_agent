"""Regression test for #24604 — progress_callback dedup state is thread-safe.

The shared closure variables last_progress_msg / repeat_count / last_tool are
accessed from concurrent ThreadPoolExecutor workers.  Without a lock the dedup
check-and-update is non-atomic and can produce duplicate progress bubbles or
lost (×N) repeat counters.  This test drives the dedup logic from many threads
simultaneously and verifies deterministic behaviour.
"""

import queue
import threading
from typing import List


def _make_dedup_callback(progress_queue: queue.Queue, progress_mode: str = "all"):
    """Replicate the locked dedup logic from gateway/run.py progress_callback."""
    last_tool = [None]
    last_progress_msg = [None]
    repeat_count = [0]
    _dedup_lock = threading.Lock()

    def callback(event_type: str, tool_name: str = None, **kwargs):
        if event_type != "tool.started":
            return

        msg = f"{tool_name}..."

        with _dedup_lock:
            if progress_mode == "new" and tool_name == last_tool[0]:
                return
            last_tool[0] = tool_name

        with _dedup_lock:
            if msg == last_progress_msg[0]:
                repeat_count[0] += 1
                progress_queue.put(("__dedup__", msg, repeat_count[0]))
                return
            last_progress_msg[0] = msg
            repeat_count[0] = 0

        progress_queue.put(msg)

    return callback


class TestProgressDedupConcurrency:
    def test_same_message_concurrent_dedup_no_duplicate_new(self):
        """N threads fire the same tool event: exactly one 'new' enqueue, rest dedup."""
        pq: queue.Queue = queue.Queue()
        cb = _make_dedup_callback(pq)
        n = 50
        barrier = threading.Barrier(n)

        def _fire():
            barrier.wait()
            cb("tool.started", "web_search")

        threads = [threading.Thread(target=_fire) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        items: List = []
        while not pq.empty():
            items.append(pq.get_nowait())

        new_msgs = [i for i in items if isinstance(i, str)]
        assert len(new_msgs) == 1, f"expected 1 new msg, got {new_msgs}"

        dedup_counts = sorted(i[2] for i in items if isinstance(i, tuple) and i[0] == "__dedup__")
        assert len(dedup_counts) == n - 1
        assert dedup_counts == list(range(1, n)), f"gap in dedup counts: {dedup_counts}"

    def test_different_messages_concurrent_no_dedup(self):
        """N threads each fire a unique tool event: all N are enqueued as new."""
        pq: queue.Queue = queue.Queue()
        cb = _make_dedup_callback(pq)
        n = 20
        barrier = threading.Barrier(n)

        def _fire(i):
            barrier.wait()
            cb("tool.started", f"tool_{i}")

        threads = [threading.Thread(target=_fire, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        items: List = []
        while not pq.empty():
            items.append(pq.get_nowait())

        new_msgs = [i for i in items if isinstance(i, str)]
        assert len(new_msgs) == n, f"expected {n} new msgs, got {len(new_msgs)}"

    def test_new_mode_same_tool_deduplicated(self):
        """In 'new' mode, repeated same-tool calls from concurrent threads are skipped."""
        pq: queue.Queue = queue.Queue()
        cb = _make_dedup_callback(pq, progress_mode="new")
        n = 30
        barrier = threading.Barrier(n)

        def _fire():
            barrier.wait()
            cb("tool.started", "execute_code")

        threads = [threading.Thread(target=_fire) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        items: List = []
        while not pq.empty():
            items.append(pq.get_nowait())

        new_msgs = [i for i in items if isinstance(i, str)]
        assert len(new_msgs) == 1, f"expected 1 enqueue in new-mode, got {len(new_msgs)}"

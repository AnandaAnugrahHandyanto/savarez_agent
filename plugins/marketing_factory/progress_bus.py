"""In-memory progress event bus for the Marketing Agent Factory.

Pipeline agents publish events as they run (`agent.start`, `agent.end`,
`campaign.start`, etc). The dashboard's `/progress/stream` SSE endpoint
subscribes and streams them to the browser in real time.

Cross-thread-safe: pipeline.generate_campaign runs in a threadpool (so it
doesn't block FastAPI's event loop), but subscribers wait on
asyncio.Queue inside the main loop. We bridge via
`asyncio.run_coroutine_threadsafe` when the publisher is on a worker
thread, falling back to `put_nowait` when both sides happen to share a
loop (e.g. unit tests).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Bounded ring buffer of recent events so late SSE subscribers see what
# happened in the last few seconds without missing a beat.
_BUFFER_CAP = 200
_recent: Deque[Dict[str, Any]] = deque(maxlen=_BUFFER_CAP)

# (queue, loop) per subscriber. Storing the loop lets us route cross-thread
# puts through run_coroutine_threadsafe even when the publisher is on a
# threadpool worker.
_subscribers: List[Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []
_lock = threading.Lock()
_seq = 0


def _next_seq() -> int:
    global _seq
    with _lock:
        _seq += 1
        return _seq


def publish(event_type: str, **payload: Any) -> Dict[str, Any]:
    """Sync-callable publish — safe from any thread."""
    event: Dict[str, Any] = {
        "seq": _next_seq(),
        "type": event_type,
        "timestamp": time.time(),
        **payload,
    }
    with _lock:
        _recent.append(event)
        subs = list(_subscribers)

    for queue, loop in subs:
        try:
            if loop.is_running():
                try:
                    running = asyncio.get_running_loop()
                except RuntimeError:
                    running = None
                if running is loop:
                    # Same loop as the publisher — direct put.
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        pass
                else:
                    # Cross-thread — schedule the put on the subscriber's loop.
                    asyncio.run_coroutine_threadsafe(_safe_put(queue, event), loop)
            else:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass
        except Exception as exc:  # noqa: BLE001 — a single bad subscriber must not break others
            logger.debug("progress_bus subscriber delivery failed: %s", exc)
    return event


async def _safe_put(queue: asyncio.Queue, event: Dict[str, Any]) -> None:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        pass


def subscribe(loop: Optional[asyncio.AbstractEventLoop] = None) -> asyncio.Queue:
    """Register a subscriber on the given event loop (defaults to running loop)."""
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    with _lock:
        _subscribers.append((queue, loop))
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    with _lock:
        _subscribers[:] = [(q, l) for (q, l) in _subscribers if q is not queue]


def recent(limit: int = 30) -> List[Dict[str, Any]]:
    """Last `limit` events, oldest first. Used by SSE backfill on connect."""
    with _lock:
        if limit >= len(_recent):
            return list(_recent)
        return list(_recent)[-limit:]


def clear() -> None:
    """For tests."""
    global _seq
    with _lock:
        _recent.clear()
        _subscribers.clear()
        _seq = 0

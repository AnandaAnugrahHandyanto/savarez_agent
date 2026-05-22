"""Async pub/sub event bus for Hermes agent lifecycle events.

Zero external dependencies. Thread-safe for sync callers; async handlers
are dispatched via asyncio.create_task to avoid blocking the emitter.

Event types are defined as dataclass instances so they carry structured
payloads rather than opaque strings.

Usage::

    from agent.event_bus import get_event_bus, HermesEventType

    bus = get_event_bus()

    def on_api_error(ev):
        print(f"API error: {ev.payload['reason']}")

    unsub = bus.subscribe(HermesEventType.API_ERROR, on_api_error)
    bus.emit(HermesEventType.API_ERROR, payload={"reason": "rate_limit"})

    # Later: stop receiving events
    unsub()

    # Inspect subscriber count (useful in tests)
    count = bus.subscriber_count(HermesEventType.API_ERROR)  # → 0
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List


class HermesEventType(str, Enum):
    """All events the bus can carry."""

    # API lifecycle
    API_CALL = "hermes:api:call"
    API_ERROR = "hermes:api:error"
    API_RETRY = "hermes:api:retry"

    # Delegation (delegate_tool.py emits these)
    DELEGATION_STARTED = "hermes:delegation:started"
    DELEGATION_FAILED = "hermes:delegation:failed"
    DELEGATION_COMPLETED = "hermes:delegation:completed"

    # Iteration budget
    ITERATION_CONSUMED = "hermes:iteration:consumed"
    ITERATION_EXHAUSTED = "hermes:iteration:exhausted"

    # Operational state machine
    STATE_TRANSITION = "hermes:state:transition"
    FALLBACK_ACTIVATED = "hermes:fallback:activated"

    # Context management
    CONTEXT_COMPRESSED = "hermes:context:compressed"

    # Lifecycle
    TURN_STARTED = "hermes:lifecycle:turn:started"
    TURN_COMPLETED = "hermes:lifecycle:turn:completed"
    TASK_STARTED = "hermes:lifecycle:task:started"
    TASK_ENDED = "hermes:lifecycle:task:ended"


@dataclass(frozen=True)
class HermesEvent:
    """A single event emitted on the bus."""

    type: HermesEventType
    payload: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"HermesEvent({self.type.value}, {self.payload})"


# Handler signature
EventHandler = Callable[[HermesEvent], None]
UnsubscribeFn = Callable[[], None]


class EventBus:
    """Thread-safe async-capable pub/sub bus.

    Supports both sync and async handlers. Sync handlers run immediately
    in the emitting thread. Async handlers are fire-and-forget via
    ``asyncio.create_task`` so the emitter never blocks onawait.
    """

    __slots__ = ("_handlers", "_lock")

    def __init__(self) -> None:
        self._handlers: Dict[HermesEventType, List[EventHandler]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(
        self, event_type: HermesEventType, handler: EventHandler
    ) -> UnsubscribeFn:
        """Register ``handler`` for ``event_type``. Returns an unsubscribe fn."""
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            # Avoid double-registration of the same handler object
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            with self._lock:
                if event_type in self._handlers:
                    try:
                        self._handlers[event_type].remove(handler)
                    except ValueError:
                        pass  # already removed

        return unsubscribe

    def emit(self, event: HermesEvent) -> None:
        """Dispatch ``event`` to all registered handlers.

        Sync handlers run synchronously in the calling thread.
        Async handlers are fire-and-forget (no await).
        Raises from handlers are swallowed to protect the emitter.
        """
        handlers: List[EventHandler] = []
        with self._lock:
            handlers = list(self._handlers.get(event.type, []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(event))
                    except RuntimeError:
                        # No running loop — dispatch via a background loop
                        # on a daemon thread so we never block the emitter.
                        _dispatch_async(handler, event)
                else:
                    handler(event)
            except Exception:
                # Never let a misbehaving handler break the emitter
                pass

    def subscriber_count(self, event_type: HermesEventType) -> int:
        """Return number of subscribers for ``event_type`` (for tests)."""
        with self._lock:
            return len(self._handlers.get(event_type, []))


# ------------------------------------------------------------------
# Process-global bus (one per agent process; thread-safe singleton)
# ------------------------------------------------------------------

_consumer_loop: asyncio.AbstractEventLoop | None = None
_consumer_loop_lock = threading.Lock()


def _get_consumer_loop() -> asyncio.AbstractEventLoop:
    """Lazily create a consumer event loop on a background thread."""
    global _consumer_loop
    if _consumer_loop is None:
        with _consumer_loop_lock:
            if _consumer_loop is None:
                loop = asyncio.new_event_loop()
                t = threading.Thread(target=loop.run_forever, daemon=True)
                t.start()
                _consumer_loop = loop
    return _consumer_loop


def _dispatch_async(handler: EventHandler, event: HermesEvent) -> None:
    """Schedule an async handler on the shared consumer loop (no running loop needed)."""
    loop = _get_consumer_loop()
    asyncio.run_coroutine_threadsafe(handler(event), loop)


_bus: EventBus | None = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Return the shared process-global EventBus instance."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = EventBus()
    return _bus

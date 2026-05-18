"""Process-wide circuit breaker for Honcho backend calls.

When the Honcho service is unreachable (timeout, connection refused), every
turn would otherwise re-attempt the same failing call — wasting up to 30s
of latency per attempt and spamming the error log. The breaker tracks
consecutive failures and short-circuits subsequent calls for a cooldown
window once a failure threshold is reached.

State machine:
    closed   → calls pass through; record_failure increments counter;
               threshold consecutive failures → open
    open     → calls are rejected immediately; after cooldown window
               elapses, transitions to half-open on next allow()
    half-open → one probe call is permitted; success → closed,
                failure → open (cooldown restarts)

A single WARN log line is emitted per transition (closed→open, open→closed),
never per-call. That keeps errors.log readable even during long outages.

The breaker is process-wide (one singleton per profile/process). Multiple
HonchoSessionManager instances share state — if the dialectic path trips
the breaker, background message sync sees the open state too and skips
its own retries.

Also writes a small JSON snapshot to ${HERMES_HOME}/honcho-circuit.json on
every transition so `hermes honcho status` (out of process) can render the
current breaker state without having to attach to the running agent.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# State names — kept as strings so they serialise cleanly into the snapshot
# file consumed by the CLI status command.
STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half-open"


@dataclass
class _BreakerSnapshot:
    state: str
    consecutive_failures: int
    opened_at: float
    cooldown_remaining_s: float
    last_error: str
    last_transition: str  # ISO8601


class HonchoCircuitBreaker:
    """Thread-safe circuit breaker for Honcho client calls.

    Failures are counted across all callers; one process-wide instance
    is exposed via ``get_breaker()`` so dialectic / message-sync / file-upload
    paths share the same state.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        cooldown_s: float = 60.0,
        snapshot_path: Path | None = None,
        now: Callable[[], float] = time.monotonic,
        wall_now: Callable[[], float] = time.time,
    ) -> None:
        self._failure_threshold = max(1, int(failure_threshold))
        self._cooldown_s = max(0.0, float(cooldown_s))
        self._snapshot_path = snapshot_path
        self._now = now
        self._wall_now = wall_now

        self._lock = threading.RLock()
        self._state: str = STATE_CLOSED
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._last_error: str = ""
        self._last_transition_wall: float = wall_now()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def allow(self) -> bool:
        """Return True if the next call should be attempted.

        Side effect: when the cooldown window has elapsed, the breaker
        moves from ``open`` to ``half-open`` and allows exactly one probe
        through.
        """
        with self._lock:
            if self._state == STATE_CLOSED:
                return True
            if self._state == STATE_OPEN:
                elapsed = self._now() - self._opened_at
                if elapsed >= self._cooldown_s:
                    self._set_state(STATE_HALF_OPEN, log=False)
                    return True
                return False
            # half-open: another caller already grabbed the probe slot;
            # block them so we don't issue a thundering-herd of probes.
            return False

    def record_success(self) -> bool:
        """Record a successful call. Returns True if the breaker closed."""
        with self._lock:
            transitioned = self._state != STATE_CLOSED
            if transitioned:
                logger.info(
                    "Honcho circuit breaker: closing (recovered after %d failure(s))",
                    self._failures,
                )
            self._failures = 0
            self._last_error = ""
            if transitioned:
                self._set_state(STATE_CLOSED)
            return transitioned

    def record_failure(self, error: BaseException | str | None = None) -> bool:
        """Record a failed call. Returns True if the breaker transitioned to open."""
        with self._lock:
            if error is not None:
                self._last_error = self._format_error(error)
            # Half-open probe failed → re-open with fresh cooldown.
            if self._state == STATE_HALF_OPEN:
                self._opened_at = self._now()
                logger.warning(
                    "Honcho circuit breaker: half-open probe failed (%s); "
                    "re-opening for %.0fs",
                    self._last_error or "unknown",
                    self._cooldown_s,
                )
                self._set_state(STATE_OPEN)
                return True
            self._failures += 1
            if (
                self._state == STATE_CLOSED
                and self._failures >= self._failure_threshold
            ):
                self._opened_at = self._now()
                logger.warning(
                    "Honcho circuit breaker: opening after %d consecutive failures "
                    "(last error: %s); skipping Honcho for %.0fs",
                    self._failures,
                    self._last_error or "unknown",
                    self._cooldown_s,
                )
                self._set_state(STATE_OPEN)
                return True
            return False

    def reset(self) -> None:
        """Force the breaker back to closed (for tests / manual recovery)."""
        with self._lock:
            self._failures = 0
            self._last_error = ""
            self._opened_at = 0.0
            self._set_state(STATE_CLOSED, log=False)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def snapshot(self) -> _BreakerSnapshot:
        with self._lock:
            cooldown_left = 0.0
            if self._state == STATE_OPEN and self._cooldown_s > 0:
                cooldown_left = max(
                    0.0, self._cooldown_s - (self._now() - self._opened_at)
                )
            return _BreakerSnapshot(
                state=self._state,
                consecutive_failures=self._failures,
                opened_at=self._opened_at,
                cooldown_remaining_s=cooldown_left,
                last_error=self._last_error,
                last_transition=time.strftime(
                    "%Y-%m-%dT%H:%M:%S",
                    time.localtime(self._last_transition_wall),
                ),
            )

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._failures

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _set_state(self, new_state: str, *, log: bool = True) -> None:
        # Caller holds self._lock.
        if new_state == self._state:
            return
        self._state = new_state
        self._last_transition_wall = self._wall_now()
        self._write_snapshot()

    def _write_snapshot(self) -> None:
        if self._snapshot_path is None:
            return
        snap = {
            "state": self._state,
            "consecutive_failures": self._failures,
            "opened_at_monotonic": self._opened_at,
            "cooldown_s": self._cooldown_s,
            "last_error": self._last_error,
            "last_transition_epoch": self._last_transition_wall,
        }
        try:
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._snapshot_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(snap, indent=2))
            tmp.replace(self._snapshot_path)
        except OSError as exc:
            # Don't let snapshot IO failures block the breaker.
            logger.debug("Honcho circuit breaker: snapshot write failed: %s", exc)

    @staticmethod
    def _format_error(err: BaseException | str) -> str:
        if isinstance(err, str):
            return err[:200]
        # ``ConnectionRefusedError([Errno 61] ...)`` → ``ConnectionRefusedError: …``
        return f"{type(err).__name__}: {str(err)[:160]}"


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------
_breaker_lock = threading.Lock()
_breaker: HonchoCircuitBreaker | None = None


def _default_snapshot_path() -> Path | None:
    """Resolve ${HERMES_HOME}/honcho-circuit.json without circular imports."""
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home() / "honcho-circuit.json"
    except Exception:
        # Stand-alone tests / boot before hermes_constants is importable.
        env = os.environ.get("HERMES_HOME")
        if env:
            return Path(env) / "honcho-circuit.json"
        return None


def get_breaker(
    *,
    failure_threshold: int | None = None,
    cooldown_s: float | None = None,
) -> HonchoCircuitBreaker:
    """Return the process-wide breaker, constructing it on first call.

    Subsequent calls ignore the threshold/cooldown args (the breaker is a
    singleton). Tests can use ``reset_breaker()`` to install a fresh one.
    """
    global _breaker
    with _breaker_lock:
        if _breaker is None:
            _breaker = HonchoCircuitBreaker(
                failure_threshold=failure_threshold or 3,
                cooldown_s=cooldown_s if cooldown_s is not None else 60.0,
                snapshot_path=_default_snapshot_path(),
            )
        return _breaker


def reset_breaker() -> None:
    """Tear down the singleton (test helper)."""
    global _breaker
    with _breaker_lock:
        _breaker = None

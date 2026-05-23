"""Operational state machine for Hermes agent.

Replaces ad-hoc retry-count tracking with a proper state machine driven by
observable signals:

  - Iteration budget fraction (remaining / total)
  - Consecutive error count (resets on any successful turn)

Maps to four operational states::

  STANDBY  → ACTIVE  → DEGRADED  → CRITICAL
    ↑          ↓          ↑            ↓
    └──────────┴──────────┴────────────┘
           (recovery possible)

State transitions are idempotent — requesting the current state is a no-op.
Every transition fires ``hermes:state:transition`` on the event bus.

Usage::

    from agent.operational_state import OperationalStateManager, OperationalState
    from agent.event_bus import get_event_bus

    op = OperationalStateManager(get_event_bus())

    op.on_task_started()
    op.on_turn_complete(ok=True)      # reset error streak
    op.on_turn_complete(ok=False)     # increment error streak, may DEGRADED
    op.on_budget_update(0.15)          # fraction remaining; may DEGRADED/CRITICAL
    op.on_task_ended()

    current = op.state                 # e.g. OperationalState.DEGRADED
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from agent.event_bus import EventBus, HermesEvent, HermesEventType


class OperationalState(str, Enum):
    """Possible operational states, most-healthy first."""

    STANDBY = "standby"  # No active task
    ACTIVE = "active"  # Task running, nominal
    DEGRADED = "degraded"  # Recoverable failures occurring
    CRITICAL = "critical"  # Exhausted recovery options


# Thresholds (can be overridden per-instance)
_DEGRADED_BUDGET_FRAC = 0.20  # <20% budget → DEGRADED
_CRITICAL_BUDGET_FRAC = 0.05  # <5%  budget → CRITICAL
_DEGRADED_ERROR_STREAK = 3  # 3+ consecutive errors → DEGRADED
_CRITICAL_ERROR_STREAK = 6  # 6+ consecutive errors → CRITICAL


@dataclass
class OperationalStateManager:
    """Thread-safe state machine with event-bus integration."""

    bus: EventBus
    degraded_budget_frac: float = field(default=_DEGRADED_BUDGET_FRAC)
    critical_budget_frac: float = field(default=_CRITICAL_BUDGET_FRAC)
    degraded_error_streak: int = field(default=_DEGRADED_ERROR_STREAK)
    critical_error_streak: int = field(default=_CRITICAL_ERROR_STREAK)

    # Internal counters
    _state: OperationalState = field(default=OperationalState.STANDBY, init=False)
    _error_streak: int = field(default=0, init=False)
    _budget_frac: float = field(default=1.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    # ------------------------------------------------------------------
    # Public read access
    # ------------------------------------------------------------------

    @property
    def state(self) -> OperationalState:
        with self._lock:
            return self._state

    @property
    def error_streak(self) -> int:
        with self._lock:
            return self._error_streak

    @property
    def budget_frac(self) -> float:
        with self._lock:
            return self._budget_frac

    # ------------------------------------------------------------------
    # State transition helpers
    # ------------------------------------------------------------------

    def on_task_started(self) -> None:
        """Begin a new task — enter ACTIVE from STANDBY."""
        self._transition(OperationalState.ACTIVE)

    def on_task_ended(self) -> None:
        """Task finished — return to STANDBY."""
        with self._lock:
            self._error_streak = 0
            self._budget_frac = 1.0
        self._transition(OperationalState.STANDBY)

    def on_turn_complete(self, *, ok: bool) -> None:
        """Record a turn outcome.

        Args:
            ok: True on successful API response, False on error/retry.
        """
        with self._lock:
            if ok:
                self._error_streak = 0
            else:
                self._error_streak += 1

            self._evaluate_locked()

    def on_budget_update(self, fraction: float) -> None:
        """Update the iteration budget fraction and re-evaluate state.

        Args:
            fraction: remaining budget as a fraction of total (0.0–1.0).
        """
        with self._lock:
            self._budget_frac = fraction
            self._evaluate_locked()

    def on_fallback_activated(self) -> None:
        """A fallback model was successfully activated — treat as recovery signal."""
        with self._lock:
            self._error_streak = max(0, self._error_streak - 2)
            self._evaluate_locked()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evaluate_locked(self) -> None:
        """Called with _lock held. Determines next state and transitions if needed."""
        if self._state in (OperationalState.STANDBY, OperationalState.CRITICAL):
            # STANDBY: wait for explicit on_task_started.
            # CRITICAL: only transitions via explicit recovery events.
            return

        # Compute target state from signals
        if (
            self._budget_frac < self.critical_budget_frac
            or self._error_streak >= self.critical_error_streak
        ):
            target = OperationalState.CRITICAL
        elif (
            self._budget_frac < self.degraded_budget_frac
            or self._error_streak >= self.degraded_error_streak
        ):
            target = OperationalState.DEGRADED
        else:
            target = OperationalState.ACTIVE

        self._transition_locked(target)

    def _transition(self, new_state: OperationalState) -> None:
        with self._lock:
            self._transition_locked(new_state)

    def _transition_locked(self, new_state: OperationalState) -> None:
        """Called with _lock held. Performs the transition."""
        if new_state == self._state:
            return  # Idempotent

        old_state = self._state
        self._state = new_state

        event = HermesEvent(
            type=HermesEventType.STATE_TRANSITION,
            payload={
                "previous": old_state.value,
                "current": new_state.value,
                "error_streak": self._error_streak,
                "budget_frac": round(self._budget_frac, 4),
            },
        )

        # Release lock before emitting so handlers can call back into self
        self._lock.release()
        try:
            self.bus.emit(event)
        finally:
            self._lock.acquire()

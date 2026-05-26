"""Per-agent iteration and per-turn budget helpers.

Extracted from ``run_agent.py``.  Each ``AIAgent`` instance (parent or
subagent) holds an :class:`IterationBudget`; the parent's cap comes from
``max_iterations`` (default 90), each subagent's cap comes from
``delegation.max_iterations`` (default 50).

``run_agent`` re-exports ``IterationBudget`` so existing
``from run_agent import IterationBudget`` imports keep working unchanged.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

DEFAULT_MAX_TOOL_CALLS_PER_TURN = 50
DEFAULT_REPEAT_TOOL_THRESHOLD = 3
DEFAULT_USAGE_EVENTS_PATH = "/Users/xbr/.agentic-stack/usage-events.jsonl"


def coerce_optional_positive_int(value: Any, default: int | None) -> int | None:
    """Return a positive int, or default when unset/invalid."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def coerce_optional_positive_float(value: Any, default: float | None = None) -> float | None:
    """Return a positive float, or default when unset/invalid."""
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def append_usage_event(event: dict[str, Any], path: str | None = None) -> bool:
    """Append one usage event to JSONL. Best-effort; never raises."""
    target = path or DEFAULT_USAGE_EVENTS_PATH
    try:
        event = dict(event)
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        out_path = Path(target).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return True
    except Exception as exc:  # pragma: no cover - logging-only failure path
        logger.warning("Failed to append usage event to %s: %s", target, exc)
        return False


class IterationBudget:
    """Thread-safe iteration counter for an agent.

    Each agent (parent or subagent) gets its own ``IterationBudget``.
    The parent's budget is capped at ``max_iterations`` (default 90).
    Each subagent gets an independent budget capped at
    ``delegation.max_iterations`` (default 50) — this means total
    iterations across parent + subagents can exceed the parent's cap.
    Users control the per-subagent limit via ``delegation.max_iterations``
    in config.yaml.

    ``execute_code`` (programmatic tool calling) iterations are refunded via
    :meth:`refund` so they don't eat into the budget.
    """

    def __init__(self, max_total: int):
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Try to consume one iteration.  Returns True if allowed."""
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        """Give back one iteration (e.g. for execute_code turns)."""
        with self._lock:
            if self._used > 0:
                self._used -= 1

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.max_total - self._used)


__all__ = [
    "IterationBudget",
    "DEFAULT_MAX_TOOL_CALLS_PER_TURN",
    "DEFAULT_REPEAT_TOOL_THRESHOLD",
    "DEFAULT_USAGE_EVENTS_PATH",
    "append_usage_event",
    "coerce_optional_positive_float",
    "coerce_optional_positive_int",
]

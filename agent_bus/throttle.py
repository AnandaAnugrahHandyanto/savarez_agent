"""Codex dispatch throttle (§9 of dual-agent-evolution-plan-2026q2).

Tracks the last dispatch timestamp per `(from_agent, to_agent)` pair and
enforces minimum interval + burst limit. Writes a rate-limit event to
`~/wiki/memory/` when a limit triggers.

Env vars
--------
HERMES_DISPATCH_MIN_INTERVAL_SEC: default 30 (minimum between consecutive dispatches)
HERMES_DISPATCH_BURST_COUNT:      default 3 (max dispatches per window)
HERMES_DISPATCH_BURST_WINDOW_SEC: default 60 (burst window length)
HERMES_DISPATCH_STRICT:           if "1", halve burst and double interval
HERMES_DISPATCH_THROTTLE:         "off" disables enforcement (bypass for tests)
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

_LOCK = threading.Lock()

# (from_agent, to_agent) -> deque of recent dispatch timestamps (epoch seconds)
_DISPATCH_LOG: Dict[Tuple[str, str], Deque[float]] = {}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _config() -> Dict[str, int]:
    min_interval = _int_env("HERMES_DISPATCH_MIN_INTERVAL_SEC", 30)
    burst_count = _int_env("HERMES_DISPATCH_BURST_COUNT", 3)
    burst_window = _int_env("HERMES_DISPATCH_BURST_WINDOW_SEC", 60)
    if os.environ.get("HERMES_DISPATCH_STRICT", "").strip() == "1":
        min_interval = max(min_interval, 60)
        burst_count = max(1, burst_count - 1)
    return {
        "min_interval_sec": min_interval,
        "burst_count": burst_count,
        "burst_window_sec": burst_window,
    }


def enforcement_enabled() -> bool:
    return os.environ.get("HERMES_DISPATCH_THROTTLE", "on").lower() != "off"


def check(from_agent: str, to_agent: str) -> Tuple[bool, Optional[str], Dict[str, int]]:
    """Check whether a dispatch from `from_agent` → `to_agent` is allowed.

    Returns (allowed, reason_if_blocked, stats_dict).
    - reason_if_blocked is a human-readable explanation.
    - stats_dict carries 'since_last_sec' + 'burst_seen' + config snapshot.
    """
    cfg = _config()
    now = time.time()
    key = (from_agent, to_agent)

    with _LOCK:
        dq = _DISPATCH_LOG.setdefault(key, deque(maxlen=32))
        # Drop entries outside burst window
        while dq and now - dq[0] > cfg["burst_window_sec"]:
            dq.popleft()

        since_last = (now - dq[-1]) if dq else float("inf")
        burst_seen = len(dq)

        stats = {
            "since_last_sec": round(since_last, 1) if since_last != float("inf") else None,
            "burst_seen": burst_seen,
            **cfg,
        }

        if since_last < cfg["min_interval_sec"]:
            reason = (
                f"§9 throttle: {round(cfg['min_interval_sec'] - since_last, 1)}s until "
                f"next {from_agent}→{to_agent} dispatch allowed "
                f"(min interval {cfg['min_interval_sec']}s)"
            )
            return (False, reason, stats)

        if burst_seen >= cfg["burst_count"]:
            reason = (
                f"§9 burst: {burst_seen} dispatches in last {cfg['burst_window_sec']}s "
                f"(cap {cfg['burst_count']})"
            )
            return (False, reason, stats)

    return (True, None, stats)


def record(from_agent: str, to_agent: str) -> None:
    """Record a successful dispatch so future checks can see it."""
    with _LOCK:
        key = (from_agent, to_agent)
        dq = _DISPATCH_LOG.setdefault(key, deque(maxlen=32))
        dq.append(time.time())


def log_rate_limit_event(from_agent: str, to_agent: str, reason: str, stats: Dict) -> Optional[Path]:
    """Write a rate-limit event file to ~/wiki/memory/ per §9."""
    memdir = Path.home() / "wiki" / "memory"
    if not memdir.exists():
        return None
    ts_iso = datetime.now(timezone(timedelta(hours=8))).isoformat()
    ts_file = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    path = memdir / f"{ts_file}_ratelimit_event.md"
    # Append mode: one file per day, multiple entries
    body = (
        f"\n## {ts_iso}\n"
        f"- direction: `{from_agent} → {to_agent}`\n"
        f"- reason: {reason}\n"
        f"- stats: `{json.dumps(stats, ensure_ascii=False)}`\n"
    )
    if not path.exists():
        header = (
            f"---\n"
            f"title: Rate-limit event log {ts_file}\n"
            f"created: {ts_iso}\n"
            f"type: event-log\n"
            f"tags: [ratelimit, throttle, se-9, agent-bus]\n"
            f"---\n\n"
            f"# Rate-limit event log {ts_file}\n\n"
            f"Auto-generated when §9 throttle blocks a dispatch.\n"
        )
        path.write_text(header + body, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(body)
    return path


def check_and_record(from_agent: str, to_agent: str) -> Tuple[bool, Optional[str], Dict]:
    """Convenience: check, then if allowed record; if blocked log event.

    Returns (allowed, reason, stats).
    If throttle disabled via env, always allows (still records).
    """
    if not enforcement_enabled():
        record(from_agent, to_agent)
        return (True, None, {"enforcement": "off"})

    allowed, reason, stats = check(from_agent, to_agent)
    if allowed:
        record(from_agent, to_agent)
    else:
        log_rate_limit_event(from_agent, to_agent, reason or "blocked", stats)
    return (allowed, reason, stats)


__all__ = [
    "check",
    "record",
    "check_and_record",
    "log_rate_limit_event",
    "enforcement_enabled",
]

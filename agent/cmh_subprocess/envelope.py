"""Profile-aware envelope tracking for local subprocess wrapper foundations."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

ENVELOPE_STATE_FILENAME = "envelope_tracking.json"
WINDOW_DURATION = timedelta(hours=5)

_DEFAULT_STATE: dict[str, dict[str, Any]] = {
    "anthropic_max": {
        "envelope_total_messages_per_5h": 225,
        "envelope_allocation_hermes_pct": 85,
        "envelope_messages_used_5h": 0,
        "window_start_iso": None,
        "last_invocation_iso": None,
        "halt_flag_active": False,
    },
    "chatgpt_pro": {
        "envelope_total_messages_per_5h": 200,
        "envelope_allocation_hermes_pct": 85,
        "envelope_messages_used_5h": 0,
        "window_start_iso": None,
        "last_invocation_iso": None,
        "halt_flag_active": False,
    },
}


@dataclass(frozen=True)
class EnvelopeDecision:
    allowed: bool
    reason: str
    used: int
    cap: int
    available: int


def envelope_state_path() -> Path:
    return get_hermes_home() / "state" / ENVELOPE_STATE_FILENAME


def default_envelope_state() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(_DEFAULT_STATE)


def allocation_cap(record: dict[str, Any]) -> int:
    total = int(record.get("envelope_total_messages_per_5h", 0))
    pct = int(record.get("envelope_allocation_hermes_pct", 0))
    return (total * pct) // 100


def load_envelope_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    state_path = path or envelope_state_path()
    if not state_path.exists():
        return default_envelope_state()
    with state_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Envelope state must be a JSON object, got {type(data).__name__}")
    state = default_envelope_state()
    for key, defaults in state.items():
        if isinstance(data.get(key), dict):
            defaults.update(data[key])
    return state


def save_envelope_state(state: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    state_path = path or envelope_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=state_path.parent,
            prefix=f".{state_path.name}.",
            suffix=".tmp",
        ) as handle:
            tmp_path = handle.name
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, state_path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def increment_usage(
    state: dict[str, dict[str, Any]],
    envelope_name: str,
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    updated = copy.deepcopy(state)
    record = updated[envelope_name]
    window_start = _parse_iso(record.get("window_start_iso"))
    if window_start is None or current - window_start >= WINDOW_DURATION:
        record["window_start_iso"] = current.isoformat()
        record["envelope_messages_used_5h"] = 0
    record["envelope_messages_used_5h"] = int(record.get("envelope_messages_used_5h", 0)) + 1
    record["last_invocation_iso"] = current.isoformat()
    return updated


def check_budget(
    state: dict[str, dict[str, Any]],
    envelope_name: str,
    *,
    priority: bool = False,
    now: datetime | None = None,
) -> EnvelopeDecision:
    record = state[envelope_name]
    current = now or datetime.now(timezone.utc)
    window_start = _parse_iso(record.get("window_start_iso"))
    cap = allocation_cap(record)

    if window_start is not None and current - window_start >= WINDOW_DURATION:
        return EnvelopeDecision(True, "window_reset", 0, cap, cap)

    used = int(record.get("envelope_messages_used_5h", 0))
    available = max(cap - used, 0)
    if used >= cap and not priority:
        return EnvelopeDecision(False, "budget_blocked", used, cap, available)
    if used >= cap and priority:
        return EnvelopeDecision(True, "priority_override", used, cap, available)
    return EnvelopeDecision(True, "within_budget", used, cap, available)

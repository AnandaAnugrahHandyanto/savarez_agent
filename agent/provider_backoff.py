"""Provider-wide transient backoff helpers.

This module intentionally stores only coarse runtime state (timestamps,
provider/model labels, reason strings).  It never stores request payloads,
responses, credentials, base URLs, or any secret-bearing material.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home

DEFAULT_WINDOW_SECONDS = 600
DEFAULT_THRESHOLD = 3
DEFAULT_BACKOFF_SECONDS = 300

_RUNTIME_DIR_NAME = "provider_backoff"
_SLUG_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _slug(value: str) -> str:
    value = (value or "unknown").strip() or "unknown"
    return _SLUG_RE.sub("_", value)[:96]


def provider_backoff_dir() -> Path:
    """Return the Hermes runtime directory for provider backoff state."""
    return get_hermes_home() / "runtime" / _RUNTIME_DIR_NAME


def provider_backoff_path(provider: str, model: Optional[str] = None) -> Path:
    """Return the state file path for a provider/model pair."""
    provider_slug = _slug(provider)
    model_slug = _slug(model or "all")
    return provider_backoff_dir() / f"{provider_slug}__{model_slug}.json"


def _read_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def record_provider_stall(
    provider: str,
    model: Optional[str] = None,
    *,
    reason: str = "transport_stall",
    now: Optional[float] = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    threshold: int = DEFAULT_THRESHOLD,
    backoff_seconds: int = DEFAULT_BACKOFF_SECONDS,
) -> int:
    """Record a transient provider stall and return active backoff seconds.

    The backoff trips when ``threshold`` stalls for the same provider/model are
    seen inside ``window_seconds``.  Return value is 0 when no backoff is active.
    """
    provider = (provider or "unknown").strip() or "unknown"
    model = (model or "all").strip() or "all"
    now_i = int(now if now is not None else time.time())
    path = provider_backoff_path(provider, model)
    state = _read_state(path)
    raw_events = state.get("events", [])
    events: list[int] = []
    cutoff = now_i - max(1, int(window_seconds))
    if isinstance(raw_events, list):
        for item in raw_events:
            try:
                ts = int(item)
            except (TypeError, ValueError):
                continue
            if ts >= cutoff:
                events.append(ts)
    events.append(now_i)

    backoff_until = int(state.get("backoff_until") or 0)
    if len(events) >= max(1, int(threshold)):
        backoff_until = max(backoff_until, now_i + max(1, int(backoff_seconds)))

    state = {
        "provider": provider,
        "model": model,
        "events": events[-50:],
        "backoff_until": backoff_until,
        "last_reason": str(reason or "transport_stall")[:160],
        "updated_at": now_i,
        "window_seconds": int(window_seconds),
        "threshold": int(threshold),
        "backoff_seconds": int(backoff_seconds),
    }
    _atomic_write(path, state)
    return max(0, backoff_until - now_i)


def provider_backoff_remaining(
    provider: str,
    model: Optional[str] = None,
    *,
    now: Optional[float] = None,
) -> int:
    """Return remaining provider backoff seconds, or 0 when inactive."""
    now_i = int(now if now is not None else time.time())
    state = _read_state(provider_backoff_path(provider, model or "all"))
    try:
        until = int(state.get("backoff_until") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, until - now_i)


def clear_provider_backoff(provider: str, model: Optional[str] = None) -> None:
    """Remove a provider/model backoff state file if it exists."""
    try:
        provider_backoff_path(provider, model or "all").unlink()
    except FileNotFoundError:
        pass

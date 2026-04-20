"""Persistent provider health state with TTL-backed temporary degradation.

This module stores provider cooldown state in ~/.hermes/provider_health/
so all Hermes entry points (CLI, gateway, cron, ACP) can share the same
view of temporarily degraded providers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

_STATE_SUBDIR = "provider_health"
_DEFAULT_BASE_COOLDOWN_SECONDS = 900.0   # 15m
_DEFAULT_MAX_COOLDOWN_SECONDS = 86400.0   # 24h


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home()
    except Exception:
        return Path.home() / ".hermes"


def _state_dir() -> Path:
    return _hermes_home() / _STATE_SUBDIR


def _provider_slug(provider: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (provider or "").strip().lower())
    slug = slug.strip("-")
    return slug or "unknown"


def _state_path(provider: str) -> Path:
    return _state_dir() / f"{_provider_slug(provider)}.json"


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _default_base_cooldown_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("HERMES_PROVIDER_HEALTH_BASE_COOLDOWN_SECONDS", _DEFAULT_BASE_COOLDOWN_SECONDS)))
    except (TypeError, ValueError):
        return _DEFAULT_BASE_COOLDOWN_SECONDS


def _default_max_cooldown_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("HERMES_PROVIDER_HEALTH_MAX_COOLDOWN_SECONDS", _DEFAULT_MAX_COOLDOWN_SECONDS)))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_COOLDOWN_SECONDS


def _casefold_headers(headers: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if not headers:
        return {}
    return {str(key).lower(): value for key, value in headers.items()}


def _parse_retry_after_seconds(headers: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not headers:
        return None

    lowered = _casefold_headers(headers)
    for key in (
        "x-ratelimit-reset-requests-1h",
        "x-ratelimit-reset-requests",
        "retry-after",
    ):
        raw = lowered.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
            if value > 0:
                return value
        except (TypeError, ValueError):
            continue
    return None


def _extract_reset_seconds(error_context: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not isinstance(error_context, Mapping):
        return None

    for key in ("reset_seconds", "retry_after_seconds"):
        raw = error_context.get(key)
        try:
            value = float(raw)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass

    raw_reset_at = error_context.get("reset_at")
    try:
        reset_at = float(raw_reset_at)
    except (TypeError, ValueError):
        return None
    remaining = reset_at - time.time()
    return remaining if remaining > 0 else None


def _coerce_error_summary(error_context: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(error_context, Mapping):
        return None

    for key in ("message", "error", "summary", "detail", "error_summary"):
        raw = error_context.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()[:500]
    return None


def peek_provider_health_state(provider: str) -> Optional[dict[str, Any]]:
    """Return the raw persisted health state without expiring it."""
    return _read_json(_state_path(provider))


def load_provider_health_state(provider: str) -> Optional[dict[str, Any]]:
    """Return the active health state for a provider, or None if healthy."""
    path = _state_path(provider)
    state = _read_json(path)
    if not state:
        return None

    now = time.time()
    degraded_until = state.get("degraded_until")
    try:
        degraded_until_f = float(degraded_until)
    except (TypeError, ValueError):
        degraded_until_f = 0.0

    remaining = degraded_until_f - now
    if remaining <= 0:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None

    state["remaining_seconds"] = remaining
    return state


def provider_degraded_remaining(provider: str) -> Optional[float]:
    """Return seconds remaining on a provider cooldown, or None if healthy."""
    state = load_provider_health_state(provider)
    if not state:
        return None
    remaining = state.get("remaining_seconds")
    try:
        remaining_f = float(remaining)
    except (TypeError, ValueError):
        return None
    return remaining_f if remaining_f > 0 else None


def is_provider_degraded(provider: str) -> bool:
    return provider_degraded_remaining(provider) is not None


def format_remaining(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def clear_provider_degradation(provider: str) -> None:
    try:
        os.unlink(_state_path(provider))
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.debug("Failed to clear provider health state for %s: %s", provider, exc)


def record_provider_degradation(
    provider: str,
    *,
    reason: str,
    status_code: Optional[int] = None,
    headers: Optional[Mapping[str, Any]] = None,
    error_context: Optional[Mapping[str, Any]] = None,
    base_cooldown_seconds: Optional[float] = None,
    max_cooldown_seconds: Optional[float] = None,
) -> dict[str, Any]:
    """Persist a temporary degradation window for a provider.

    The TTL starts at the header-derived retry/reset time when available.
    Otherwise it uses an exponential backoff with a 15m base and 24h cap.
    Repeated failures extend the existing cooldown rather than replacing it.
    """
    provider = (provider or "").strip().lower()
    if not provider:
        raise ValueError("provider is required")

    now = time.time()
    path = _state_path(provider)
    current = _read_json(path) or {}

    try:
        current_until = float(current.get("degraded_until", 0.0))
    except (TypeError, ValueError):
        current_until = 0.0

    try:
        current_failures = int(current.get("failure_count", 0))
    except (TypeError, ValueError):
        current_failures = 0

    if current_until > now:
        failure_count = current_failures + 1
        degraded_from = float(current.get("degraded_at", now))
    else:
        failure_count = 1
        degraded_from = now
        current_until = now

    base = _default_base_cooldown_seconds() if base_cooldown_seconds is None else max(1.0, float(base_cooldown_seconds))
    cap = _default_max_cooldown_seconds() if max_cooldown_seconds is None else max(1.0, float(max_cooldown_seconds))

    retry_after_seconds = _parse_retry_after_seconds(headers)
    if retry_after_seconds is None:
        retry_after_seconds = _extract_reset_seconds(error_context)

    backoff_seconds = min(base * (2 ** max(0, failure_count - 1)), cap)
    cooldown_seconds = backoff_seconds
    if retry_after_seconds is not None and retry_after_seconds > 0:
        cooldown_seconds = min(max(retry_after_seconds, backoff_seconds), cap)

    degraded_until = max(current_until, now) + cooldown_seconds
    summary = _coerce_error_summary(error_context)

    state = {
        "provider": provider,
        "reason": reason,
        "status_code": status_code,
        "failure_count": failure_count,
        "degraded_at": degraded_from,
        "last_failure_at": now,
        "degraded_until": degraded_until,
        "cooldown_seconds": cooldown_seconds,
        "retry_after_seconds": retry_after_seconds,
        "max_cooldown_seconds": cap,
    }
    if summary:
        state["last_error"] = summary
    if isinstance(error_context, Mapping) and error_context:
        compact_context = {}
        for key in ("message", "error_type", "error_code", "request_id", "reset_at", "retry_after", "reset_seconds"):
            value = error_context.get(key)
            if value is not None:
                compact_context[key] = value
        if compact_context:
            state["error_context"] = compact_context

    try:
        _atomic_write(path, state)
        logger.info(
            "Provider %s marked degraded for %.0fs (reason=%s, failures=%d)",
            provider,
            cooldown_seconds,
            reason,
            failure_count,
        )
    except Exception as exc:
        logger.debug("Failed to write provider health state for %s: %s", provider, exc)

    return state


def provider_health_summary(provider: str) -> Optional[dict[str, Any]]:
    """Return the raw health state, including remaining seconds, if degraded."""
    return load_provider_health_state(provider)

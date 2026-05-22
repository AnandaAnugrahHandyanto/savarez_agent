"""Append redacted provider/fallback/safety telemetry events.

The runtime calls this module from hot error/fallback paths, so every public
function is deliberately best-effort: telemetry must never break an agent turn.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

DEFAULT_LOG_NAME = "provider-failover.log"
CANONICAL_SCHEMA = "hermes.provider-failover.v2"
MAX_STRING_LENGTH = 500

REQUIRED_FIELDS = (
    "schema",
    "ts",
    "event",
    "session_id",
    "platform",
    "role",
    "domain",
    "task",
    "provider",
    "model",
    "engine",
    "status",
    "resolution",
    "failure_kind",
    "fallback",
    "latency_ms",
    "retry_count",
    "input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "safety_rail_tripped",
    "manual_rescue",
    "notes",
)

_ALLOWED_FAILURE_KINDS = {
    "none",
    "rate_limit",
    "billing",
    "auth",
    "overloaded",
    "context_overflow",
    "provider_error",
    "safety",
    "timeout",
    "payload_too_large",
    "model_not_found",
    "unknown",
}
_ALLOWED_STATUSES = {
    "started",
    "completed",
    "failed",
    "blocked",
    "fallback_activated",
}
_ALLOWED_RESOLUTIONS = {
    "pass",
    "fail",
    "blocked",
    "fallback",
    "manual_rescue",
    "required",
    "unknown",
}

_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s&,'\"]+"),
    re.compile(r"(?i)(token\s*[=:]\s*)[^\s&,'\"]+"),
    re.compile(r"(?i)(password\s*[=:]\s*)[^\s&,'\"]+"),
    re.compile(r"(?i)(secret\s*[=:]\s*)[^\s&,'\"]+"),
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_log_path() -> Path:
    # Keep this import lazy: telemetry must remain importable in embedded/test
    # contexts where runtime constants are stubbed or partially initialized.
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home()) / "logs" / DEFAULT_LOG_NAME


def redact_value(value: Any) -> Any:
    """Return *value* with obvious secrets removed and large strings bounded."""
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        # Catch very long high-entropy-ish fragments that are commonly bearer
        # tokens but avoid mangling normal prose.
        redacted = re.sub(r"\b[A-Za-z0-9_-]{80,}\b", "[REDACTED_LONG_TOKEN]", redacted)
        if len(redacted) > MAX_STRING_LENGTH:
            return redacted[:MAX_STRING_LENGTH] + "…[truncated]"
        return redacted
    if isinstance(value, Mapping):
        return {str(redact_value(k)): redact_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact_value(v) for v in value]
    return value


def _coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _coerce_failure_kind(value: Any) -> str:
    failure_kind = str(value or "none").strip().lower()
    if failure_kind == "quota":
        failure_kind = "rate_limit"
    elif failure_kind == "safety_block":
        failure_kind = "safety"
    elif failure_kind == "fallback":
        failure_kind = "provider_error"
    elif failure_kind == "tool_error":
        failure_kind = "unknown"
    return failure_kind if failure_kind in _ALLOWED_FAILURE_KINDS else "unknown"


def sanitize_event(event: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize an event to the provider telemetry v2 JSONL schema."""
    raw = redact_value(dict(event or {}))
    status = str(raw.get("status") or "completed").strip().lower()
    if status not in _ALLOWED_STATUSES:
        status = "failed" if status in {"error", "errored"} else "completed"
    resolution = str(raw.get("resolution") or "pass").strip().lower()
    if resolution not in _ALLOWED_RESOLUTIONS:
        resolution = "unknown"

    sanitized = {
        "schema": str(raw.get("schema") or CANONICAL_SCHEMA),
        "ts": str(raw.get("ts") or _now_utc()),
        "event": str(raw.get("event") or "provider_request_end"),
        "session_id": raw.get("session_id"),
        "platform": str(raw.get("platform") or "unknown"),
        "role": str(raw.get("role") or "executor"),
        "domain": str(raw.get("domain") or "unknown"),
        "task": raw.get("task"),
        "provider": str(raw.get("provider") or "unknown"),
        "model": str(raw.get("model") or "unknown"),
        "engine": str(raw.get("engine") or "hermes-runtime"),
        "status": status,
        "resolution": resolution,
        "failure_kind": _coerce_failure_kind(raw.get("failure_kind")),
        "fallback": raw.get("fallback"),
        "latency_ms": _coerce_int(raw.get("latency_ms")),
        "retry_count": _coerce_int(raw.get("retry_count")),
        "input_tokens": _coerce_int(raw.get("input_tokens")),
        "output_tokens": _coerce_int(raw.get("output_tokens")),
        "estimated_cost_usd": raw.get("estimated_cost_usd"),
        "safety_rail_tripped": _coerce_bool(raw.get("safety_rail_tripped")),
        "manual_rescue": _coerce_bool(raw.get("manual_rescue")),
        "notes": str(raw.get("notes") or ""),
    }

    # Preserve explicitly supplied non-secret diagnostic fields after the
    # canonical fields. This lets tests and operators carry status_code/reason
    # without expanding the required schema every time.
    for key, value in raw.items():
        if key not in sanitized:
            sanitized[str(key)] = value
    return sanitized


def append_provider_event(event: Mapping[str, Any] | None, path: str | Path | None = None) -> None:
    """Append a sanitized JSONL event, swallowing all telemetry failures."""
    try:
        sanitized = sanitize_event(event)
        log_path = Path(path).expanduser() if path is not None else _default_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitized, sort_keys=True, separators=(",", ":")) + "\n")
    except Exception as exc:  # pragma: no cover - exact OS errors vary
        logger.warning("provider telemetry append failed: %s", exc, exc_info=logger.isEnabledFor(logging.DEBUG))


__all__ = [
    "CANONICAL_SCHEMA",
    "REQUIRED_FIELDS",
    "append_provider_event",
    "redact_value",
    "sanitize_event",
]

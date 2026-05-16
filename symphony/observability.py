"""Small observability helpers for Symphony state and event snapshots."""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any

ClockMs = Any

_SECRET_KEY_PARTS = frozenset({"api", "key", "apikey", "token", "secret", "password", "credential", "credentials"})
_SECRET_PATTERN = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*([^\s,;]+)")


def _system_now_ms() -> int:
    return int(time.time() * 1000)


class EventBuffer:
    """Deterministic structured event ring buffer."""

    def __init__(self, *, capacity: int = 200, max_message_chars: int = 500, clock_ms: ClockMs | None = None):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if max_message_chars < 1:
            raise ValueError("max_message_chars must be >= 1")
        self.capacity = capacity
        self.max_message_chars = max_message_chars
        self._clock_ms = clock_ms or _system_now_ms
        self._events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._seq = 0

    def record(
        self,
        level: str,
        message: Any,
        *,
        issue_id: str | None = None,
        issue_identifier: str | None = None,
        session_id: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append and return one structured event."""

        self._seq += 1
        event: dict[str, Any] = {
            "seq": self._seq,
            "ts_ms": int(self._clock_ms()),
            "level": str(level),
            "message": _truncate(_redact_message(str(message)), self.max_message_chars),
        }
        if issue_id is not None:
            event["issue_id"] = issue_id
        if issue_identifier is not None:
            event["issue_identifier"] = issue_identifier
        if session_id is not None:
            event["session_id"] = session_id
        if extra:
            event["extra"] = _redact_mapping(extra)
        self._events.append(event)
        return dict(event)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a JSON-serializable copy of retained events, oldest first."""

        return [_copy_jsonish(event) for event in self._events]

    def __len__(self) -> int:
        return len(self._events)


def build_state_snapshot(orchestrator_state: Any, *, events: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Build the stable state shape intended for `hermes symphony state --json`."""

    event_rows = [_copy_jsonish(event) for event in (events or [])]
    running_rows = [_running_row(issue_id, running) for issue_id, running in orchestrator_state.running.items()]
    retry_rows = [_retry_row(issue_id, retry, orchestrator_state.now_ms()) for issue_id, retry in orchestrator_state.retries.items()]
    latest_errors = [event for event in event_rows if str(event.get("level", "")).casefold() in {"error", "exception"}]
    evidence_dirs = {
        row["issue_id"]: row["evidence_dir"]
        for row in running_rows
        if row.get("issue_id") is not None and row.get("evidence_dir") is not None
    }

    return {
        "counts": {
            "running": len(running_rows),
            "retrying": len(retry_rows),
            "events": len(event_rows),
            "latest_errors": len(latest_errors),
        },
        "running": running_rows,
        "retrying": retry_rows,
        "totals": {"running": len(running_rows), "retrying": len(retry_rows)},
        "latest_errors": latest_errors[-10:],
        "events": event_rows,
        "evidence_dirs": evidence_dirs,
    }


def _running_row(issue_id: str, running: Any) -> dict[str, Any]:
    issue = getattr(running, "issue", None)
    runner = getattr(running, "runner", None)
    workspace = getattr(running, "workspace", None)
    return {
        "issue_id": getattr(issue, "id", issue_id),
        "issue_identifier": getattr(issue, "identifier", None),
        "title": getattr(issue, "title", None),
        "state": getattr(issue, "state", None),
        "session_id": _get_attr_or_key(runner, "session_id"),
        "workspace": _workspace_path(workspace),
        "evidence_dir": _get_attr_or_key(workspace, "evidence_dir"),
    }


def _retry_row(issue_id: str, retry: Any, now_ms: int) -> dict[str, Any]:
    retry_after_ms = int(getattr(retry, "retry_after_ms"))
    return {
        "issue_id": issue_id,
        "attempt": getattr(retry, "attempt"),
        "retry_after_ms": retry_after_ms,
        "retry_in_ms": max(0, retry_after_ms - int(now_ms)),
    }


def _workspace_path(workspace: Any) -> str | None:
    path = _get_attr_or_key(workspace, "path")
    if path is not None:
        return str(path)
    if isinstance(workspace, str):
        return workspace
    return None


def _get_attr_or_key(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _redact_message(message: str) -> str:
    return _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", message)


def _redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = str(key)
        if _is_secret_key(key_text):
            redacted[key_text] = "[REDACTED]"
        elif isinstance(value, Mapping):
            redacted[key_text] = _redact_mapping(value)
        elif isinstance(value, str):
            redacted[key_text] = _redact_message(value)
        else:
            redacted[key_text] = value
    return redacted


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    if not normalized:
        return False
    parts = {part for part in normalized.split("_") if part}
    return (
        normalized in _SECRET_KEY_PARTS
        or "token" in parts
        or "secret" in parts
        or "password" in parts
        or "apikey" in parts
        or "token" in normalized
        or "secret" in normalized
        or "password" in normalized
        or "apikey" in normalized
        or ({"api", "key"} <= parts)
    )


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars == 1:
        return "…"
    return value[: max_chars - 1] + "…"


def _copy_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _copy_jsonish(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_jsonish(item) for item in value]
    if isinstance(value, tuple):
        return [_copy_jsonish(item) for item in value]
    return value

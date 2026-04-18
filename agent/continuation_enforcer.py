"""Continuation queue + delegation loop guard for Hermes orchestration.

Phase 2 builds on the lightweight orchestration state added in Phase 1.
This module keeps a small durable queue of sessions that ended with open work,
and exposes a simple circuit breaker for repeated delegated-child failures.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.orchestration_state import get_session_state
from hermes_constants import get_hermes_dir

_QUEUE_LOCK = threading.RLock()
_ACTIVE_TODO_STATUSES = {"pending", "in_progress"}
_DELEGATION_FAILURE_STATUSES = {"failed", "error", "interrupted", "blocked"}
_MAX_CONSECUTIVE_DELEGATION_FAILURES = 3
_MAX_PREVIEW_CHARS = 500
_DEFAULT_RETRY_LEASE_SECONDS = 300
_DEFAULT_MAX_RETRY_AGE_SECONDS = 6 * 60 * 60
_DEFAULT_MAX_AUTO_RESUME_ATTEMPTS = 3
_MAX_CONTINUATION_EVENTS = 25


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _iso_from_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clear_retry_runtime_fields(item: Dict[str, Any]) -> None:
    for key in ("leaseOwner", "leaseClaimedAt", "leaseExpiresAt"):
        item.pop(key, None)


def _append_event(
    item: Dict[str, Any],
    event_type: str,
    message: Optional[str],
    *,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    events = item.get("events")
    if not isinstance(events, list):
        events = []
        item["events"] = events
    entry: Dict[str, Any] = {
        "type": str(event_type or "event").strip() or "event",
        "timestamp": timestamp or _now_iso(),
        "message": _truncate_preview(message) or "Continuation updated.",
    }
    if metadata:
        clean_metadata = {
            str(key): value
            for key, value in metadata.items()
            if value is not None
        }
        if clean_metadata:
            entry["metadata"] = clean_metadata
    events.append(entry)
    if len(events) > _MAX_CONTINUATION_EVENTS:
        item["events"] = events[-_MAX_CONTINUATION_EVENTS:]


def _truncate_preview(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= _MAX_PREVIEW_CHARS:
        return text
    return text[:_MAX_PREVIEW_CHARS].rstrip() + "…"


def _queue_dir() -> Path:
    directory = get_hermes_dir("runtime/orchestration", "orchestration_state")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _queue_path() -> Path:
    return _queue_dir() / "continuations.json"


def _normalize_todo(item: Dict[str, Any]) -> Dict[str, str]:
    status = str(item.get("status", "pending")).strip().lower()
    return {
        "id": str(item.get("id", "")).strip() or "?",
        "content": str(item.get("content", "")).strip() or "(no description)",
        "status": status or "pending",
    }


def _active_todos(todos: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [
        _normalize_todo(item)
        for item in todos or []
        if str(item.get("status", "")).strip().lower() in _ACTIVE_TODO_STATUSES
    ]


def _read_queue() -> Dict[str, Any]:
    path = _queue_path()
    if not path.exists():
        return {"items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            items = payload.get("items")
            payload["items"] = items if isinstance(items, list) else []
            return payload
    except Exception:
        pass
    return {"items": []}


def _write_queue(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _queue_path()
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return payload


def get_pending_continuations() -> List[Dict[str, Any]]:
    with _QUEUE_LOCK:
        payload = _read_queue()
        items = [item for item in payload.get("items", []) if isinstance(item, dict) and item.get("status") == "pending"]
        items.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
        return items


def get_continuation_record(session_id: str) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return None
    with _QUEUE_LOCK:
        payload = _read_queue()
        for item in payload.get("items", []):
            if isinstance(item, dict) and item.get("sessionId") == normalized_session_id:
                return dict(item)
    return None


def append_continuation_event(
    session_id: str,
    event_type: str,
    message: Optional[str],
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    now = _now_iso()
    with _QUEUE_LOCK:
        payload = _read_queue()
        items = payload.setdefault("items", [])
        existing = next((item for item in items if item.get("sessionId") == normalized_session_id), None)
        if existing is None:
            return None
        _append_event(existing, event_type, message, timestamp=now, metadata=metadata)
        existing["updatedAt"] = now
        _write_queue(payload)
        return dict(existing)


def request_continuation_retry(
    session_id: str,
    *,
    requested_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    now = _now_iso()
    with _QUEUE_LOCK:
        payload = _read_queue()
        items = payload.setdefault("items", [])
        existing = next((item for item in items if item.get("sessionId") == normalized_session_id), None)
        if existing is None or not (existing.get("openTodos") or []):
            return None

        existing["status"] = "retry_requested"
        existing["retryRequestedAt"] = now
        existing["updatedAt"] = now
        existing["requestedBy"] = str(requested_by or "").strip() or existing.get("requestedBy")
        existing["retryRequestCount"] = int(existing.get("retryRequestCount") or 0) + 1
        existing.pop("resolution", None)
        _clear_retry_runtime_fields(existing)
        _append_event(
            existing,
            "retry_requested",
            f"Retry requested by {existing.get('requestedBy') or 'operator'}.",
            timestamp=now,
            metadata={"requested_by": existing.get("requestedBy")},
        )
        _write_queue(payload)
        return dict(existing)


def block_continuation(
    session_id: str,
    *,
    resolution: str,
) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    now = _now_iso()
    with _QUEUE_LOCK:
        payload = _read_queue()
        items = payload.setdefault("items", [])
        existing = next((item for item in items if item.get("sessionId") == normalized_session_id), None)
        if existing is None:
            return None

        existing["status"] = "blocked"
        existing["resolution"] = str(resolution or "blocked").strip() or "blocked"
        existing["updatedAt"] = now
        _clear_retry_runtime_fields(existing)
        _append_event(existing, "blocked", str(existing.get("resolution") or "blocked"), timestamp=now)
        _write_queue(payload)
        return dict(existing)


def release_continuation_claim(
    session_id: str,
    worker_id: str,
    *,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    normalized_worker_id = str(worker_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")
    if not normalized_worker_id:
        raise ValueError("worker_id is required")

    now = _now_iso()
    with _QUEUE_LOCK:
        payload = _read_queue()
        items = payload.setdefault("items", [])
        existing = next((item for item in items if item.get("sessionId") == normalized_session_id), None)
        if existing is None:
            return None
        if str(existing.get("leaseOwner") or "").strip() not in ("", normalized_worker_id):
            return None

        existing["status"] = "retry_requested"
        existing["updatedAt"] = now
        if reason:
            existing["lastReleaseReason"] = str(reason).strip()
        _clear_retry_runtime_fields(existing)
        _append_event(existing, "retry_released", str(reason or "released"), timestamp=now, metadata={"worker_id": normalized_worker_id})
        _write_queue(payload)
        return dict(existing)


def claim_retry_requested_continuation(
    worker_id: str,
    *,
    lease_seconds: int = _DEFAULT_RETRY_LEASE_SECONDS,
    max_retry_age_seconds: int = _DEFAULT_MAX_RETRY_AGE_SECONDS,
    max_auto_resume_attempts: int = _DEFAULT_MAX_AUTO_RESUME_ATTEMPTS,
) -> Optional[Dict[str, Any]]:
    normalized_worker_id = str(worker_id or "").strip()
    if not normalized_worker_id:
        raise ValueError("worker_id is required")

    now = _now_iso()
    now_dt = _parse_iso(now) or datetime.now(timezone.utc)

    with _QUEUE_LOCK:
        payload = _read_queue()
        items = payload.setdefault("items", [])
        dirty = False
        candidates: List[Dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            status = str(item.get("status") or "").strip().lower()
            if status == "running":
                lease_expires_at = _parse_iso(item.get("leaseExpiresAt"))
                if lease_expires_at and lease_expires_at > now_dt:
                    continue
                item["status"] = "retry_requested"
                item["updatedAt"] = now
                _clear_retry_runtime_fields(item)
                dirty = True
                status = "retry_requested"

            if status != "retry_requested":
                continue

            retry_requested_at = _parse_iso(item.get("retryRequestedAt") or item.get("updatedAt") or item.get("createdAt"))
            if (
                max_retry_age_seconds >= 0
                and retry_requested_at is not None
                and (now_dt - retry_requested_at).total_seconds() > max_retry_age_seconds
            ):
                item["status"] = "blocked"
                item["resolution"] = "retry_request_expired"
                item["updatedAt"] = now
                _clear_retry_runtime_fields(item)
                _append_event(item, "blocked", "retry_request_expired", timestamp=now)
                dirty = True
                continue

            if max_auto_resume_attempts >= 0 and int(item.get("resumeCount") or 0) >= max_auto_resume_attempts:
                item["status"] = "blocked"
                item["resolution"] = "max_auto_resume_attempts_exceeded"
                item["updatedAt"] = now
                _clear_retry_runtime_fields(item)
                _append_event(item, "blocked", "max_auto_resume_attempts_exceeded", timestamp=now)
                dirty = True
                continue

            candidates.append(item)

        candidates.sort(key=lambda item: str(item.get("retryRequestedAt") or item.get("updatedAt") or item.get("createdAt") or ""))
        if not candidates:
            if dirty:
                _write_queue(payload)
            return None

        claimed = candidates[0]
        claimed["status"] = "running"
        claimed["leaseOwner"] = normalized_worker_id
        claimed["leaseClaimedAt"] = now
        claimed["leaseExpiresAt"] = _iso_from_datetime(now_dt + timedelta(seconds=max(int(lease_seconds or 0), 1)))
        claimed["resumeCount"] = int(claimed.get("resumeCount") or 0) + 1
        claimed["lastResumedAt"] = now
        claimed["updatedAt"] = now
        claimed.pop("resolution", None)
        _append_event(claimed, "auto_resume_claimed", f"Claimed by {normalized_worker_id}.", timestamp=now, metadata={"worker_id": normalized_worker_id})
        _write_queue(payload)
        return dict(claimed)


def reconcile_session_continuation(
    session_id: str,
    *,
    outcome_status: str,
    todos: List[Dict[str, Any]] | None,
    response_preview: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create/update/remove pending continuation state for a finished session.

    Returns the pending record when one exists after reconciliation, otherwise None.
    """
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    active_todos = _active_todos(todos or [])
    normalized_status = str(outcome_status or "failed").strip().lower() or "failed"
    now = _now_iso()

    with _QUEUE_LOCK:
        payload = _read_queue()
        items = payload.setdefault("items", [])
        existing = next((item for item in items if item.get("sessionId") == normalized_session_id), None)

        if normalized_status == "completed" or not active_todos:
            if existing is not None:
                existing["status"] = "resolved"
                existing["resolution"] = normalized_status if normalized_status == "completed" else "cleared"
                existing["openTodos"] = active_todos
                existing["responsePreview"] = _truncate_preview(response_preview)
                existing["updatedAt"] = now
                _clear_retry_runtime_fields(existing)
                _append_event(existing, "resolved", str(existing.get("resolution") or "resolved"), timestamp=now)
                _write_queue(payload)
            return None

        if existing is None:
            existing = {
                "sessionId": normalized_session_id,
                "status": "pending",
                "reason": normalized_status,
                "responsePreview": _truncate_preview(response_preview),
                "openTodos": active_todos,
                "createdAt": now,
                "updatedAt": now,
                "attemptCount": 1,
            }
            _append_event(existing, "pending_created", f"Continuation created from {normalized_status} outcome.", timestamp=now)
            items.append(existing)
        else:
            existing["status"] = "pending"
            existing["reason"] = normalized_status
            existing["responsePreview"] = _truncate_preview(response_preview)
            existing["openTodos"] = active_todos
            existing["updatedAt"] = now
            existing["attemptCount"] = int(existing.get("attemptCount") or 0) + 1
            existing.setdefault("createdAt", now)
            existing.pop("resolution", None)
            _clear_retry_runtime_fields(existing)
            _append_event(existing, "pending_updated", f"Continuation updated from {normalized_status} outcome.", timestamp=now)

        _write_queue(payload)
        return dict(existing)


def should_block_delegation(session_id: str, goal: str) -> Optional[str]:
    normalized_session_id = str(session_id or "").strip()
    normalized_goal = " ".join(str(goal or "").split()).strip().casefold()
    if not normalized_session_id or not normalized_goal:
        return None

    state = get_session_state(normalized_session_id)
    if not state:
        return None

    matching = [
        entry
        for entry in (state.get("delegations") or [])
        if isinstance(entry, dict)
        and " ".join(str(entry.get("goal") or "").split()).strip().casefold() == normalized_goal
    ]
    if len(matching) < _MAX_CONSECUTIVE_DELEGATION_FAILURES:
        return None

    recent = matching[-_MAX_CONSECUTIVE_DELEGATION_FAILURES:]
    if all(str(entry.get("status") or "").strip().lower() in _DELEGATION_FAILURE_STATUSES for entry in recent):
        display_goal = str(goal).strip()
        return (
            f"Blocked delegated retry loop for '{display_goal}': the last "
            f"{_MAX_CONSECUTIVE_DELEGATION_FAILURES} attempts all ended without completion. "
            "Surface the unfinished work through the continuation queue instead of retrying automatically."
        )
    return None

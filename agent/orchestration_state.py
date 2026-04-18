"""Durable orchestration state for active Hermes sessions.

Stores small per-session JSON snapshots under HERMES_HOME so Pan and future
continuation logic can inspect what the agent is currently doing, including
child delegations. This is intentionally lightweight and profile-scoped.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import get_hermes_dir

_STATE_LOCK = threading.RLock()
_MAX_PREVIEW_CHARS = 500
_MAX_DELEGATIONS = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truncate_preview(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= _MAX_PREVIEW_CHARS:
        return text
    return text[:_MAX_PREVIEW_CHARS].rstrip() + "…"


def _state_dir() -> Path:
    directory = get_hermes_dir("runtime/orchestration", "orchestration_state")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _state_path(session_id: str) -> Path:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        raise ValueError("session_id is required")
    return _state_dir() / f"{safe_session_id}.json"


def _read_state(session_id: str) -> Dict[str, Any]:
    path = _state_path(session_id)
    if not path.exists():
        return {
            "sessionId": session_id,
            "status": "running",
            "platform": None,
            "userId": None,
            "messagePreview": None,
            "responsePreview": None,
            "startedAt": None,
            "updatedAt": None,
            "endedAt": None,
            "sessionLifecycle": "active",
            "delegations": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("sessionId", session_id)
            payload.setdefault("delegations", [])
            payload.setdefault("sessionLifecycle", "active")
            return payload
    except Exception:
        pass
    return {
        "sessionId": session_id,
        "status": "running",
        "platform": None,
        "userId": None,
        "messagePreview": None,
        "responsePreview": None,
        "startedAt": None,
        "updatedAt": None,
        "endedAt": None,
        "sessionLifecycle": "active",
        "delegations": [],
    }


def _write_state(session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _state_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return payload


def get_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    with _STATE_LOCK:
        path = _state_path(session_id)
        if not path.exists():
            return None
        return _read_state(session_id)


def record_agent_start(
    session_id: str,
    *,
    platform: Optional[str] = None,
    user_id: Optional[str] = None,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    with _STATE_LOCK:
        payload = _read_state(session_id)
        now = _now_iso()
        payload["status"] = "running"
        payload["platform"] = platform or payload.get("platform")
        payload["userId"] = user_id or payload.get("userId")
        payload["messagePreview"] = _truncate_preview(message) or payload.get("messagePreview")
        payload["startedAt"] = payload.get("startedAt") or now
        payload["updatedAt"] = now
        payload["endedAt"] = None
        payload["sessionLifecycle"] = "active"
        return _write_state(session_id, payload)


def record_agent_end(
    session_id: str,
    *,
    status: str = "completed",
    response: Optional[str] = None,
) -> Dict[str, Any]:
    with _STATE_LOCK:
        payload = _read_state(session_id)
        now = _now_iso()
        payload["status"] = status
        payload["responsePreview"] = _truncate_preview(response) if response is not None else payload.get("responsePreview")
        payload["updatedAt"] = now
        if status and status != "running":
            payload["endedAt"] = now
        return _write_state(session_id, payload)


def record_session_lifecycle(session_id: str, lifecycle: str) -> Dict[str, Any]:
    with _STATE_LOCK:
        payload = _read_state(session_id)
        now = _now_iso()
        payload["sessionLifecycle"] = lifecycle
        payload["updatedAt"] = now
        if lifecycle in {"ended", "reset"}:
            payload["endedAt"] = now
        return _write_state(session_id, payload)


def record_delegation_start(
    session_id: str,
    *,
    goal: str,
    task_index: Optional[int] = None,
    toolsets: Optional[list[str]] = None,
) -> str:
    with _STATE_LOCK:
        payload = _read_state(session_id)
        now = _now_iso()
        delegations = payload.setdefault("delegations", [])
        delegation_id = f"dlg_{len(delegations) + 1}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        delegations.append(
            {
                "id": delegation_id,
                "taskIndex": task_index,
                "goal": _truncate_preview(goal),
                "status": "running",
                "summary": None,
                "apiCalls": None,
                "durationSeconds": None,
                "model": None,
                "toolsets": toolsets or [],
                "startedAt": now,
                "updatedAt": now,
            }
        )
        if len(delegations) > _MAX_DELEGATIONS:
            payload["delegations"] = delegations[-_MAX_DELEGATIONS:]
        payload["updatedAt"] = now
        _write_state(session_id, payload)
        return delegation_id


def record_delegation_end(
    session_id: str,
    delegation_id: str,
    *,
    status: str,
    summary: Optional[str] = None,
    api_calls: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    with _STATE_LOCK:
        payload = _read_state(session_id)
        now = _now_iso()
        delegations = payload.setdefault("delegations", [])
        for entry in delegations:
            if entry.get("id") != delegation_id:
                continue
            entry["status"] = status
            entry["summary"] = _truncate_preview(summary) if summary is not None else entry.get("summary")
            entry["apiCalls"] = api_calls if api_calls is not None else entry.get("apiCalls")
            entry["durationSeconds"] = duration_seconds if duration_seconds is not None else entry.get("durationSeconds")
            entry["model"] = model if model is not None else entry.get("model")
            entry["updatedAt"] = now
            break
        payload["updatedAt"] = now
        return _write_state(session_id, payload)

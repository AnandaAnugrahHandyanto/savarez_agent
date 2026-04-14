"""Hermes-native continuity queue, dependency, lock, and handoff helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

SCHEMA = "hermes.continuity_queue_state.v1"
EVENT_SCHEMA = "hermes.continuity_queue_event.v1"
HANDOFF_SCHEMA = "hermes.continuity_queue_handoff.v1"
ACTIVE_STATES = {"QUEUED", "RUNNING", "REVIEW", "BLOCKED"}
TERMINAL_STATES = {"DONE", "FAILED", "ROLLED_BACK"}
ALLOWED_TRANSITIONS = {
    "QUEUED": {"RUNNING", "BLOCKED", "FAILED", "ROLLED_BACK"},
    "RUNNING": {"REVIEW", "BLOCKED", "FAILED", "ROLLED_BACK", "DONE"},
    "REVIEW": {"DONE", "BLOCKED", "FAILED", "ROLLED_BACK", "RUNNING"},
    "BLOCKED": {"QUEUED", "RUNNING", "FAILED", "ROLLED_BACK"},
    "DONE": set(),
    "FAILED": set(),
    "ROLLED_BACK": set(),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _root() -> Path:
    return get_hermes_home() / "continuity_queue"


def _state_path() -> Path:
    return _root() / "state.json"


def _events_path() -> Path:
    return _root() / "events.jsonl"


def _snapshot_path() -> Path:
    return _root() / "latest_snapshot.json"


def _base_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "updated_at": _utc_now_iso(),
        "items": {},
        "handoff_packets": [],
        "locks": {},
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return _base_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _base_state()
    if not isinstance(payload, dict):
        return _base_state()
    merged = _base_state()
    merged.update(payload)
    merged["items"] = dict(payload.get("items") or {})
    merged["handoff_packets"] = list(payload.get("handoff_packets") or [])
    merged["locks"] = dict(payload.get("locks") or {})
    return merged


def write_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = _base_state()
    payload.update(state)
    payload["updated_at"] = _utc_now_iso()
    _write_json(_state_path(), payload)
    return payload


def _append_event(action: str, payload: dict[str, Any]) -> None:
    record = {
        "schema": EVENT_SCHEMA,
        "ts": _utc_now_iso(),
        "action": action,
        **payload,
    }
    path = _events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "state": task["state"],
        "role_required": task["role_required"],
        "owner": task.get("owner"),
        "updated_at": task.get("updated_at"),
        "dependencies": list(task.get("dependencies") or []),
        "file_targets": list(task.get("file_targets") or []),
        "artifacts": list(task.get("artifacts") or []),
        "blocked_reason": task.get("blocked_reason"),
        "next_role": task.get("next_role"),
    }


def _dependencies_satisfied(state: dict[str, Any], task: dict[str, Any]) -> tuple[bool, list[str]]:
    unsatisfied: list[str] = []
    for dependency in task.get("dependencies") or []:
        dep_task = (state.get("items") or {}).get(dependency)
        if not isinstance(dep_task, dict) or dep_task.get("state") != "DONE":
            unsatisfied.append(dependency)
    return (not unsatisfied, unsatisfied)


def _conflicting_locks(state: dict[str, Any], task_id: str, targets: list[str]) -> list[str]:
    conflicts: list[str] = []
    for target in targets:
        lock = (state.get("locks") or {}).get(target)
        if not isinstance(lock, dict):
            continue
        if lock.get("task_id") != task_id and lock.get("state") == "ACTIVE":
            conflicts.append(target)
    return conflicts


def _release_locks(state: dict[str, Any], task_id: str) -> None:
    for target, lock in list((state.get("locks") or {}).items()):
        if isinstance(lock, dict) and lock.get("task_id") == task_id and lock.get("state") == "ACTIVE":
            state["locks"][target] = {
                **lock,
                "state": "RELEASED",
                "released_at": _utc_now_iso(),
            }


def enqueue_task(
    *,
    task_id: str,
    title: str,
    role_required: str,
    file_targets: list[str] | None = None,
    dependencies: list[str] | None = None,
    artifacts: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = read_state()
    items = state.setdefault("items", {})
    if task_id in items:
        raise ValueError(f"duplicate task id: {task_id}")
    now = _utc_now_iso()
    task = {
        "task_id": task_id,
        "title": title,
        "state": "QUEUED",
        "role_required": role_required,
        "owner": None,
        "created_at": now,
        "updated_at": now,
        "dependencies": list(dependencies or []),
        "file_targets": list(file_targets or []),
        "artifacts": list(artifacts or []),
        "metadata": dict(metadata or {}),
        "blocked_reason": None,
        "next_role": None,
    }
    items[task_id] = task
    write_state(state)
    _append_event("enqueue", {"task": _task_summary(task)})
    return task


def claim_task(*, task_id: str, actor_id: str, actor_role: str) -> dict[str, Any]:
    state = read_state()
    task = (state.get("items") or {}).get(task_id)
    if not isinstance(task, dict):
        raise KeyError(task_id)
    if task.get("state") not in {"QUEUED", "BLOCKED"}:
        raise ValueError(f"task not claimable from state {task.get('state')}")
    if str(task.get("role_required") or "") != actor_role:
        raise PermissionError("actor role does not match task boundary owner")
    deps_ok, missing = _dependencies_satisfied(state, task)
    if not deps_ok:
        task["state"] = "BLOCKED"
        task["blocked_reason"] = f"dependency_blocked:{','.join(missing)}"
        task["updated_at"] = _utc_now_iso()
        write_state(state)
        _append_event("claim_blocked", {"task": _task_summary(task), "missing_dependencies": missing})
        return task
    conflicts = _conflicting_locks(state, task_id, list(task.get("file_targets") or []))
    if conflicts:
        task["state"] = "BLOCKED"
        task["blocked_reason"] = f"file_lock_conflict:{','.join(conflicts)}"
        task["updated_at"] = _utc_now_iso()
        write_state(state)
        _append_event("claim_blocked", {"task": _task_summary(task), "lock_conflicts": conflicts})
        return task

    now = _utc_now_iso()
    task["state"] = "RUNNING"
    task["blocked_reason"] = None
    task["owner"] = {"actor_id": actor_id, "actor_role": actor_role, "claimed_at": now}
    task["updated_at"] = now
    for target in task.get("file_targets") or []:
        state.setdefault("locks", {})[target] = {
            "task_id": task_id,
            "state": "ACTIVE",
            "actor_id": actor_id,
            "actor_role": actor_role,
            "claimed_at": now,
        }
    write_state(state)
    _append_event("claim", {"task": _task_summary(task)})
    return task


def transition_task(
    *,
    task_id: str,
    to_state: str,
    actor_id: str,
    actor_role: str,
    evidence_refs: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    next_role: str | None = None,
    block_reason: str | None = None,
) -> dict[str, Any]:
    state = read_state()
    task = (state.get("items") or {}).get(task_id)
    if not isinstance(task, dict):
        raise KeyError(task_id)
    from_state = str(task.get("state") or "")
    target = str(to_state or "").strip().upper()
    if target not in ALLOWED_TRANSITIONS.get(from_state, set()):
        raise ValueError(f"invalid transition {from_state} -> {target}")
    if actor_role not in {str(task.get("role_required") or ""), str(task.get("next_role") or "") or actor_role}:
        if from_state != "REVIEW":
            raise PermissionError("actor role is not allowed to perform this transition")

    now = _utc_now_iso()
    task["state"] = target
    task["updated_at"] = now
    task["blocked_reason"] = block_reason if target == "BLOCKED" else None
    if artifact_refs:
        existing = list(task.get("artifacts") or [])
        for ref in artifact_refs:
            if ref not in existing:
                existing.append(ref)
        task["artifacts"] = existing

    if next_role:
        packet = {
            "schema": HANDOFF_SCHEMA,
            "packet_id": f"handoff_{task_id}_{now.replace(':', '').replace('-', '')}",
            "task_id": task_id,
            "from_role": actor_role,
            "to_role": next_role,
            "from_state": from_state,
            "to_state": target,
            "created_at": now,
            "evidence_refs": list(evidence_refs or []),
            "artifact_refs": list(artifact_refs or []),
        }
        state.setdefault("handoff_packets", []).append(packet)
        task["next_role"] = next_role
    elif target in TERMINAL_STATES:
        task["next_role"] = None

    if target in TERMINAL_STATES:
        _release_locks(state, task_id)
    write_state(state)
    _append_event(
        "transition",
        {
            "task_id": task_id,
            "from_state": from_state,
            "to_state": target,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "evidence_refs": list(evidence_refs or []),
            "artifact_refs": list(artifact_refs or []),
            "next_role": next_role,
            "blocked_reason": block_reason,
        },
    )
    return task


def build_snapshot() -> dict[str, Any]:
    state = read_state()
    items = [task for task in (state.get("items") or {}).values() if isinstance(task, dict)]
    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    running: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    done: list[dict[str, Any]] = []
    resumable: list[dict[str, Any]] = []

    for task in items:
        summary = _task_summary(task)
        deps_ok, missing = _dependencies_satisfied(state, task)
        lock_conflicts = _conflicting_locks(state, task["task_id"], list(task.get("file_targets") or []))
        summary["missing_dependencies"] = missing
        summary["lock_conflicts"] = lock_conflicts
        if task.get("state") == "QUEUED" and deps_ok and not lock_conflicts:
            ready.append(summary)
        elif task.get("state") == "RUNNING":
            running.append(summary)
            resumable.append(summary)
        elif task.get("state") == "REVIEW":
            review.append(summary)
            resumable.append(summary)
        elif task.get("state") == "BLOCKED":
            blocked.append(summary)
        elif task.get("state") == "DONE":
            done.append(summary)

    snapshot = {
        "schema": "hermes.continuity_queue_snapshot.v1",
        "generated_at": _utc_now_iso(),
        "queue": {
            "ready": ready,
            "running": running,
            "review": review,
            "blocked": blocked,
            "done": done,
            "resumable": resumable,
        },
        "handoff_packets": list(state.get("handoff_packets") or []),
        "lock_summary": {
            "active": sorted(target for target, lock in (state.get("locks") or {}).items() if isinstance(lock, dict) and lock.get("state") == "ACTIVE"),
            "released": sorted(target for target, lock in (state.get("locks") or {}).items() if isinstance(lock, dict) and lock.get("state") == "RELEASED"),
        },
        "totals": {
            "items": len(items),
            "ready": len(ready),
            "running": len(running),
            "review": len(review),
            "blocked": len(blocked),
            "done": len(done),
            "handoffs": len(state.get("handoff_packets") or []),
        },
    }
    _write_json(_snapshot_path(), snapshot)
    snapshot["snapshot_path"] = str(_snapshot_path())
    return snapshot

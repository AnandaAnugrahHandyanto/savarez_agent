from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .reminder_log import append_reminder_log
from .schedule_store import load_schedule_registry
from .storage import get_people_manager_root, get_report_path

QUEUE_DIRNAME = "prep-queue"
LOCKS_DIRNAME = "locks"
DEFAULT_MIYA_SLA_SECONDS = 30
DEFAULT_FALLBACK_SECONDS = 60



def get_prep_queue_root() -> Path:
    root = get_people_manager_root() / QUEUE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root



def occurrence_key(profile_slug: str, meeting_at: datetime | str) -> str:
    meeting_text = meeting_at if isinstance(meeting_at, str) else meeting_at.isoformat()
    return f"{profile_slug}::{meeting_text}"



def _safe_filename(dedupe_key: str) -> str:
    return dedupe_key.replace("::", "__").replace(":", "-").replace("/", "_") + ".json"



def get_queue_event_path(dedupe_key: str) -> Path:
    return get_prep_queue_root() / _safe_filename(dedupe_key)



def get_prep_queue_locks_root() -> Path:
    root = get_prep_queue_root() / LOCKS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root



def get_transition_lock_path(dedupe_key: str, *, lock_name: str) -> Path:
    stem = _safe_filename(dedupe_key).removesuffix('.json')
    return get_prep_queue_locks_root() / f"{stem}.{lock_name}.lock"



def acquire_transition_lock(dedupe_key: str, *, lock_name: str, owner: str) -> bool:
    path = get_transition_lock_path(dedupe_key, lock_name=lock_name)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(owner + "\n")
    except FileExistsError:
        return False
    return True



def release_transition_lock(dedupe_key: str, *, lock_name: str) -> None:
    path = get_transition_lock_path(dedupe_key, lock_name=lock_name)
    path.unlink(missing_ok=True)



def _atomic_write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload



def _append_history(event: dict[str, Any], *, status: str, at: str, actor: str | None = None, note: str | None = None) -> None:
    history = event.setdefault("history", [])
    item: dict[str, Any] = {"status": status, "at": at}
    if actor:
        item["actor"] = actor
    if note:
        item["note"] = note
    history.append(item)



def _append_log(event: dict[str, Any], *, status: str, at: str, actor: str | None = None, note: str | None = None) -> None:
    payload = {
        "profile_slug": event["profile_slug"],
        "meeting_at": event["meeting_at"],
        "event_at": at,
        "delivery_target": event.get("delivery_target", "origin"),
        "template_style": event.get("template_style"),
        "dedupe_key": event["dedupe_key"],
        "status": status,
    }
    if actor:
        payload["actor"] = actor
    if note:
        payload["note"] = note
    append_reminder_log(payload)



def load_queue_event(dedupe_key: str) -> dict[str, Any] | None:
    path = get_queue_event_path(dedupe_key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))



def save_queue_event(event: dict[str, Any]) -> dict[str, Any]:
    return _atomic_write(get_queue_event_path(event["dedupe_key"]), deepcopy(event))



def create_queue_event(event: dict[str, Any]) -> dict[str, Any] | None:
    path = get_queue_event_path(event["dedupe_key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(deepcopy(event), indent=2, sort_keys=True) + "\n")
    except FileExistsError:
        return None
    return event



def list_queue_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in sorted(get_prep_queue_root().glob("*.json")):
        try:
            events.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    events.sort(key=lambda item: (item.get("prep_due_at", ""), item.get("profile_slug", ""), item.get("dedupe_key", "")))
    return events



def build_queue_event(
    due_entry: dict[str, Any],
    *,
    detected_at: datetime,
    miya_sla_seconds: int = DEFAULT_MIYA_SLA_SECONDS,
    fallback_seconds: int = DEFAULT_FALLBACK_SECONDS,
) -> dict[str, Any]:
    meeting_at = due_entry["meeting_at"]
    prep_due_at = due_entry["prep_at"]
    profile_slug = due_entry["profile_slug"]
    schedule = due_entry["schedule"]
    report = due_entry["report"]
    dedupe_key = occurrence_key(profile_slug, meeting_at)
    target_send_by = prep_due_at.timestamp() + miya_sla_seconds
    fallback_deadline = prep_due_at.timestamp() + fallback_seconds
    event = {
        "type": "one_on_one_prep_due",
        "profile_slug": profile_slug,
        "name": schedule.get("name") or report.get("name") or profile_slug,
        "meeting_at": meeting_at.isoformat(),
        "prep_due_at": prep_due_at.isoformat(),
        "target_send_by_at": datetime.fromtimestamp(target_send_by, tz=prep_due_at.tzinfo).isoformat(),
        "deadline_at": datetime.fromtimestamp(fallback_deadline, tz=prep_due_at.tzinfo).isoformat(),
        "delivery_target": schedule.get("delivery_target", "origin"),
        "report_path": str(get_report_path(profile_slug)),
        "template_style": schedule.get("template_style"),
        "fallback_allowed": True,
        "dedupe_key": dedupe_key,
        "minutes_until": max(1, int((meeting_at - prep_due_at).total_seconds() // 60)),
        "state": "queued_for_miya",
        "delivery_outcome": None,
        "detected_at": detected_at.isoformat(),
        "queued_at": detected_at.isoformat(),
        "history": [],
    }
    _append_history(event, status="due_detected", at=detected_at.isoformat(), actor="scheduler")
    _append_history(event, status="queued_for_miya", at=detected_at.isoformat(), actor="scheduler")
    return event



def enqueue_due_occurrence(
    due_entry: dict[str, Any],
    *,
    detected_at: datetime,
    miya_sla_seconds: int = DEFAULT_MIYA_SLA_SECONDS,
    fallback_seconds: int = DEFAULT_FALLBACK_SECONDS,
) -> tuple[dict[str, Any], bool]:
    event = build_queue_event(
        due_entry,
        detected_at=detected_at,
        miya_sla_seconds=miya_sla_seconds,
        fallback_seconds=fallback_seconds,
    )
    existing = load_queue_event(event["dedupe_key"])
    if existing is not None:
        return existing, False
    created = create_queue_event(event)
    if created is None:
        return load_queue_event(event["dedupe_key"]) or event, False
    _append_log(created, status="due_detected", at=created["detected_at"], actor="scheduler")
    _append_log(created, status="queued_for_miya", at=created["queued_at"], actor="scheduler")
    return created, True



def _record_state(
    event: dict[str, Any],
    *,
    state: str,
    at: datetime,
    actor: str,
    note: str | None = None,
    delivery_outcome: str | None | object = None,
) -> dict[str, Any]:
    event = deepcopy(event)
    event["state"] = state
    if delivery_outcome is not None:
        event["delivery_outcome"] = delivery_outcome
    timestamp = at.isoformat()
    event[f"{state}_at"] = timestamp
    _append_history(event, status=state, at=timestamp, actor=actor, note=note)
    saved = save_queue_event(event)
    _append_log(saved, status=state, at=timestamp, actor=actor, note=note)
    return saved



def _override_blocks_event(event: dict[str, Any]) -> bool:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).get(str(event.get("profile_slug") or "")) or {}
    meeting_at = str(event.get("meeting_at") or "")
    has_active_match = False
    has_inactive_match = False
    for override in schedule.get("overrides", []) or []:
        if str(override.get("kind") or "") != "reschedule_once":
            continue
        if str(override.get("effective_meeting_at") or "") != meeting_at:
            continue
        if str(override.get("status") or "") == "active":
            has_active_match = True
        else:
            has_inactive_match = True
    return has_inactive_match and not has_active_match



def _suppress_if_blocked(event: dict[str, Any], *, at: datetime, actor: str, note: str) -> dict[str, Any] | None:
    if not _override_blocks_event(event):
        return None
    return _record_state(
        event,
        state="cancelled_override",
        at=at,
        actor=actor,
        note=note,
        delivery_outcome="cancelled_override",
    )



def claim_next_for_miya(*, now: datetime, actor: str = "miya") -> dict[str, Any] | None:
    candidates = [
        event
        for event in list_queue_events()
        if event.get("state") in {"queued_for_miya", "failed"} and not event.get("delivery_outcome")
    ]
    for event in candidates:
        dedupe_key = str(event["dedupe_key"])
        if not acquire_transition_lock(dedupe_key, lock_name="miya-claim", owner=actor):
            continue
        try:
            fresh = load_queue_event(dedupe_key)
            if not fresh:
                continue
            if fresh.get("state") not in {"queued_for_miya", "failed"} or fresh.get("delivery_outcome"):
                continue
            suppressed = _suppress_if_blocked(
                fresh,
                at=now,
                actor=actor,
                note="Override is no longer active; suppressing queued occurrence.",
            )
            if suppressed is not None:
                continue
            fresh["claimed_by"] = actor
            return _record_state(fresh, state="claimed_by_miya", at=now, actor=actor)
        finally:
            release_transition_lock(dedupe_key, lock_name="miya-claim")
    return None



def mark_failed(dedupe_key: str, *, failed_at: datetime, actor: str = "miya-bridge", note: str | None = None) -> dict[str, Any]:
    event = load_queue_event(dedupe_key)
    if event is None:
        raise KeyError(f"Unknown occurrence: {dedupe_key}")
    if event.get("delivery_outcome") in {"sent_by_miya", "fallback_sent"}:
        return event
    return _record_state(
        event,
        state="failed",
        at=failed_at,
        actor=actor,
        note=note,
        delivery_outcome=None,
    )



def mark_sent_by_miya(
    dedupe_key: str,
    *,
    sent_at: datetime,
    actor: str = "miya",
    note: str | None = None,
) -> dict[str, Any]:
    event = load_queue_event(dedupe_key)
    if event is None:
        raise KeyError(f"Unknown occurrence: {dedupe_key}")
    outcome = event.get("delivery_outcome")
    if outcome == "sent_by_miya":
        return event
    if outcome == "fallback_sent":
        return _record_state(
            event,
            state="stale_completion_suppressed",
            at=sent_at,
            actor=actor,
            note=note or "Founder-facing fallback already sent; suppressing late Miya completion.",
            delivery_outcome="fallback_sent",
        )
    suppressed = _suppress_if_blocked(
        event,
        at=sent_at,
        actor=actor,
        note=note or "Override is no longer active; suppressing Miya completion.",
    )
    if suppressed is not None:
        return suppressed
    return _record_state(
        event,
        state="sent_by_miya",
        at=sent_at,
        actor=actor,
        note=note,
        delivery_outcome="sent_by_miya",
    )



def fallback_candidates(*, now: datetime) -> list[dict[str, Any]]:
    candidates = []
    for event in list_queue_events():
        if not event.get("fallback_allowed", True):
            continue
        if event.get("delivery_outcome"):
            continue
        if _override_blocks_event(event):
            _suppress_if_blocked(
                event,
                at=now,
                actor="scheduler",
                note="Override is no longer active; suppressing queued occurrence before fallback.",
            )
            continue
        if get_transition_lock_path(str(event.get("dedupe_key")), lock_name="fallback-send").exists():
            continue
        deadline_at = event.get("deadline_at")
        if not deadline_at:
            continue
        try:
            deadline = datetime.fromisoformat(str(deadline_at))
        except ValueError:
            continue
        if deadline <= now:
            candidates.append(event)
    candidates.sort(key=lambda item: (item.get("deadline_at", ""), item.get("profile_slug", "")))
    return candidates



def mark_fallback_sent(dedupe_key: str, *, sent_at: datetime, actor: str = "scheduler", note: str | None = None) -> dict[str, Any]:
    event = load_queue_event(dedupe_key)
    if event is None:
        raise KeyError(f"Unknown occurrence: {dedupe_key}")
    if event.get("delivery_outcome") == "fallback_sent":
        return event
    if event.get("delivery_outcome") == "sent_by_miya":
        return event
    return _record_state(
        event,
        state="fallback_sent",
        at=sent_at,
        actor=actor,
        note=note,
        delivery_outcome="fallback_sent",
    )



def queue_state_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in list_queue_events():
        state = str(event.get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))

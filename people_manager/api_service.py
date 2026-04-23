from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .ad_hoc_prep import build_ad_hoc_prep_note
from .merge import apply_assessment, apply_one_on_one, apply_todo, apply_update
from .prep_queue import enqueue_due_occurrence, list_queue_events
from .prep_renderer import render_prep_note
from .reminder_log import load_reminder_entries
from .renderers import render_team_scan
from .schedule_store import (
    DEFAULT_TIMEZONE,
    create_reschedule_override,
    due_reminders,
    load_schedule_registry,
    next_schedule_times,
    resolve_schedule_occurrence,
    save_schedule_registry,
)
from .storage import (
    create_report,
    list_reports_by_recency,
    load_report,
    normalize_report,
    save_report,
    slugify_name,
    touch_report,
)


def _load_reports() -> list[dict[str, Any]]:
    reports = []
    for meta in list_reports_by_recency():
        report = load_report(str(meta["slug"]))
        if report:
            reports.append(report)
    return reports


def list_profiles() -> dict[str, Any]:
    profiles = []
    for meta in list_reports_by_recency():
        report = load_report(str(meta["slug"]))
        if not report:
            continue
        profiles.append(
            {
                "slug": report["slug"],
                "name": report["name"],
                "role_title": report.get("role_title") or "",
                "status": report.get("status") or "active",
                "updated_at": report.get("updated_at"),
                "open_loop_count": len(report.get("open_loop_items") or []),
                "interaction_count": len(report.get("interaction_log") or []),
            }
        )
    return {"profiles": profiles}


def get_profile(slug: str) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    return {"profile": report, "open_loops": report.get("open_loop_items") or []}


def create_profile(payload: dict[str, Any]) -> dict[str, Any]:
    report = create_report(payload["name"], payload.get("role_title", ""), payload.get("mandate", ""))
    return {"profile": report}


def patch_profile(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    for key, value in payload.items():
        if key in {"role_charter", "goals", "operating_state", "performance", "management_strategy", "open_loops", "upcoming_one_on_one"} and isinstance(value, dict):
            report.setdefault(key, {}).update(value)
        else:
            report[key] = value
    saved = save_report(report)
    touch_report(slug)
    return {"profile": saved}


def list_interactions(slug: str) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    return {"interactions": report.get("interaction_log") or []}


def add_interaction(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    lane_id = payload.get("lane_id", "web")
    kind = str(payload.get("kind") or "update")
    body = str(payload.get("body") or "").strip()
    if kind == "update":
        report = apply_update(report, body, lane_id=lane_id)
    elif kind == "one_on_one":
        report = apply_one_on_one(report, body, lane_id=lane_id)
    elif kind == "assessment":
        report = apply_assessment(report, body, lane_id=lane_id)
    elif kind == "todo_report":
        report = apply_todo(report, body, for_manager=False, lane_id=lane_id)
    elif kind == "todo_manager":
        report = apply_todo(report, body, for_manager=True, lane_id=lane_id)
    else:
        raise ValueError(f"Unsupported interaction kind: {kind}")
    saved = save_report(report)
    touch_report(slug)
    return {"interaction": saved["interaction_log"][-1], "profile": saved}


def _sync_open_loop_buckets(report: dict[str, Any]) -> dict[str, Any]:
    report = normalize_report(report)
    loops = report.setdefault("open_loops", {})
    items = [item for item in report.get("open_loop_items") or [] if str(item.get("status") or "open") != "closed"]
    bucket_map = {
        "report": "open_todos_for_them",
        "manager": "open_todos_for_michael",
        "question": "unresolved_questions",
        "risk": "active_risks",
    }
    for bucket in bucket_map.values():
        loops[bucket] = []
    for item in items:
        bucket = bucket_map.get(str(item.get("owner") or "report"), "open_todos_for_them")
        text = str(item.get("text") or "").strip()
        if text and text not in loops[bucket]:
            loops[bucket].append(text)
    report["open_loop_items"] = items
    return report


def add_open_loop(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    items = report.setdefault("open_loop_items", [])
    next_id = f"loop_{len(items) + 1:04d}"
    item = {
        "id": next_id,
        "text": str(payload.get("text") or "").strip(),
        "owner": str(payload.get("owner") or "report"),
        "status": str(payload.get("status") or "open"),
    }
    items.append(item)
    report = _sync_open_loop_buckets(report)
    saved = save_report(report)
    touch_report(slug)
    return {"open_loop": item, "profile": saved}


def update_open_loop(slug: str, loop_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    for item in report.get("open_loop_items") or []:
        if str(item.get("id")) != loop_id:
            continue
        item.update(payload)
        report = _sync_open_loop_buckets(report)
        saved = save_report(report)
        touch_report(slug)
        return {"open_loop": item, "profile": saved}
    raise KeyError(loop_id)


def get_prep(slug: str, *, mode: str = "adhoc", minutes_until: int = 5) -> dict[str, Any]:
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    title_mode = "adhoc" if mode == "adhoc" else "scheduled"
    brief = render_prep_note(report, title_mode=title_mode, minutes_until=minutes_until)
    return {"slug": slug, "mode": title_mode, "brief": brief}


def preview_prep(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    return get_prep(slug, mode=str(payload.get("mode") or "adhoc"), minutes_until=int(payload.get("minutes_until") or 5))


def get_team_scan() -> dict[str, Any]:
    reports = _load_reports()
    return {"markdown": render_team_scan(reports), "count": len(reports)}


def list_schedules(*, now: str | None = None) -> dict[str, Any]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    local_now = _parse_now(now, timezone_name)
    schedules: dict[str, Any] = {}
    for slug, schedule in registry.get("profiles", {}).items():
        item = deepcopy(schedule)
        try:
            resolved = resolve_schedule_occurrence(schedule, now=local_now, timezone_name=timezone_name)
            item["next_meeting_at"] = resolved["meeting_at"].isoformat()
            item["next_prep_at"] = resolved["prep_at"].isoformat()
        except Exception:
            item["next_meeting_at"] = None
            item["next_prep_at"] = None
        schedules[slug] = item
    return {"timezone": timezone_name, "schedules": schedules}


def get_schedule(slug: str, *, now: str | None = None) -> dict[str, Any]:
    schedules = list_schedules(now=now)["schedules"]
    if slug not in schedules:
        raise KeyError(slug)
    return {"schedule": schedules[slug]}


def create_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    registry = load_schedule_registry()
    slug = str(payload["slug"])
    schedule = deepcopy(payload)
    schedule.pop("slug", None)
    registry.setdefault("profiles", {})[slug] = schedule
    save_schedule_registry(registry)
    return get_schedule(slug)


def patch_schedule(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    registry = load_schedule_registry()
    schedule = registry.setdefault("profiles", {}).get(slug)
    if not schedule:
        raise KeyError(slug)
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(schedule.get(key), dict):
            schedule[key].update(value)
        else:
            schedule[key] = value
    save_schedule_registry(registry)
    return get_schedule(slug)


def set_schedule_enabled(slug: str, enabled: bool) -> dict[str, Any]:
    return patch_schedule(slug, {"enabled": enabled})


def preview_schedule(slug: str, *, now: str | None = None) -> dict[str, Any]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    schedule = registry.get("profiles", {}).get(slug)
    if not schedule:
        raise KeyError(slug)
    report = load_report(slug)
    if not report:
        raise KeyError(slug)
    local_now = _parse_now(now, timezone_name)
    resolved = resolve_schedule_occurrence(schedule, now=local_now, timezone_name=timezone_name)
    brief = render_prep_note(report, title_mode="scheduled", minutes_until=max(1, int((resolved["meeting_at"] - resolved["prep_at"]).total_seconds() // 60)))
    return {"brief": brief, "meeting_at": resolved["meeting_at"].isoformat(), "prep_at": resolved["prep_at"].isoformat()}


def reschedule_once(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    override = create_reschedule_override(
        slug,
        effective_meeting_at=_parse_now(str(payload["effective_meeting_at"]), timezone_name),
        now=_parse_now(payload.get("now"), timezone_name),
        source={"platform": "web", "lane": "web", "message_text": str(payload.get("message_text") or "")},
        override_id=payload.get("override_id"),
    )
    return {"override": override}


def delete_schedule(slug: str) -> dict[str, Any]:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).pop(slug, None)
    if not schedule:
        raise KeyError(slug)
    registry.setdefault("archived_profiles", {})[slug] = schedule
    save_schedule_registry(registry)
    return {"removed": slug, "archived": True}


def ops_due_now(*, now: str | None = None) -> dict[str, Any]:
    entries = due_reminders(now=_parse_now(now, str(load_schedule_registry().get("timezone") or DEFAULT_TIMEZONE)))
    return {
        "due": [
            {
                "profile_slug": entry["profile_slug"],
                "meeting_at": entry["meeting_at"].isoformat(),
                "prep_at": entry["prep_at"].isoformat(),
            }
            for entry in entries
        ]
    }


def ops_log(*, month: str | None = None, slug: str | None = None, limit: int = 20) -> dict[str, Any]:
    return {"entries": load_reminder_entries(month=month, profile_slug=slug, limit=limit)}


def ops_audit() -> dict[str, Any]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    now = datetime.now(ZoneInfo(timezone_name))
    profiles = registry.get("profiles", {})
    from .storage import get_people_manager_root

    reports_dir = get_people_manager_root() / "reports"
    report_slugs = sorted(path.stem for path in reports_dir.glob("*.json")) if reports_dir.exists() else []
    scheduled_without_report = [slug for slug in sorted(profiles) if slug not in report_slugs]
    unscheduled_reports = [slug for slug in report_slugs if slug not in profiles]
    sparse_prep = []
    malformed_schedules = []
    for slug, schedule in sorted(profiles.items()):
        report = load_report(slug)
        if report and not any(
            [
                (report.get("upcoming_one_on_one") or {}).get("topics"),
                (report.get("upcoming_one_on_one") or {}).get("ritual"),
                report.get("relationship_note"),
                (report.get("open_loops") or {}).get("open_todos_for_michael"),
            ]
        ):
            sparse_prep.append(slug)
        try:
            next_schedule_times(schedule, now=now, timezone_name=timezone_name)
        except Exception:
            malformed_schedules.append(slug)
    return {
        "scheduled_without_report": scheduled_without_report,
        "unscheduled_reports": unscheduled_reports,
        "sparse_prep_metadata": sparse_prep,
        "malformed_schedules": malformed_schedules,
        "queue_state": list_queue_events(),
    }


def ops_run_once(*, now: str | None = None) -> dict[str, Any]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    local_now = _parse_now(now, timezone_name)
    created = []
    existing = []
    for entry in due_reminders(now=local_now):
        event, was_created = enqueue_due_occurrence(entry, detected_at=local_now)
        (created if was_created else existing).append(event["dedupe_key"])
    return {"created": created, "existing": existing}


def _parse_now(value: str | None, timezone_name: str) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed.astimezone(ZoneInfo(timezone_name))
    return datetime.now(ZoneInfo(timezone_name))

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .storage import get_people_manager_root, load_report

SCHEDULES_DIRNAME = "schedules"
SCHEDULES_FILENAME = "one_on_ones.json"
DEFAULT_TIMEZONE = "Asia/Singapore"
DEFAULT_PREP_OFFSET_MINUTES = 5
DEFAULT_TEMPLATE_STYLE = "ultra_short_telegram"
GRACE_SECONDS = 90


@dataclass(slots=True)
class DueReminder:
    profile_slug: str
    report: dict[str, Any]
    schedule: dict[str, Any]
    base_meeting_at: datetime
    base_prep_at: datetime
    meeting_at: datetime
    prep_at: datetime
    override: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_slug": self.profile_slug,
            "report": self.report,
            "schedule": self.schedule,
            "base_meeting_at": self.base_meeting_at,
            "base_prep_at": self.base_prep_at,
            "meeting_at": self.meeting_at,
            "prep_at": self.prep_at,
            "override": self.override,
        }


def get_schedules_root() -> Path:
    root = get_people_manager_root() / SCHEDULES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_schedule_registry_path() -> Path:
    return get_schedules_root() / SCHEDULES_FILENAME


def default_schedule_registry() -> dict[str, Any]:
    return {"version": 1, "timezone": DEFAULT_TIMEZONE, "profiles": {}, "archived_profiles": {}}


def _normalize_registry(registry: dict[str, Any]) -> dict[str, Any]:
    registry.setdefault("version", 1)
    registry.setdefault("timezone", DEFAULT_TIMEZONE)
    registry.setdefault("profiles", {})
    registry.setdefault("archived_profiles", {})
    for bucket_name in ("profiles", "archived_profiles"):
        for schedule in registry.get(bucket_name, {}).values():
            schedule.setdefault("overrides", [])
    return registry


def load_schedule_registry() -> dict[str, Any]:
    path = get_schedule_registry_path()
    if not path.exists():
        registry = default_schedule_registry()
        save_schedule_registry(registry)
        return registry
    data = json.loads(path.read_text(encoding="utf-8"))
    return _normalize_registry(data)


def save_schedule_registry(registry: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(registry)
    _normalize_registry(payload)
    path = get_schedule_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = str(value).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except Exception as exc:
        raise ValueError(f"Invalid time value: {value}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time value: {value}")
    return hour, minute


def _combine_local(day: date, hhmm: str, timezone_name: str) -> datetime:
    hour, minute = _parse_hhmm(hhmm)
    return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=ZoneInfo(timezone_name))


def _weekday_to_py(weekday: int) -> int:
    if weekday not in {1, 2, 3, 4, 5, 6, 7}:
        raise ValueError(f"weekday must be 1..7, got {weekday}")
    return weekday - 1


def _next_weekly_occurrence(meeting: dict[str, Any], *, now: datetime, timezone_name: str) -> datetime:
    target = _weekday_to_py(int(meeting["weekday"]))
    today = now.date()
    candidate = today + timedelta(days=(target - today.weekday()) % 7)
    scheduled = _combine_local(candidate, meeting["time"], timezone_name)
    if scheduled < now:
        scheduled = _combine_local(candidate + timedelta(days=7), meeting["time"], timezone_name)
    return scheduled


def _next_biweekly_occurrence(meeting: dict[str, Any], *, now: datetime, timezone_name: str) -> datetime:
    anchor = date.fromisoformat(str(meeting["anchor_date"]))
    target = _weekday_to_py(int(meeting["weekday"]))
    anchor_candidate = anchor + timedelta(days=(target - anchor.weekday()) % 7)
    base = _next_weekly_occurrence(meeting, now=now, timezone_name=timezone_name)
    delta_days = (base.date() - anchor_candidate).days
    if delta_days < 0:
        weeks = math.floor(delta_days / 7)
        candidate = anchor_candidate + timedelta(weeks=weeks)
    else:
        candidate = base.date()
    weeks_apart = (candidate - anchor_candidate).days // 7
    if weeks_apart % 2 != 0:
        candidate = candidate + timedelta(days=7)
    scheduled = _combine_local(candidate, meeting["time"], timezone_name)
    if scheduled < now:
        scheduled = _combine_local(candidate + timedelta(days=14), meeting["time"], timezone_name)
    return scheduled


def _nth_weekday_of_month(year: int, month: int, *, weekday: int, ordinal: int) -> date:
    if ordinal < 1:
        raise ValueError(f"ordinal must be >= 1, got {ordinal}")
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    candidate = first + timedelta(days=offset + (ordinal - 1) * 7)
    if candidate.month != month:
        raise ValueError(f"No ordinal {ordinal} weekday {weekday} in {year:04d}-{month:02d}")
    return candidate


def _next_monthly_nth_weekday_occurrence(meeting: dict[str, Any], *, now: datetime, timezone_name: str) -> datetime:
    target = _weekday_to_py(int(meeting["weekday"]))
    ordinal = int(meeting["ordinal"])
    year = now.year
    month = now.month
    for _ in range(24):
        candidate_day = _nth_weekday_of_month(year, month, weekday=target, ordinal=ordinal)
        scheduled = _combine_local(candidate_day, meeting["time"], timezone_name)
        if scheduled >= now:
            return scheduled
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    raise ValueError("Could not compute monthly occurrence within 24 months")


def _parse_iso_dt(value: datetime | str, *, timezone_name: str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return dt.astimezone(ZoneInfo(timezone_name))


def next_meeting_occurrence(meeting: dict[str, Any], *, now: datetime, timezone_name: str) -> datetime:
    now = now.astimezone(ZoneInfo(timezone_name))
    meeting_type = meeting.get("type")
    if meeting_type == "weekly":
        return _next_weekly_occurrence(meeting, now=now, timezone_name=timezone_name)
    if meeting_type == "biweekly":
        return _next_biweekly_occurrence(meeting, now=now, timezone_name=timezone_name)
    if meeting_type == "monthly_nth_weekday":
        return _next_monthly_nth_weekday_occurrence(meeting, now=now, timezone_name=timezone_name)
    raise ValueError(f"Unsupported meeting type: {meeting_type}")


def active_override_for_schedule(schedule: dict[str, Any], *, now: datetime, timezone_name: str) -> dict[str, Any] | None:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for override in schedule.get("overrides", []) or []:
        if str(override.get("kind") or "") != "reschedule_once":
            continue
        if str(override.get("status") or "active") != "active":
            continue
        try:
            effective_meeting_at = _parse_iso_dt(override["effective_meeting_at"], timezone_name=timezone_name)
        except Exception:
            continue
        if effective_meeting_at < local_now:
            continue
        candidates.append((effective_meeting_at, deepcopy(override)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _consumed_override_suppresses_base(schedule: dict[str, Any], *, base_meeting_at: datetime, now: datetime, timezone_name: str) -> bool:
    for override in schedule.get("overrides", []) or []:
        if str(override.get("kind") or "") != "reschedule_once":
            continue
        if str(override.get("status") or "") != "consumed":
            continue
        try:
            original_meeting_at = _parse_iso_dt(override["original_meeting_at"], timezone_name=timezone_name)
            effective_meeting_at = _parse_iso_dt(override["effective_meeting_at"], timezone_name=timezone_name)
        except Exception:
            continue
        if original_meeting_at != base_meeting_at:
            continue
        if effective_meeting_at >= original_meeting_at:
            continue
        if now > original_meeting_at:
            continue
        return True
    return False


def resolve_schedule_occurrence(schedule: dict[str, Any], *, now: datetime, timezone_name: str) -> dict[str, Any]:
    prep_offset = int(schedule.get("prep_offset_minutes", DEFAULT_PREP_OFFSET_MINUTES))
    override = active_override_for_schedule(schedule, now=now, timezone_name=timezone_name)
    if override:
        base_meeting_at = _parse_iso_dt(override["original_meeting_at"], timezone_name=timezone_name)
        meeting_at = _parse_iso_dt(override["effective_meeting_at"], timezone_name=timezone_name)
    else:
        base_meeting_at = next_meeting_occurrence(schedule.get("meeting", {}), now=now, timezone_name=timezone_name)
        if _consumed_override_suppresses_base(schedule, base_meeting_at=base_meeting_at, now=now, timezone_name=timezone_name):
            base_meeting_at = next_meeting_occurrence(
                schedule.get("meeting", {}),
                now=base_meeting_at + timedelta(seconds=1),
                timezone_name=timezone_name,
            )
        meeting_at = base_meeting_at
    base_prep_at = base_meeting_at - timedelta(minutes=prep_offset)
    prep_at = meeting_at - timedelta(minutes=prep_offset)
    return {
        "base_meeting_at": base_meeting_at,
        "base_prep_at": base_prep_at,
        "meeting_at": meeting_at,
        "prep_at": prep_at,
        "override": override,
    }


def next_schedule_times(schedule: dict[str, Any], *, now: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    resolved = resolve_schedule_occurrence(schedule, now=now, timezone_name=timezone_name)
    return resolved["meeting_at"], resolved["prep_at"]


def create_reschedule_override(
    profile_slug: str,
    *,
    effective_meeting_at: datetime,
    now: datetime,
    source: dict[str, Any],
    override_id: str | None = None,
) -> dict[str, Any]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    schedule = registry.get("profiles", {}).get(profile_slug)
    if not schedule:
        raise KeyError(f"Schedule not found for {profile_slug}")
    local_now = now.astimezone(ZoneInfo(timezone_name))
    if active_override_for_schedule(schedule, now=local_now, timezone_name=timezone_name):
        raise ValueError(f"Active override already exists for {profile_slug}")
    current = resolve_schedule_occurrence(schedule, now=local_now, timezone_name=timezone_name)
    local_effective = effective_meeting_at.astimezone(ZoneInfo(timezone_name))
    if local_effective <= local_now:
        raise ValueError("effective_meeting_at must be in the future")
    override = {
        "override_id": override_id or f"ovr_{int(local_now.timestamp())}",
        "kind": "reschedule_once",
        "original_meeting_at": current["meeting_at"].isoformat(),
        "effective_meeting_at": local_effective.isoformat(),
        "status": "active",
        "created_at": local_now.isoformat(),
        "source": deepcopy(source),
    }
    schedule.setdefault("overrides", []).append(override)
    save_schedule_registry(registry)
    return deepcopy(override)


def consume_override_for_occurrence(profile_slug: str, *, meeting_at: datetime, consumed_at: datetime) -> dict[str, Any] | None:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    schedule = registry.get("profiles", {}).get(profile_slug)
    if not schedule:
        return None
    meeting_text = meeting_at.astimezone(ZoneInfo(timezone_name)).isoformat()
    for override in schedule.get("overrides", []) or []:
        if str(override.get("status") or "") != "active":
            continue
        if str(override.get("effective_meeting_at") or "") != meeting_text:
            continue
        override["status"] = "consumed"
        override["consumed_at"] = consumed_at.astimezone(ZoneInfo(timezone_name)).isoformat()
        save_schedule_registry(registry)
        return deepcopy(override)
    return None


def cancel_override(profile_slug: str, *, now: datetime, override_id: str | None = None) -> dict[str, Any] | None:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    schedule = registry.get("profiles", {}).get(profile_slug)
    if not schedule:
        raise KeyError(f"Schedule not found for {profile_slug}")
    local_now = now.astimezone(ZoneInfo(timezone_name))
    for override in schedule.get("overrides", []) or []:
        if str(override.get("status") or "") != "active":
            continue
        if override_id and str(override.get("override_id") or "") != override_id:
            continue
        override["status"] = "cancelled"
        override["cancelled_at"] = local_now.isoformat()
        save_schedule_registry(registry)
        return deepcopy(override)
    return None


def due_reminders(*, now: datetime | None = None, grace_seconds: int = GRACE_SECONDS) -> list[dict[str, Any]]:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or DEFAULT_TIMEZONE)
    local_now = (now or datetime.now(ZoneInfo(timezone_name))).astimezone(ZoneInfo(timezone_name))
    due: list[dict[str, Any]] = []
    for profile_slug, schedule in registry.get("profiles", {}).items():
        if not schedule.get("enabled", True):
            continue
        report = load_report(profile_slug)
        if not report:
            continue
        try:
            resolved = resolve_schedule_occurrence(schedule, now=local_now, timezone_name=timezone_name)
            meeting_at = resolved["meeting_at"]
            prep_at = resolved["prep_at"]
        except Exception:
            continue
        if prep_at <= local_now <= prep_at + timedelta(seconds=grace_seconds):
            due.append(
                DueReminder(
                    profile_slug=profile_slug,
                    report=report,
                    schedule=schedule,
                    base_meeting_at=resolved["base_meeting_at"],
                    base_prep_at=resolved["base_prep_at"],
                    meeting_at=meeting_at,
                    prep_at=prep_at,
                    override=resolved["override"],
                ).to_dict()
            )
    due.sort(key=lambda item: (item["prep_at"], item["profile_slug"]))
    return due

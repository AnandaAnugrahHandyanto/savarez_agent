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
    meeting_at: datetime
    prep_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_slug": self.profile_slug,
            "report": self.report,
            "schedule": self.schedule,
            "meeting_at": self.meeting_at,
            "prep_at": self.prep_at,
        }



def get_schedules_root() -> Path:
    root = get_people_manager_root() / SCHEDULES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root



def get_schedule_registry_path() -> Path:
    return get_schedules_root() / SCHEDULES_FILENAME



def default_schedule_registry() -> dict[str, Any]:
    return {"version": 1, "timezone": DEFAULT_TIMEZONE, "profiles": {}, "archived_profiles": {}}



def load_schedule_registry() -> dict[str, Any]:
    path = get_schedule_registry_path()
    if not path.exists():
        registry = default_schedule_registry()
        save_schedule_registry(registry)
        return registry
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("timezone", DEFAULT_TIMEZONE)
    data.setdefault("profiles", {})
    data.setdefault("archived_profiles", {})
    return data



def save_schedule_registry(registry: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(registry)
    payload.setdefault("version", 1)
    payload.setdefault("timezone", DEFAULT_TIMEZONE)
    payload.setdefault("profiles", {})
    payload.setdefault("archived_profiles", {})
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



def next_schedule_times(schedule: dict[str, Any], *, now: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    meeting = schedule.get("meeting", {})
    meeting_at = next_meeting_occurrence(meeting, now=now, timezone_name=timezone_name)
    prep_offset = int(schedule.get("prep_offset_minutes", DEFAULT_PREP_OFFSET_MINUTES))
    prep_at = meeting_at - timedelta(minutes=prep_offset)
    return meeting_at, prep_at



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
            meeting = schedule.get("meeting", {})
            meeting_at = next_meeting_occurrence(meeting, now=local_now, timezone_name=timezone_name)
            prep_offset = int(schedule.get("prep_offset_minutes", DEFAULT_PREP_OFFSET_MINUTES))
            prep_at = meeting_at - timedelta(minutes=prep_offset)
        except Exception:
            continue
        if prep_at <= local_now <= prep_at + timedelta(seconds=grace_seconds):
            due.append(
                DueReminder(
                    profile_slug=profile_slug,
                    report=report,
                    schedule=schedule,
                    meeting_at=meeting_at,
                    prep_at=prep_at,
                ).to_dict()
            )
    due.sort(key=lambda item: (item["prep_at"], item["profile_slug"]))
    return due

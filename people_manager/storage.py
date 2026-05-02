from __future__ import annotations

import json
import os
import re
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

from .constants import (
    CADENCE_VALUES,
    CATEGORY_VALUES,
    EXTERNAL_RELATIONSHIP_KINDS,
    INTERNAL_RANK_VALUES,
    INTERNAL_RELATIONSHIP_KINDS,
    PERFORMANCE_VALUES,
    PROFILE_TYPES,
    PROJECT_DIRNAME,
    REGISTRY_FILENAME,
    REPORTS_DIRNAME,
    TEAM_SNAPSHOTS_DIRNAME,
    TRUST_VALUES,
    VERSION,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slugify_name(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return text or "report"


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def get_people_manager_root() -> Path:
    configured_root = os.getenv("PEOPLEOS_DATA_ROOT")
    root = Path(configured_root).expanduser() if configured_root else get_hermes_home() / "projects" / PROJECT_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    (root / REPORTS_DIRNAME).mkdir(parents=True, exist_ok=True)
    (root / TEAM_SNAPSHOTS_DIRNAME).mkdir(parents=True, exist_ok=True)
    return root


def get_registry_path() -> Path:
    return get_people_manager_root() / REGISTRY_FILENAME


def get_report_path(slug: str) -> Path:
    return get_people_manager_root() / REPORTS_DIRNAME / f"{slug}.json"


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def default_registry() -> dict[str, Any]:
    return {
        "version": VERSION,
        "updated_at": utc_now_iso(),
        "reports": {},
    }


def load_registry() -> dict[str, Any]:
    path = get_registry_path()
    if not path.exists():
        registry = default_registry()
        _atomic_json_write(path, registry)
        return registry
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", VERSION)
    data.setdefault("updated_at", utc_now_iso())
    data.setdefault("reports", {})
    return data


def save_registry(registry: dict[str, Any]) -> dict[str, Any]:
    registry = deepcopy(registry)
    registry["updated_at"] = utc_now_iso()
    _atomic_json_write(get_registry_path(), registry)
    return registry


def default_report(*, name: str, role_title: str, mandate: str) -> dict[str, Any]:
    now = utc_now_iso()
    slug = slugify_name(name)
    return {
        "version": VERSION,
        "name": name,
        "slug": slug,
        "role_title": role_title,
        "category": "Nexus",
        "rank": 101,
        "roles": role_title,
        "mandates": mandate,
        "trust": "Normal",
        "cadence": "monthly",
        "cadence_details": {},
        "last_meeting_date": None,
        "last_meeting_date_overridden": False,
        "last_meeting_date_source": "database",
        "last_meeting_notes": "",
        "next_meeting_date": None,
        "next_meeting_date_overridden": False,
        "next_meeting_date_source": "calculated",
        "prep_notes": "",
        "performance_rating": "meets expectations",
        "long_term_notes_todos": "",
        "profile_type": "internal",
        "relationship_kind": "direct_report",
        "internal_rank": None,
        "last_touch_at": None,
        "next_checkup_at": None,
        "checkup_cadence": None,
        "function": "",
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "role_charter": {
            "mandate": mandate,
            "what_good_looks_like": [],
            "current_priorities": [],
            "decision_rights": [],
            "interfaces": [],
        },
        "goals": {
            "current_okrs_or_kpis": [],
            "expected_outputs": [],
            "measures_of_success": [],
            "review_window": None,
            "last_goal_refresh_at": None,
        },
        "operating_state": {
            "energy_level": "unknown",
            "focus_quality": "unknown",
            "execution_reliability": "unknown",
            "communication_quality": "unknown",
            "decision_velocity": "unknown",
            "ownership_level": "unknown",
            "team_health_impact": "unknown",
        },
        "strengths": "",
        "weaknesses": "",
        "failure_modes": [],
        "performance": {
            "current_performance_read": None,
            "trajectory": "unclear",
            "scope_fit": "unclear",
            "confidence_level_in_read": "low",
            "evidence_basis": [],
        },
        "management_strategy": {
            "how_michael_should_manage_them": [],
            "feedback_that_works": [],
            "pressure_that_backfires": [],
            "current_manager_interventions": [],
            "support_needed": [],
            "stretch_opportunities": [],
        },
        "open_loops": {
            "open_todos_for_them": [],
            "open_todos_for_michael": [],
            "unresolved_questions": [],
            "active_risks": [],
            "current_focus_topics": [],
            "next_review_date": None,
        },
        "open_loop_items": [],
        "interaction_log": [],
    }


def _deep_merge_defaults(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_defaults(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _normalize_open_loop_items(report: dict[str, Any]) -> None:
    loops = report.setdefault("open_loops", {})
    items = report.setdefault("open_loop_items", [])
    if items:
        return
    generated: list[dict[str, Any]] = []
    counter = 1
    bucket_map = {
        "open_todos_for_them": "report",
        "open_todos_for_michael": "manager",
        "unresolved_questions": "question",
        "active_risks": "risk",
    }
    for bucket, owner in bucket_map.items():
        for text in loops.get(bucket, []) or []:
            text_value = str(text or "").strip()
            if not text_value:
                continue
            generated.append(
                {
                    "id": f"loop_{counter:04d}",
                    "text": text_value,
                    "owner": owner,
                    "status": "open",
                    "source_bucket": bucket,
                }
            )
            counter += 1
    report["open_loop_items"] = generated


def _as_multiline_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _as_int_rank(value: Any) -> int:
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return 101
    return rank if 1 <= rank <= 101 else 101


def _normalize_clean_profile_fields(report: dict[str, Any]) -> None:
    category = str(report.get("category") or "").strip()
    if not category or (category == "Nexus" and str(report.get("profile_type") or "internal").lower() == "external"):
        if str(report.get("profile_type") or "internal").lower() == "external":
            category = "External"
        elif str(report.get("relationship_kind") or "").lower() in {"satellite", "satellites"}:
            category = "Satellites"
        else:
            category = "Nexus"
    if category.lower() == "external":
        category = "External"
    elif category.lower() in {"satellite", "satellites"}:
        category = "Satellites"
    elif category not in CATEGORY_VALUES:
        category = "Nexus"
    report["category"] = category

    report["profile_type"] = "external" if category == "External" else "internal"
    if category == "Satellites" and not report.get("relationship_kind"):
        report["relationship_kind"] = "satellites"

    report["rank"] = _as_int_rank(report.get("rank"))
    roles = _as_multiline_text(report.get("roles") or report.get("role_title"))
    mandates = _as_multiline_text(report.get("mandates") or (report.get("role_charter") or {}).get("mandate") or report.get("mandate"))
    report["roles"] = roles
    report["mandates"] = mandates
    report["role_title"] = "; ".join(line for line in roles.splitlines() if line.strip())
    report.setdefault("role_charter", {})["mandate"] = mandates

    trust = str(report.get("trust") or "Normal").strip()
    report["trust"] = trust if trust in TRUST_VALUES else "Normal"
    cadence = str(report.get("cadence") or report.get("checkup_cadence") or "monthly").strip().lower()
    report["cadence"] = cadence if cadence in CADENCE_VALUES else "monthly"
    report["checkup_cadence"] = report["cadence"]
    report["cadence_details"] = report.get("cadence_details") if isinstance(report.get("cadence_details"), dict) else {}

    report["last_meeting_notes"] = _as_multiline_text(report.get("last_meeting_notes"))
    report["prep_notes"] = _as_multiline_text(report.get("prep_notes"))
    report["long_term_notes_todos"] = _as_multiline_text(report.get("long_term_notes_todos"))
    report["strengths"] = _as_multiline_text(report.get("strengths"))
    report["weaknesses"] = _as_multiline_text(report.get("weaknesses"))

    performance_rating = str(report.get("performance_rating") or (report.get("performance") or {}).get("current_performance_read") or "meets expectations").strip().lower()
    report["performance_rating"] = performance_rating if performance_rating in PERFORMANCE_VALUES else "meets expectations"
    report.setdefault("performance", {})["current_performance_read"] = report["performance_rating"]


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _add_month_clamped(base: date) -> date:
    year = base.year + (1 if base.month == 12 else 0)
    month = 1 if base.month == 12 else base.month + 1
    day = min(base.day, monthrange(year, month)[1])
    return date(year, month, day)


def _nth_weekday_of_month(year: int, month: int, weekday_name: str, week_of_month: Any) -> date | None:
    weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    target = weekdays.get(str(weekday_name or "").strip().lower())
    if target is None:
        return None
    last_day = monthrange(year, month)[1]
    if str(week_of_month) == "last":
        current = date(year, month, last_day)
        while current.weekday() != target:
            current -= timedelta(days=1)
        return current
    try:
        nth = int(week_of_month)
    except (TypeError, ValueError):
        return None
    if nth < 1 or nth > 4:
        return None
    current = date(year, month, 1)
    while current.weekday() != target:
        current += timedelta(days=1)
    current += timedelta(days=7 * (nth - 1))
    return current if current.month == month else None


def _weekday_index(weekday_name: Any) -> int | None:
    weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    return weekdays.get(str(weekday_name or "").strip().lower())


def _next_weekday_on_or_after(reference: date, weekday_name: Any) -> date:
    target = _weekday_index(weekday_name)
    if target is None:
        return reference
    delta = (target - reference.weekday()) % 7
    return reference + timedelta(days=delta)


def calculate_next_meeting_date(reference_date: Any, cadence: str, cadence_details: dict[str, Any] | None = None) -> str | None:
    reference = _parse_date(reference_date) or datetime.now(timezone.utc).date()
    cadence = str(cadence or "monthly").strip().lower()
    details = cadence_details or {}
    if cadence == "weekly":
        return _date_iso(_next_weekday_on_or_after(reference, details.get("weekday")))
    if cadence == "biweekly":
        current = _next_weekday_on_or_after(reference, details.get("weekday"))
        parity = str(details.get("week_parity") or "").strip().lower()
        while parity in {"odd", "even"} and ((current.isocalendar().week % 2 == 1) != (parity == "odd")):
            current += timedelta(days=7)
        return _date_iso(current)
    next_month = _add_month_clamped(reference)
    scheduled = _nth_weekday_of_month(next_month.year, next_month.month, str(details.get("weekday") or ""), details.get("week_of_month"))
    return _date_iso(scheduled or next_month)


def _normalize_meeting_dates(report: dict[str, Any]) -> None:
    if report.get("last_meeting_date_overridden"):
        report["last_meeting_date"] = report.get("last_meeting_date") or report.get("last_touch_at")
        report["last_meeting_date_source"] = "manual"
    else:
        report["last_meeting_date"] = report.get("last_touch_at") or report.get("last_meeting_date")
        report["last_meeting_date_source"] = "database"
    report["last_touch_at"] = report.get("last_meeting_date")

    if report.get("next_meeting_date_overridden"):
        report["next_meeting_date"] = report.get("next_meeting_date") or report.get("next_checkup_at")
        report["next_meeting_date_source"] = "manual"
    else:
        reference_date = report.get("calculation_reference_date") or report.get("next_meeting_calculation_reference_date")
        report["next_meeting_date"] = calculate_next_meeting_date(reference_date, str(report.get("cadence") or "monthly"), report.get("cadence_details") or {})
        report["next_meeting_date_source"] = "calculated"
    report["next_checkup_at"] = report.get("next_meeting_date")


def _normalize_taxonomy(report: dict[str, Any]) -> None:
    profile_type = str(report.get("profile_type") or "internal").strip().lower()
    if profile_type not in PROFILE_TYPES:
        profile_type = "internal"
    report["profile_type"] = profile_type

    relationship_kind = str(report.get("relationship_kind") or "").strip().lower()
    if profile_type == "external":
        if relationship_kind not in EXTERNAL_RELATIONSHIP_KINDS:
            relationship_kind = "other"
        report["relationship_kind"] = relationship_kind
        report["internal_rank"] = None
        performance = report.setdefault("performance", {})
        performance["current_performance_read"] = None
        return

    if relationship_kind not in INTERNAL_RELATIONSHIP_KINDS:
        relationship_kind = "direct_report"
    report["relationship_kind"] = relationship_kind
    rank = report.get("internal_rank")
    report["internal_rank"] = rank if rank in INTERNAL_RANK_VALUES else None


def normalize_report(report: dict[str, Any]) -> dict[str, Any]:
    raw = deepcopy(report or {})
    normalized = _deep_merge_defaults(
        default_report(
            name=str(raw.get("name") or raw.get("slug") or "Unknown"),
            role_title=str(raw.get("role_title") or ""),
            mandate=str((raw.get("role_charter") or {}).get("mandate") or raw.get("mandate") or ""),
        ),
        raw,
    )
    normalized["slug"] = str(normalized.get("slug") or slugify_name(str(normalized.get("name") or "Unknown")))
    normalized["name"] = str(normalized.get("name") or normalized["slug"])
    normalized.setdefault("version", VERSION)
    _normalize_clean_profile_fields(normalized)
    _normalize_meeting_dates(normalized)
    _normalize_taxonomy(normalized)
    _normalize_open_loop_items(normalized)
    return normalized


def load_report(slug: str) -> dict[str, Any] | None:
    path = get_report_path(slug)
    if not path.exists():
        return None
    return normalize_report(json.loads(path.read_text(encoding="utf-8")))


def save_report(report: dict[str, Any]) -> dict[str, Any]:
    report = normalize_report(report)
    report["updated_at"] = utc_now_iso()
    _atomic_json_write(get_report_path(report["slug"]), report)
    return report


def create_report(name: str, role_title: str, mandate: str, **metadata: Any) -> dict[str, Any]:
    report = default_report(name=name, role_title=role_title, mandate=mandate)
    for key in (
        "category",
        "rank",
        "roles",
        "mandates",
        "trust",
        "cadence",
        "cadence_details",
        "last_meeting_date",
        "last_meeting_date_overridden",
        "last_meeting_date_source",
        "last_meeting_notes",
        "next_meeting_date",
        "next_meeting_date_overridden",
        "next_meeting_date_source",
        "prep_notes",
        "performance_rating",
        "long_term_notes_todos",
        "strengths",
        "weaknesses",
        "profile_type",
        "relationship_kind",
        "internal_rank",
        "last_touch_at",
        "next_checkup_at",
        "checkup_cadence",
    ):
        if key in metadata:
            report[key] = metadata[key]
    report = save_report(report)

    registry = load_registry()
    registry["reports"][report["slug"]] = {
        "name": name,
        "normalized_name": normalize_name(name),
        "slug": report["slug"],
        "role_title": report.get("role_title") or role_title,
        "category": report.get("category"),
        "rank": report.get("rank"),
        "roles": report.get("roles"),
        "trust": report.get("trust"),
        "cadence": report.get("cadence"),
        "profile_type": report.get("profile_type"),
        "relationship_kind": report.get("relationship_kind"),
        "internal_rank": report.get("internal_rank"),
        "last_touch_at": report.get("last_touch_at"),
        "next_checkup_at": report.get("next_checkup_at"),
        "checkup_cadence": report.get("checkup_cadence"),
        "status": report["status"],
        "created_at": report["created_at"],
        "updated_at": report["updated_at"],
        "last_touched_at": report["updated_at"],
        "last_accessed_at": report["updated_at"],
    }
    save_registry(registry)
    return load_report(report["slug"])


def touch_report(slug: str) -> None:
    registry = load_registry()
    if slug not in registry["reports"]:
        return
    now = utc_now_iso()
    registry["reports"][slug]["updated_at"] = now
    registry["reports"][slug]["last_touched_at"] = now
    registry["reports"][slug].setdefault("last_accessed_at", now)
    registry["reports"][slug]["last_accessed_at"] = now
    save_registry(registry)


def access_report(slug: str) -> None:
    registry = load_registry()
    if slug not in registry["reports"]:
        return
    registry["reports"][slug]["last_accessed_at"] = utc_now_iso()
    save_registry(registry)


def list_reports_by_recency() -> list[dict[str, Any]]:
    registry = load_registry()
    reports = list(registry["reports"].values())
    reports.sort(key=lambda item: (item.get("last_touched_at", ""), item.get("updated_at", ""), item.get("name", "")), reverse=True)
    return reports


def find_report_by_name(name: str) -> dict[str, Any] | None:
    registry = load_registry()
    normalized = normalize_name(name)
    for meta in registry["reports"].values():
        if meta.get("normalized_name") == normalized or meta.get("slug") == slugify_name(name):
            return meta
    return None


def resolve_report_by_name(name: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    registry = load_registry()
    reports = [meta for meta in registry["reports"].values() if str(meta.get("status") or "active") != "archived"]
    normalized = normalize_name(name)
    slug = slugify_name(name)

    for meta in reports:
        if meta.get("normalized_name") == normalized or meta.get("slug") == slug:
            return meta, []

    first_token = normalized.split(" ", 1)[0] if normalized else ""
    if not first_token or normalized != first_token:
        return None, []

    matches = []
    for meta in reports:
        meta_name = str(meta.get("name") or "")
        meta_first = normalize_name(meta_name).split(" ", 1)[0]
        if meta_first == first_token:
            matches.append(meta)

    if len(matches) == 1:
        return matches[0], []
    if len(matches) > 1:
        matches.sort(key=lambda item: str(item.get("name") or ""))
        return None, matches
    return None, []

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

from .constants import PROJECT_DIRNAME, REGISTRY_FILENAME, REPORTS_DIRNAME, TEAM_SNAPSHOTS_DIRNAME, VERSION


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slugify_name(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return text or "report"


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def get_people_manager_root() -> Path:
    root = get_hermes_home() / "projects" / PROJECT_DIRNAME
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
        "strengths": [],
        "weaknesses": [],
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
            "next_review_date": None,
        },
        "interaction_log": [],
    }


def load_report(slug: str) -> dict[str, Any] | None:
    path = get_report_path(slug)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_report(report: dict[str, Any]) -> dict[str, Any]:
    report = deepcopy(report)
    report["updated_at"] = utc_now_iso()
    _atomic_json_write(get_report_path(report["slug"]), report)
    return report


def create_report(name: str, role_title: str, mandate: str) -> dict[str, Any]:
    report = default_report(name=name, role_title=role_title, mandate=mandate)
    save_report(report)

    registry = load_registry()
    registry["reports"][report["slug"]] = {
        "name": name,
        "normalized_name": normalize_name(name),
        "slug": report["slug"],
        "role_title": role_title,
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
    reports = list(registry["reports"].values())
    normalized = normalize_name(name)
    slug = slugify_name(name)

    for meta in reports:
        if meta.get("normalized_name") == normalized or meta.get("slug") == slug:
            return meta, []

    first_token = normalized.split(" ", 1)[0] if normalized else ""
    if not first_token:
        return None, []

    matches = []
    for meta in reports:
        meta_name = str(meta.get("name") or "")
        meta_first = normalize_name(meta_name).split(" ", 1)[0]
        if meta_first.startswith(first_token):
            matches.append(meta)

    if len(matches) == 1:
        return matches[0], []
    if len(matches) > 1:
        matches.sort(key=lambda item: str(item.get("name") or ""))
        return None, matches
    return None, []

from __future__ import annotations

from typing import Any

from .prep_renderer import render_prep_note
from .schedule_store import load_schedule_registry
from .storage import load_report, resolve_report_by_name


def resolve_prep_report(name: str) -> tuple[dict[str, Any] | None, str | None]:
    meta, matches = resolve_report_by_name(name)
    if meta:
        return meta, None
    if matches:
        names = ", ".join(str(item.get("name") or item.get("slug") or "Unknown") for item in matches)
        return None, f"Multiple direct reports match `{name}`: {names}. Use full name."
    return None, f"No direct report found for `{name}`. Start with `New report: {name} - <role> - <mandate>`."


def load_schedule_for_slug(slug: str) -> dict[str, Any] | None:
    registry = load_schedule_registry()
    return registry.get("profiles", {}).get(slug)


def build_ad_hoc_prep_note(name: str) -> str:
    meta, error = resolve_prep_report(name)
    if not meta:
        return str(error)
    report = load_report(str(meta["slug"]))
    if not report:
        return f"Report record for `{name}` is missing on disk."
    return render_prep_note(report, title_mode="adhoc")

from __future__ import annotations

from typing import Any

from .schedule_store import load_schedule_registry
from .storage import load_report, resolve_report_by_name

MAX_LINES = 8


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


def _normalize_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def build_ad_hoc_prep_note(name: str) -> str:
    meta, error = resolve_prep_report(name)
    if not meta:
        return str(error)
    report = load_report(str(meta["slug"]))
    if not report:
        return f"Report record for `{name}` is missing on disk."
    schedule = load_schedule_for_slug(str(meta["slug"]))

    upcoming = report.get("upcoming_one_on_one") or {}
    open_loops = report.get("open_loops") or {}
    management = report.get("management_strategy") or {}

    bullets: list[str] = []
    seen: set[str] = set()

    def add(items: list[str], *, prefix: str = "") -> None:
        for item in items:
            text = f"{prefix}{item}" if prefix else item
            if text and text not in seen:
                seen.add(text)
                bullets.append(text)

    add(_normalize_lines(upcoming.get("ritual")))
    add(_normalize_lines(upcoming.get("topics")))
    add(_normalize_lines(open_loops.get("open_todos_for_michael")))
    add(_normalize_lines(management.get("how_michael_should_manage_them")))
    relationship_goal = str(upcoming.get("relationship_goal") or report.get("relationship_note") or "").strip()
    if relationship_goal:
        add([relationship_goal], prefix="tone: ")

    if not bullets:
        add(["weekly/monthly alignment", "check current priorities"])

    lines = [f"{report.get('name') or meta.get('name') or name} 1:1"]
    for bullet in bullets[: MAX_LINES - 1]:
        lines.append(f"- {bullet}")

    if schedule and len(lines) < 2:
        lines.append(f"- cadence offset {int(schedule.get('prep_offset_minutes') or 5)}m")
    return "\n".join(lines)

from __future__ import annotations

from typing import Any

MAX_BULLETS = 6
MAX_CHARS_SOFT = 350
_METADATAISH_KEYS = {"example_shape", "status", "style", "notes", "schema"}


def _normalize_lines(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    if isinstance(values, dict):
        result: list[str] = []
        for key, value in values.items():
            if key in _METADATAISH_KEYS:
                continue
            result.extend(_normalize_lines(value))
        return result
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def candidate_prep_bullets(report: dict[str, Any]) -> list[str]:
    upcoming = report.get("upcoming_one_on_one") or {}
    open_loops = report.get("open_loops") or {}
    strategy = report.get("management_strategy") or {}
    role_charter = report.get("role_charter") or {}

    bullets: list[str] = []
    bullets.extend(_normalize_lines(upcoming.get("ritual")))
    bullets.extend(_normalize_lines(report.get("one_on_one_cadence_notes")))
    bullets.extend(_normalize_lines(upcoming.get("topics")))
    bullets.extend(_normalize_lines(report.get("prep_note_preference")))
    bullets.extend(_normalize_lines(open_loops.get("open_todos_for_michael")))
    bullets.extend(_normalize_lines(strategy.get("how_michael_should_manage_them")))
    bullets.extend(_normalize_lines(open_loops.get("current_focus_topics")))

    if not bullets:
        bullets.extend(_normalize_lines(role_charter.get("current_priorities"))[:2])
    if not bullets:
        bullets = ["weekly/monthly alignment", "check current priorities"]
    return _dedupe(bullets)


def candidate_tone_lines(report: dict[str, Any]) -> list[str]:
    upcoming = report.get("upcoming_one_on_one") or {}
    tones = []
    for source in (
        upcoming.get("relationship_goal"),
        report.get("relationship_context"),
        report.get("relationship_note"),
    ):
        tones.extend(_normalize_lines(source))
    deduped = _dedupe([f"tone: {item}" if not str(item).startswith("tone:") else str(item) for item in tones])
    return deduped[:1]


def build_prep_lines(report: dict[str, Any]) -> list[str]:
    bullets = candidate_prep_bullets(report)[: MAX_BULLETS - 1]
    tone_lines = candidate_tone_lines(report)
    combined = bullets + tone_lines
    if not combined:
        combined = ["weekly/monthly alignment", "check current priorities"]
    return combined[:MAX_BULLETS]


def render_prep_note(
    report: dict[str, Any],
    *,
    minutes_until: int = 5,
    title_mode: str = "scheduled",
) -> str:
    name = report.get("name") or report.get("slug") or "Unknown"
    if title_mode == "adhoc":
        title = f"{name} 1:1"
    else:
        title = f"{name} 1:1 in {minutes_until}m"

    lines = [title]
    for bullet in build_prep_lines(report):
        lines.append(f"- {bullet}")

    text = "\n".join(lines)
    if len(text) <= MAX_CHARS_SOFT:
        return text

    trimmed = [lines[0]]
    for line in lines[1:]:
        candidate = "\n".join(trimmed + [line])
        if len(candidate) > MAX_CHARS_SOFT and len(trimmed) > 2:
            break
        trimmed.append(line)
    return "\n".join(trimmed)


def render_fallback_prep_note(report: dict[str, Any], *, minutes_until: int = 5) -> str:
    name = report.get("name") or report.get("slug") or "Unknown"
    lines = [f"{name} 1:1 in {minutes_until}m"]
    for bullet in build_prep_lines(report)[:3]:
        lines.append(f"- {bullet}")
    lines.append("- Miya response delayed")
    return "\n".join(lines)

from __future__ import annotations

from typing import Any

MAX_BULLETS = 6
MAX_CHARS_SOFT = 350



def _normalize_lines(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result



def render_prep_note(report: dict[str, Any], *, minutes_until: int = 5) -> str:
    name = report.get("name") or report.get("slug") or "Unknown"
    bullets: list[str] = []

    bullets.extend(_normalize_lines(report.get("prep_note_preference")))

    upcoming = report.get("upcoming_one_on_one") or {}
    bullets.extend(_normalize_lines(upcoming.get("topics")))

    cadence_notes = _normalize_lines(report.get("one_on_one_cadence_notes"))
    bullets.extend(cadence_notes)

    current_priorities = _normalize_lines(report.get("role_charter", {}).get("current_priorities"))
    if not bullets:
        bullets.extend(current_priorities[:2])

    deduped: list[str] = []
    for bullet in bullets:
        if bullet not in deduped:
            deduped.append(bullet)
    bullets = deduped[: MAX_BULLETS - 1]

    if not bullets:
        bullets = ["weekly/monthly alignment", "check current priorities"]

    relationship_note = str(report.get("relationship_note") or "").strip()
    if relationship_note:
        bullets.append(f"tone: {relationship_note}")

    lines = [f"{name} 1:1 in {minutes_until}m"]
    for bullet in bullets[:MAX_BULLETS]:
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

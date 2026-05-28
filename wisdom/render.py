"""Telegram-friendly rendering for Wisdom Kernel results."""

from __future__ import annotations

from datetime import datetime

from wisdom.models import ApplicationRecord, CaptureRecord, InterpretationRecord, StatusSnapshot


def render_help() -> str:
    return (
        "Wisdom commands:\n"
        "/wisdom status\n"
        "/wisdom capture <text>\n"
        "/wisdom inbox\n"
        "/wisdom search <query>\n"
        "/wisdom original <id>\n"
        "/wisdom interpret <id>\n"
        "/wisdom apply <id>\n"
        "/wisdom archive <id>\n"
        "/wisdom review\n"
        "/wisdom on | /wisdom off"
    )


def render_capture(capture: CaptureRecord) -> str:
    return (
        f"Captured #{capture.id} - {capture.category.title()} - {capture.source_type.title()}\n"
        "Original saved exactly."
    )


def render_blocked_secret() -> str:
    return "Capture blocked because the text looks like it contains a secret."


def render_status(snapshot: StatusSnapshot) -> str:
    counts = snapshot.counts
    last = _date(snapshot.last_capture_at) if snapshot.last_capture_at else "never"
    return (
        "Wisdom status\n"
        f"Enabled: {'yes' if snapshot.enabled else 'no'}\n"
        f"Capture mode: {snapshot.capture_mode}\n"
        f"DB: {snapshot.db_path}\n"
        f"Captures: {counts.get('captures', 0)}\n"
        f"Interpretations: {counts.get('interpretations', 0)}\n"
        f"Applications: {counts.get('applications', 0)}\n"
        f"FTS: {'available' if snapshot.fts_available else 'LIKE fallback'}\n"
        f"Last capture: {last}"
    )


def render_captures(title: str, captures: list[CaptureRecord]) -> str:
    if not captures:
        return f"{title}\nNo captures found."
    lines = [title]
    for capture in captures:
        lines.append(
            f"#{capture.id} - {_date(capture.created_at)} - {capture.category} - "
            f"{capture.title}\n  {_excerpt(capture.original_text)}"
        )
    return "\n".join(lines)


def render_original(capture: CaptureRecord) -> str:
    return capture.original_text


def render_interpretation(record: InterpretationRecord | None) -> str:
    if record is None:
        return "No interpretation exists for that capture."
    parts = [
        f"Interpretation for #{record.capture_id}",
        f"Summary: {record.summary}",
    ]
    if record.insight:
        parts.append(f"Insight: {record.insight}")
    if record.why_it_matters:
        parts.append(f"Why it matters: {record.why_it_matters}")
    if record.possible_application:
        parts.append(f"Possible application: {record.possible_application}")
    if record.counterpoint:
        parts.append(f"Counterpoint: {record.counterpoint}")
    parts.append(f"Confidence: {record.confidence:.2f} ({record.method})")
    return "\n".join(parts)


def render_applications(capture_id: int, applications: list[ApplicationRecord]) -> str:
    if not applications:
        return f"No application proposals for #{capture_id}."
    lines = [f"Application proposals for #{capture_id}:"]
    for idx, app in enumerate(applications, start=1):
        lines.append(f"{idx}. {app.title}: {app.body}")
    return "\n".join(lines)


def render_review(counts: dict[str, int], recent: list[CaptureRecord], unapplied: list[CaptureRecord]) -> str:
    count_text = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "none"
    lines = ["Wisdom review", f"By category: {count_text}"]
    lines.append("Recent captures:")
    if recent:
        lines.extend(f"#{c.id} - {c.category} - {c.title}" for c in recent)
    else:
        lines.append("none")
    lines.append("Unapplied candidates:")
    if unapplied:
        lines.extend(f"#{c.id} - {c.category} - {c.title}" for c in unapplied)
    else:
        lines.append("none")
    return "\n".join(lines)


def render_not_found(capture_id: int) -> str:
    return f"Capture #{capture_id} was not found."


def render_error() -> str:
    return "Wisdom command failed. Normal Hermes is still available."


def _date(ts: float | None) -> str:
    if ts is None:
        return "unknown"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _excerpt(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."

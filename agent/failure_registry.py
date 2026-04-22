#!/usr/bin/env python3
"""Structured failure capture for Spar and agent turn failures."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from hermes_constants import get_hermes_home


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(value: str, *, limit: int = 48) -> str:
    cleaned = "".join(
        ch.lower() if ch.isalnum() else "-"
        for ch in str(value or "").strip()
    )
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return (collapsed or "failure")[:limit].strip("-") or "failure"


def _clip(value: Any, *, limit: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _normalize_skills(values: Optional[Iterable[str]]) -> list[str]:
    seen: list[str] = []
    for raw in list(values or []):
        item = str(raw or "").strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def _render_metadata(metadata: Optional[dict[str, Any]]) -> str:
    lines: list[str] = []
    for key, value in sorted((metadata or {}).items()):
        if value in (None, "", [], {}):
            continue
        lines.append(f"- {key}: {_clip(value, limit=400)}")
    return "\n".join(lines)


def record_failure(
    *,
    trigger: str,
    symptom: str,
    root_cause: str,
    fix: str = "",
    prevention: str = "",
    related_skills: Optional[Iterable[str]] = None,
    session_id: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    trigger_text = _clip(trigger, limit=120)
    symptom_text = _clip(symptom)
    root_text = _clip(root_cause)
    if not trigger_text or not (symptom_text or root_text):
        return None

    now = _utc_now()
    failures_dir = get_hermes_home() / "FAILURES"
    failures_dir.mkdir(parents=True, exist_ok=True)

    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    fingerprint = hashlib.sha1(
        f"{now.isoformat()}|{trigger_text}|{session_id}|{symptom_text}".encode("utf-8")
    ).hexdigest()[:8]
    filename = f"{stamp}_{_slug(trigger_text)}_{fingerprint}.md"
    target = failures_dir / filename

    skills = _normalize_skills(related_skills)
    sections = [
        f"# Failure Scar — {trigger_text}",
        "",
        f"- timestamp: {now.isoformat()}",
        f"- session_id: {session_id or 'n/a'}",
        "",
        "## Trigger",
        trigger_text,
        "",
        "## Symptom",
        symptom_text or "n/a",
        "",
        "## Root Cause",
        root_text or "n/a",
        "",
        "## Fix",
        _clip(fix) or "n/a",
        "",
        "## Prevention",
        _clip(prevention) or "n/a",
        "",
        "## Related Skills",
        ", ".join(skills) if skills else "n/a",
    ]

    metadata_block = _render_metadata(metadata)
    if metadata_block:
        sections.extend(["", "## Metadata", metadata_block])

    target.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return target

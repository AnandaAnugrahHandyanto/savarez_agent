from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .storage import get_people_manager_root

REMINDER_LOG_DIRNAME = "reminder-log"
CLAIMS_DIRNAME = "claims"



def get_reminder_log_root() -> Path:
    root = get_people_manager_root() / REMINDER_LOG_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root



def get_reminder_log_path(for_dt: datetime) -> Path:
    return get_reminder_log_root() / f"{for_dt.strftime('%Y-%m')}.jsonl"


def get_claims_root() -> Path:
    root = get_reminder_log_root() / CLAIMS_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_occurrence_claim_path(profile_slug: str, meeting_at: datetime) -> Path:
    safe_meeting = meeting_at.isoformat().replace(":", "-")
    return get_claims_root() / f"{profile_slug}__{safe_meeting}.lock"



def append_reminder_log(entry: dict[str, Any]) -> None:
    meeting_at = datetime.fromisoformat(entry["meeting_at"])
    path = get_reminder_log_path(meeting_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")



def iter_reminder_log(for_dt: datetime):
    path = get_reminder_log_path(for_dt)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            yield json.loads(text)



def reminder_entry_timestamp(entry: dict[str, Any]) -> str:
    return str(
        entry.get("event_at")
        or entry.get("prep_sent_at")
        or entry.get("queued_at")
        or entry.get("detected_at")
        or entry.get("meeting_at")
        or ""
    )



def load_reminder_entries(*, month: str | None = None, profile_slug: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if month:
        base = datetime.fromisoformat(f"{month}-01T00:00:00")
    else:
        base = datetime.now()
    entries = list(iter_reminder_log(base) or [])
    if profile_slug:
        entries = [entry for entry in entries if entry.get("profile_slug") == profile_slug]
    entries.sort(key=reminder_entry_timestamp, reverse=True)
    return entries[:limit]



def was_sent_for_occurrence(profile_slug: str, meeting_at: datetime) -> bool:
    meeting_key = meeting_at.isoformat()
    sent_statuses = {"sent", "sent_by_miya", "fallback_sent"}
    for entry in iter_reminder_log(meeting_at) or []:
        if entry.get("profile_slug") == profile_slug and entry.get("meeting_at") == meeting_key and entry.get("status") in sent_statuses:
            return True
    return False


def claim_occurrence(profile_slug: str, meeting_at: datetime) -> bool:
    path = get_occurrence_claim_path(profile_slug, meeting_at)
    try:
        fd = path.open("x", encoding="utf-8")
    except FileExistsError:
        return False
    with fd:
        fd.write(f"{profile_slug}\n{meeting_at.isoformat()}\n")
    return True


def release_occurrence_claim(profile_slug: str, meeting_at: datetime) -> None:
    path = get_occurrence_claim_path(profile_slug, meeting_at)
    if path.exists():
        path.unlink()

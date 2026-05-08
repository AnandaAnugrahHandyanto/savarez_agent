"""
Session mirroring for out-of-band gateway deliveries.

When a background command, cron job, or cross-platform delivery sends a result
directly through a platform adapter, this module appends a compact assistant
"delivery mirror" record to the matching gateway transcript.  That keeps the
next live turn aware of background work the user already saw.

Standalone -- works from CLI, cron, and gateway contexts without needing the
full SessionStore machinery.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

_SESSIONS_DIR = get_hermes_home() / "sessions"
_SESSIONS_INDEX = _SESSIONS_DIR / "sessions.json"
_LOCK = threading.Lock()


def _now_iso() -> str:
    """Return a timezone-aware ISO timestamp for mirrored transcript records."""
    return datetime.now(timezone.utc).isoformat()


def mirror_to_session(
    platform: str,
    chat_id: str,
    message_text: str,
    source_label: str = "cli",
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    """
    Append a delivery-mirror message to the target session's transcript.

    Finds the gateway session that matches the given platform + chat_id, then
    writes a mirror entry to both the JSONL transcript and SQLite DB.  Returns
    True if mirrored successfully, False if no matching session or error.  All
    errors are caught -- this is never fatal for the original delivery.
    """
    text = (message_text or "").strip()
    if not text:
        return False

    try:
        with _LOCK:
            match = _find_session_entry(
                platform,
                str(chat_id),
                thread_id=thread_id,
                user_id=user_id,
            )
            if not match:
                logger.debug(
                    "Mirror: no session found for %s:%s:%s:%s",
                    platform,
                    chat_id,
                    thread_id,
                    user_id,
                )
                return False

            _session_key, entry = match
            session_id = str(entry.get("session_id") or "").strip()
            if not session_id:
                return False

            timestamp = _now_iso()
            mirror_msg = {
                "role": "assistant",
                "content": text,
                "timestamp": timestamp,
                "mirror": True,
                "mirror_source": source_label,
            }

            _append_to_jsonl(session_id, mirror_msg)
            _append_to_sqlite(session_id, mirror_msg)

            logger.debug("Mirror: wrote to session %s (from %s)", session_id, source_label)
            return True

    except Exception as e:
        logger.debug(
            "Mirror failed for %s:%s:%s:%s: %s",
            platform,
            chat_id,
            thread_id,
            user_id,
            e,
        )
        return False


def _load_sessions_index() -> dict[str, Any]:
    if not _SESSIONS_INDEX.exists():
        return {}
    try:
        with open(_SESSIONS_INDEX, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _find_session_entry(
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[tuple[str, dict[str, Any]]]:
    """
    Find the active session entry for a platform + chat_id pair.

    Scans sessions.json entries and matches where origin.chat_id == chat_id on
    the right platform.  DM session keys don't necessarily embed the chat_id
    (e.g. "agent:main:telegram:dm"), so origin metadata is authoritative.

    When *user_id* is provided, prefer exact sender matches. If multiple
    same-chat candidates exist and none matches the user, return None instead
    of guessing and contaminating another participant's session.
    """
    data = _load_sessions_index()
    if not data:
        return None

    platform_lower = platform.lower()
    candidates: list[tuple[str, dict[str, Any]]] = []

    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        origin = entry.get("origin") or {}
        entry_platform = (origin.get("platform") or entry.get("platform", "")).lower()

        if entry_platform != platform_lower:
            continue

        origin_chat_id = str(origin.get("chat_id", ""))
        if origin_chat_id == str(chat_id):
            origin_thread_id = origin.get("thread_id")
            if thread_id is not None and str(origin_thread_id or "") != str(thread_id):
                continue
            candidates.append((key, entry))

    if not candidates:
        return None

    if user_id:
        exact_user_matches = [
            (key, entry)
            for key, entry in candidates
            if str((entry.get("origin") or {}).get("user_id") or "") == str(user_id)
        ]
        if exact_user_matches:
            candidates = exact_user_matches
        elif len(candidates) > 1:
            return None
    elif len(candidates) > 1:
        distinct_user_ids = {
            str((entry.get("origin") or {}).get("user_id") or "").strip()
            for _key, entry in candidates
            if str((entry.get("origin") or {}).get("user_id") or "").strip()
        }
        if len(distinct_user_ids) > 1:
            return None

    return max(candidates, key=lambda item: item[1].get("updated_at", ""))


def _append_to_jsonl(session_id: str, message: dict[str, Any]) -> None:
    """Append a message to the JSONL transcript file."""
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_path = _SESSIONS_DIR / f"{session_id}.jsonl"
    with open(transcript_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def _append_to_sqlite(session_id: str, message: dict[str, Any]) -> None:
    """Append a message to the SQLite session database."""
    db = None
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        db.append_message(
            session_id=session_id,
            role=message.get("role", "assistant"),
            content=message.get("content"),
        )
    except Exception as e:
        logger.debug("Mirror SQLite write failed: %s", e)
    finally:
        if db is not None:
            db.close()

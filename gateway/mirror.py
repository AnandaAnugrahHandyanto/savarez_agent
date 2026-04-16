"""
Session mirroring for cross-platform message delivery.

When a message is sent to a platform (via send_message or cron delivery),
this module appends a "delivery-mirror" record to the target session's
transcript so the receiving-side agent has context about what was sent.

Standalone -- works from CLI, cron, and gateway contexts without needing
the full SessionStore machinery.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

from hermes_cli.config import get_hermes_home

logger = logging.getLogger(__name__)

_SESSIONS_DIR = get_hermes_home() / "sessions"
_SESSIONS_INDEX = _SESSIONS_DIR / "sessions.json"


def mirror_to_session(
    platform: str,
    chat_id: str,
    message_text: str,
    source_label: str = "cli",
    thread_id: Optional[str] = None,
) -> bool:
    """
    Append a delivery-mirror message to the target session's transcript.

    Finds the gateway session that matches the given platform + chat_id,
    then writes a mirror entry to both the JSONL transcript and SQLite DB.

    Returns True if mirrored successfully, False if no matching session or error.
    All errors are caught -- this is never fatal.
    """
    try:
        timestamp = datetime.now().isoformat()
        sessions_data = _load_sessions_index()
        session_key, session_entry = _find_session_entry(
            sessions_data,
            platform,
            str(chat_id),
            thread_id=thread_id,
        )
        if not session_entry:
            logger.debug("Mirror: no session found for %s:%s:%s", platform, chat_id, thread_id)
            return False
        session_id = session_entry.get("session_id")
        if not session_id:
            logger.debug("Mirror: matching session entry is missing session_id for %s:%s:%s", platform, chat_id, thread_id)
            return False

        mirror_msg = {
            "role": "assistant",
            "content": message_text,
            "timestamp": timestamp,
            "mirror": True,
            "mirror_source": source_label,
        }

        _append_to_jsonl(session_id, mirror_msg)
        _append_to_sqlite(session_id, mirror_msg)
        if session_key is not None:
            _touch_session_entry(sessions_data, session_key, updated_at=timestamp)

        logger.debug("Mirror: wrote to session %s (from %s)", session_id, source_label)
        return True

    except Exception as e:
        logger.debug("Mirror failed for %s:%s:%s: %s", platform, chat_id, thread_id, e)
        return False


def _find_session_id(platform: str, chat_id: str, thread_id: Optional[str] = None) -> Optional[str]:
    """Find the active session_id for a platform + chat_id pair."""
    sessions_data = _load_sessions_index()
    _session_key, session_entry = _find_session_entry(
        sessions_data,
        platform,
        chat_id,
        thread_id=thread_id,
    )
    if not session_entry:
        return None
    return session_entry.get("session_id")


def _load_sessions_index() -> dict[str, dict]:
    if not _SESSIONS_INDEX.exists():
        return {}

    try:
        with open(_SESSIONS_INDEX, encoding="utf-8") as f:
            loaded = json.load(f)
    except Exception:
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _find_session_entry(
    sessions_data: dict[str, dict],
    platform: str,
    chat_id: str,
    *,
    thread_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[dict]]:
    """
    Find the active session entry for a platform + chat_id pair.

    Scans sessions.json entries and matches where origin.chat_id == chat_id
    on the right platform.  DM session keys don't embed the chat_id
    (e.g. "agent:main:telegram:dm"), so we check the origin dict.
    """
    if not sessions_data:
        return None, None

    platform_lower = platform.lower()
    best_match_key = None
    best_match_entry = None
    best_updated = ""

    for entry_key, entry in sessions_data.items():
        origin = entry.get("origin") or {}
        entry_platform = (origin.get("platform") or entry.get("platform", "")).lower()

        if entry_platform != platform_lower:
            continue

        origin_chat_id = str(origin.get("chat_id", ""))
        if origin_chat_id == str(chat_id):
            origin_thread_id = origin.get("thread_id")
            if thread_id is not None and str(origin_thread_id or "") != str(thread_id):
                continue
            updated = entry.get("updated_at", "")
            if updated > best_updated:
                best_updated = updated
                best_match_key = entry_key
                best_match_entry = entry

    return best_match_key, best_match_entry


def _touch_session_entry(
    sessions_data: dict[str, dict],
    session_key: str,
    *,
    updated_at: str,
) -> None:
    """Refresh the matched session's updated_at in sessions.json."""
    if session_key not in sessions_data:
        return

    try:
        sessions_data[session_key]["updated_at"] = updated_at
        _write_sessions_index(sessions_data)
    except Exception as e:
        logger.debug("Mirror session updated_at refresh failed: %s", e)


def _write_sessions_index(sessions_data: dict[str, dict]) -> None:
    """Atomically rewrite sessions.json with updated metadata."""
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(_SESSIONS_DIR), suffix=".tmp", prefix=".sessions_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(sessions_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, _SESSIONS_INDEX)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _append_to_jsonl(session_id: str, message: dict) -> None:
    """Append a message to the JSONL transcript file."""
    transcript_path = _SESSIONS_DIR / f"{session_id}.jsonl"
    try:
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("Mirror JSONL write failed: %s", e)


def _append_to_sqlite(session_id: str, message: dict) -> None:
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

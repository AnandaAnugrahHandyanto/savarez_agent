"""Reaction feedback event store for gateway messages.

This module is deliberately small and dependency-free. It stores two local,
profile-scoped artifacts under ``$HERMES_HOME/state``:

* ``reaction_feedback_sent_index.json`` — bounded index of Hermes-sent message
  ids with route/session metadata and content hashes (not raw text).
* ``reaction_feedback_events.jsonl`` — append-only normalized reaction events.

The event stream is a feedback sensor only. It does not edit prompts, memory,
skills, or user profile state; downstream learning/proposal systems can read the
JSONL and decide what to propose for approval.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_VERSION = "reaction_feedback.v1"
_SENT_INDEX_VERSION = "sent_index.v1"
_MAX_SENT_INDEX_ENTRIES = 5000

_USEFUL = {"👍", "❤️", "❤", "👌", "👏"}
_MISS = {"👎"}
_UNCLEAR = {"🤔", "❓", "?"}
_BAD_TIMING = {"⏰", "😴"}
_TOO_LONG = {"📏"}


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home()
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _state_dir() -> Path:
    return _hermes_home() / "state"


def sent_index_path() -> Path:
    return _state_dir() / "reaction_feedback_sent_index.json"


def events_path() -> Path:
    return _state_dir() / "reaction_feedback_events.jsonl"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _key(platform: str, chat_id: Any, message_id: Any) -> str:
    return f"{platform}:{chat_id}:{message_id}"


def _load_index() -> dict[str, Any]:
    try:
        data = json.loads(sent_index_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"schema_version": _SENT_INDEX_VERSION, "messages": {}}
    if not isinstance(data, dict):
        return {"schema_version": _SENT_INDEX_VERSION, "messages": {}}
    messages = data.get("messages")
    if not isinstance(messages, dict):
        messages = {}
    return {"schema_version": data.get("schema_version") or _SENT_INDEX_VERSION, "messages": messages}


def _write_index(data: dict[str, Any]) -> None:
    path = sent_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _trim_messages(messages: dict[str, Any]) -> None:
    overflow = len(messages) - _MAX_SENT_INDEX_ENTRIES
    if overflow <= 0:
        return
    oldest = sorted(
        messages.items(),
        key=lambda item: (item[1] or {}).get("recorded_ts", 0),
    )[:overflow]
    for key, _ in oldest:
        messages.pop(key, None)


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _content_hash(content: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    if content is None:
        return None, None
    encoded = content.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), len(content)


def _metadata_value(metadata: Optional[dict[str, Any]], *keys: str) -> Optional[str]:
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        value = metadata.get(key)
        if value not in {None, ""}:
            return str(value)
    return None


def record_sent_message(
    *,
    platform: str,
    chat_id: Any,
    message_id: Any,
    thread_id: Any = None,
    content: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    message_kind: str = "assistant",
) -> None:
    """Remember a Hermes-sent message as a possible reaction target.

    Raw message text is never stored. The index keeps route/session metadata and
    a SHA-256 hash/length so downstream reports can correlate reactions without
    copying private assistant content into the feedback store.
    """

    if chat_id is None or message_id is None:
        return
    platform_s = str(platform or "").strip().lower()
    if not platform_s:
        return

    content_sha256, content_chars = _content_hash(content)
    thread = _safe_str(thread_id) or _metadata_value(
        metadata,
        "thread_id",
        "message_thread_id",
        "direct_messages_topic_id",
        "telegram_direct_messages_topic_id",
    )
    entry = {
        "platform": platform_s,
        "chat_id": str(chat_id),
        "thread_id": thread,
        "message_id": str(message_id),
        "message_kind": str(message_kind or "assistant"),
        "session_key": _metadata_value(metadata, "session_key", "gateway_session_key"),
        "session_id": _metadata_value(metadata, "session_id"),
        "content_sha256": content_sha256,
        "content_chars": content_chars,
        "recorded_at": _now_iso(),
        "recorded_ts": time.time(),
    }

    try:
        data = _load_index()
        messages = data.setdefault("messages", {})
        messages[_key(platform_s, chat_id, message_id)] = entry
        _trim_messages(messages)
        _write_index(data)
    except Exception:
        # Feedback capture must never break user-facing delivery.
        return


def lookup_sent_message(platform: str, chat_id: Any, message_id: Any) -> Optional[dict[str, Any]]:
    if chat_id is None or message_id is None:
        return None
    try:
        data = _load_index()
        entry = data.get("messages", {}).get(_key(str(platform or "").strip().lower(), chat_id, message_id))
        return dict(entry) if isinstance(entry, dict) else None
    except Exception:
        return None


def normalize_feedback(emojis: Iterable[str]) -> dict[str, Any]:
    """Map Telegram emoji reactions to the v0 feedback semantics."""

    values = [str(e) for e in emojis if e]
    if not values:
        return {"emoji": None, "emojis": [], "semantic": "cleared", "action": "cleared"}

    emoji = values[0]
    if emoji in _USEFUL:
        semantic = "useful"
    elif emoji in _MISS:
        semantic = "miss"
    elif emoji in _UNCLEAR:
        semantic = "unclear"
    elif emoji in _BAD_TIMING:
        semantic = "bad_timing"
    elif emoji in _TOO_LONG:
        semantic = "too_long"
    else:
        semantic = "other"
    return {"emoji": emoji, "emojis": values, "semantic": semantic, "action": "set"}


def _user_hash(platform: str, user_id: Any) -> Optional[str]:
    if user_id in {None, ""}:
        return None
    return hashlib.sha256(f"{platform}:{user_id}".encode("utf-8")).hexdigest()


def _event_target(entry: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not entry:
        return {"known": False}
    return {
        "known": True,
        "message_kind": entry.get("message_kind"),
        "session_key": entry.get("session_key"),
        "session_id": entry.get("session_id"),
        "content_sha256": entry.get("content_sha256"),
        "content_chars": entry.get("content_chars"),
        "sent_recorded_at": entry.get("recorded_at"),
    }


def record_feedback(
    *,
    platform: str,
    chat_id: Any,
    message_id: Any,
    thread_id: Any = None,
    actor_user_id: Any = None,
    old_emojis: Optional[Iterable[str]] = None,
    new_emojis: Optional[Iterable[str]] = None,
    update_id: Any = None,
) -> dict[str, Any]:
    """Append a normalized reaction feedback event and return it."""

    platform_s = str(platform or "").strip().lower()
    target_entry = lookup_sent_message(platform_s, chat_id, message_id)
    resolved_thread_id = _safe_str(thread_id) or (target_entry or {}).get("thread_id")
    feedback = normalize_feedback(new_emojis or [])
    old_values = [str(e) for e in (old_emojis or []) if e]

    event = {
        "schema_version": SCHEMA_VERSION,
        "event_type": "reaction_feedback",
        "recorded_at": _now_iso(),
        "platform": platform_s,
        "route": {
            "chat_id": str(chat_id) if chat_id is not None else None,
            "thread_id": str(resolved_thread_id) if resolved_thread_id is not None else None,
            "message_id": str(message_id) if message_id is not None else None,
        },
        "update_id": str(update_id) if update_id is not None else None,
        "actor": {
            "user_id_hash": _user_hash(platform_s, actor_user_id),
        },
        "reaction": {
            **feedback,
            "old_emojis": old_values,
        },
        "target": _event_target(target_entry),
        "privacy": {
            "raw_text_stored": False,
            "actor_user_id_stored": False,
        },
        "no_auto_apply": True,
    }

    path = events_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        # Keep the returned event useful for tests/callers, but never raise into
        # the gateway update loop.
        return event
    return event

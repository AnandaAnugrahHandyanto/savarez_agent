"""Read-only Hermes record adapter for ContextOps Events.

Harness-specific quarantine: this module is NOT part of the top-level
``contextops`` core API. Hermes-aware callers import it from the plugin-local
``plugins.context_engine.contextops`` namespace; the harness-agnostic core must
never depend on it.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from contextops.models import Event

MAX_EVENT_TEXT_CHARS = 512
TRANSCRIPT_REF_PREFIX = "hermes:transcript:"
_SAFE_METADATA_KEYS = {"role", "channel", "platform", "safe_label", "thread_id", "message_type"}
_UNSAFE_METADATA_KEYS = {"text", "content", "body", "transcript", "raw_transcript", "messages", "conversation", "history"}

# Safe-ref policy: Event.refs only ever holds short, structured pointers --
# never raw transcript content, filesystem paths, or secret-like material.
MAX_REF_CHARS = 128
MAX_METADATA_VALUE_CHARS = 64
REDACTED = "[redacted]"
# Caller- or adapter-supplied refs are kept only when they match a derived
# safe-ref namespace or a benign hashtag tag.
_SAFE_REF_PREFIXES = ("message:", "session:", "channel:", "hermes:")
_HASHTAG_RE = re.compile(r"^#[\w-]{1,64}$")
_SECRET_HINT_RE = re.compile(
    r"(secret|token|password|passwd|api[_-]?key|apikey|bearer|authorization|credential)",
    re.IGNORECASE,
)
_LONG_HEX_RE = re.compile(r"[0-9a-fA-F]{32,}")
_AWS_ACCESS_KEY_RE = re.compile(r"AKIA[A-Z0-9]{16}")
_JWT_LIKE_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
# Allowlisted string metadata values must be short, printable, whitespace-free
# identifier/tag-like tokens -- not free-text phrases or embedded paths.
_METADATA_TAG_RE = re.compile(r"^[#A-Za-z0-9._:-]{1,64}$")


def _looks_secret_like(value: str) -> bool:
    return bool(
        _SECRET_HINT_RE.search(value)
        or _LONG_HEX_RE.search(value)
        or _AWS_ACCESS_KEY_RE.search(value)
        or _JWT_LIKE_RE.search(value)
    )


def _is_safe_ref(ref: str) -> bool:
    """Return ``True`` only for short, structured, non-leaking refs.

    Rejects raw transcript-like strings (whitespace/sentences), absolute and
    drive-letter paths, token/secret-like values, oversized caller strings, and
    anything outside the derived safe-ref namespaces.
    """

    if not ref or len(ref) > MAX_REF_CHARS:
        return False
    if not ref.isprintable() or any(ch.isspace() for ch in ref):
        return False
    if _HASHTAG_RE.match(ref):
        return True
    for prefix in _SAFE_REF_PREFIXES:
        if ref.startswith(prefix):
            value = ref[len(prefix):]
            if not value or value[0] in "/\\~":
                return False
            if _DRIVE_PATH_RE.match(value):
                return False
            if _looks_secret_like(value):
                return False
            return True
    return False


def _safe_ref_value(value: Any) -> Any:
    """Validate one metadata value, redacting raw/path/secret-like content.

    Numeric and boolean values pass through. String values are fail-closed:
    only short, printable, whitespace-free identifier/tag-like tokens survive,
    so raw phrases (``operator said sensitive things``) and embedded paths
    (``operator pasted /home/op/.env``) cannot be smuggled through metadata.
    """

    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return REDACTED
    if len(value) > MAX_METADATA_VALUE_CHARS or not _METADATA_TAG_RE.match(value):
        return REDACTED
    if _looks_secret_like(value):
        return REDACTED
    return value


def _record_id(record: dict[str, Any]) -> str:
    for key in ("id", "message_id", "event_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("hermes record must carry a non-empty 'id'")


def _first_str(record: dict[str, Any], keys: tuple[str, ...], label: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError(f"hermes record must carry a non-empty {label}")


def _source(record: dict[str, Any]) -> str:
    explicit = record.get("source")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    platform = record.get("platform")
    channel = record.get("channel")
    if isinstance(platform, str) and platform.strip() and isinstance(channel, str) and channel.strip():
        return f"{platform.strip()}/{channel.strip()}"
    return _first_str(record, ("author", "sender"), "source")


def _safe_metadata(record: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in ("role", "channel"):
        value = record.get(key)
        if isinstance(value, (str, int, float, bool)) and value is not None:
            safe[key] = _safe_ref_value(value)

    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if not isinstance(key, str):
                continue
            normalized = key.strip()
            if not normalized or normalized in _UNSAFE_METADATA_KEYS:
                continue
            if normalized in _SAFE_METADATA_KEYS and isinstance(value, (str, int, float, bool)):
                safe[normalized] = _safe_ref_value(value)
    return safe


def hermes_record_to_event(record: dict[str, Any], *, max_text_chars: int = MAX_EVENT_TEXT_CHARS) -> Event:
    """Map one Hermes session/event-like record to a ContextOps Event.

    ``record`` is treated as immutable input -- it is read, never written. A
    record with text over ``max_text_chars`` keeps only a short excerpt; the
    full transcript is referenced via a ``hermes:transcript:<id>`` safe ref.
    """

    if not isinstance(record, dict):
        raise TypeError("hermes record must be a mapping")
    event_id = _record_id(record)
    text = _first_str(record, ("text", "content", "body"), "text")
    refs: list[str] = []
    raw_refs = record.get("refs")
    if isinstance(raw_refs, (list, tuple)):
        for ref in raw_refs:
            if isinstance(ref, str) and ref.strip():
                refs.append(ref.strip())
    refs.append(f"message:{event_id}")
    session_id = record.get("session_id")
    if isinstance(session_id, str) and session_id.strip():
        refs.append(f"session:{session_id.strip()}")
    channel = record.get("channel")
    if isinstance(channel, str) and channel.strip():
        refs.append(f"channel:{channel.strip()}")
    metadata = _safe_metadata(record)
    if len(text) > max_text_chars:
        transcript_ref = f"{TRANSCRIPT_REF_PREFIX}{event_id}"
        refs.append(transcript_ref)
        metadata["transcript_truncated"] = True
        metadata["transcript_chars"] = len(text)
        text = text[:max_text_chars].rstrip() + f" … [transcript truncated; full transcript at ref {transcript_ref}]"
    safe_refs = [ref for ref in dict.fromkeys(refs) if _is_safe_ref(ref)]
    return Event.model_validate({
        "id": event_id,
        "source": _source(record),
        "text": text,
        "refs": safe_refs,
        "metadata": metadata,
    })


def hermes_records_to_events(records: Iterable[dict[str, Any]]) -> list[Event]:
    """Map many Hermes records to Events, preserving input order."""

    return [hermes_record_to_event(record) for record in records]

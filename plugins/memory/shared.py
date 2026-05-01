"""Shared helpers for memory providers.

Centralizes durable-memory metadata hygiene, fingerprinting, and JSON config
merge/write behavior so providers can share the same semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

_DEFAULT_ROLE_MARKER_RE = re.compile(r"\[(role|user:end|assistant:end):?[^\]]*\]", re.IGNORECASE)
_DEFAULT_WHITESPACE_RE = re.compile(r"\s+")
_DEFAULT_BLOCKED_SUBSTRINGS = (
    "token",
    "secret",
    "password",
    "cookie",
    "credential",
    "auth",
    "header",
    "phone",
    "email",
    "address",
    "location",
    "ip",
    "session",
    "message",
    "thread",
    "chat",
    "user",
    "sender",
    "attachment",
    "event",
    "raw",
    "trace",
    "file",
    "path",
    "url",
)
_DEFAULT_BLOCKED_EXACT = {
    "session_id",
    "conversation_id",
    "message_id",
    "thread_id",
    "chat_id",
    "user_id",
    "sender_id",
    "raw_event",
    "attachments",
    "attachment",
    "platform_user_id",
    "platform_chat_id",
    "file_path",
    "filepath",
    "timestamp",
    "created_at",
    "updated_at",
    "trace_id",
    "request_id",
    "agent_id",
}


def normalize_memory_text(text: str) -> str:
    normalized = _DEFAULT_WHITESPACE_RE.sub(" ", (text or "").strip().lower())
    normalized = _DEFAULT_ROLE_MARKER_RE.sub(" ", normalized)
    return _DEFAULT_WHITESPACE_RE.sub(" ", normalized).strip()


def stable_memory_fingerprint(*parts: str) -> str:
    joined = "\n".join(normalize_memory_text(part) for part in parts if part and part.strip())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16] if joined else ""


def should_skip_duplicate_write(fingerprint: str, previous_fingerprint: str) -> bool:
    return bool(fingerprint and previous_fingerprint and fingerprint == previous_fingerprint)


def sanitize_metadata(
    metadata: Any,
    *,
    allowlist: Iterable[str] | None = None,
    blocked_exact: Iterable[str] | None = None,
    blocked_substrings: Iterable[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}

    allowed = {str(item).strip().lower() for item in (allowlist or []) if str(item).strip()}
    blocked_exact_set = {str(item).strip().lower() for item in (blocked_exact or _DEFAULT_BLOCKED_EXACT) if str(item).strip()}
    blocked_substrings_tuple = tuple(
        str(item).strip().lower() for item in (blocked_substrings or _DEFAULT_BLOCKED_SUBSTRINGS) if str(item).strip()
    )

    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if value in (None, "", [], {}, ()):  # drop empty noise
            continue
        key_str = str(key).strip()
        if not key_str:
            continue
        lowered = key_str.lower()
        if lowered in blocked_exact_set:
            continue
        if lowered not in allowed and any(part in lowered for part in blocked_substrings_tuple):
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key_str] = value
    return sanitized


def build_capture_metadata(
    *,
    source: str,
    memory_type: str,
    content: str,
    extra: Any = None,
    allowlist: Iterable[str] | None = None,
    blocked_exact: Iterable[str] | None = None,
    blocked_substrings: Iterable[str] | None = None,
) -> dict[str, Any]:
    metadata = sanitize_metadata(
        extra,
        allowlist=allowlist,
        blocked_exact=blocked_exact,
        blocked_substrings=blocked_substrings,
    )
    metadata["source"] = source
    metadata["type"] = memory_type
    fingerprint = stable_memory_fingerprint(content)
    if fingerprint:
        metadata["fingerprint"] = fingerprint
    return metadata


def merge_json_config(path: str | Path, values: Mapping[str, Any], *, sort_keys: bool = False, trailing_newline: bool = False) -> None:
    config_path = Path(path)
    existing: dict[str, Any] = {}
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = raw
        except Exception:
            existing = {}
    existing.update(dict(values or {}))
    rendered = json.dumps(existing, indent=2, sort_keys=sort_keys)
    if trailing_newline:
        rendered += "\n"
    config_path.write_text(rendered, encoding="utf-8")

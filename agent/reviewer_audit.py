"""Audit logging for background memory/skill reviewers.

This module is deliberately best-effort: audit logging must never break the
user-facing agent turn or the background reviewer itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.redact import redact_sensitive_text
from hermes_constants import get_hermes_home

_AUDIT_LOG_RELATIVE_PATH = Path("logs") / "reviewer_audit.jsonl"
_CONTENT_FIELD_NAMES = {
    "content",
    "conversation",
    "conversation_history",
    "messages",
    "plaintext",
    "prompt",
    "response",
    "text",
    "user_message",
}
_PREVIEW_CHARS = 80
_AUDIT_WRITE_LOCK = threading.Lock()
_SECRET_PREVIEW_MARKERS = (
    "api_key",
    "apikey",
    "auth",
    "bearer ",
    "cookie",
    "password",
    "private-key",
    "private_key",
    "secret",
    "token",
)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _is_content_field(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in _CONTENT_FIELD_NAMES
        or lowered.endswith("_content")
        or lowered.endswith("_plaintext")
    )


def _stringify_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def _safe_scalar(value: Any) -> Any:
    """Return JSON-safe values with secrets redacted from every string field."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_sensitive_text(_stringify_content(value))


def _redact_content_field(record: dict[str, Any], key: str, value: Any) -> None:
    content = _stringify_content(value)
    redacted_content = redact_sensitive_text(content)
    compact = " ".join(redacted_content.split())
    lowered = compact.lower()
    if any(marker in lowered for marker in _SECRET_PREVIEW_MARKERS):
        preview = "[redacted-sensitive-content]"
    else:
        preview = compact[:_PREVIEW_CHARS]
        if len(compact) > _PREVIEW_CHARS:
            preview = preview.rstrip() + "…"
    record[f"{key}_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    record[f"{key}_preview"] = preview


def append_reviewer_audit_event(event: str, kind: str, **fields: Any) -> None:
    """Append a profile-aware JSONL audit event for background reviewers.

    Writes to ``get_hermes_home()/logs/reviewer_audit.jsonl``. Full-content
    fields are replaced with a SHA-256 hash and short preview. All exceptions
    are swallowed so audit failure cannot affect the caller.
    """

    try:
        record: dict[str, Any] = {
            "ts": _utc_timestamp(),
            "event": event,
            "kind": kind,
        }
        for key, value in fields.items():
            if value is None:
                continue
            if _is_content_field(key):
                _redact_content_field(record, key, value)
            else:
                record[key] = _safe_scalar(value)

        audit_path = get_hermes_home() / _AUDIT_LOG_RELATIVE_PATH
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n"
        with _AUDIT_WRITE_LOCK:
            fd = os.open(audit_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
    except Exception:
        return

"""Helpers for visible gateway-backed sessions.

Visible sessions are human-visible child agent lanes (for example a Telegram
forum topic) that Hermes can create and prompt through trusted local gateway
control paths. This module intentionally contains only pure data-model and
routing helpers; runtime dispatch belongs in ``gateway.run`` / adapters.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from utils import atomic_json_write


_MAX_TOPIC_NAME_CHARS = 64
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
_WHITESPACE_RE = re.compile(r"\s+")
_SECRET_LIKE_RE = re.compile(
    r"(?i)(?:\bsk-(?:proj-)?[a-z0-9_-]{20,}\b|\b[a-z0-9_-]{6,}:[a-z0-9_-]{20,}\b|\bxox[abprs]-[a-z0-9-]{20,}\b)"
)
_VISIBLE_SESSION_REGISTRY_FILE = "visible_sessions.json"


class VisibleSessionAction(str, Enum):
    """Supported visible-session control operations."""

    CREATE = "create"
    PROMPT = "prompt"
    LIST = "list"
    STATUS = "status"
    CLOSE = "close"


class VisibleSessionPromptMode(str, Enum):
    """How a follow-up prompt should be delivered to a child session."""

    QUEUE = "queue"
    INTERRUPT = "interrupt"
    STEER = "steer"
    SEND_ONLY = "send_only"


@dataclass(frozen=True)
class VisibleHandleRef:
    """Parsed visible-session target reference."""

    platform: str
    chat_id: str
    thread_id: Optional[str] = None


@dataclass(frozen=True)
class VisibleSessionHandle:
    """Persistent routing metadata for a spawned visible session."""

    platform: str
    chat_id: str
    thread_id: Optional[str]
    topic_name: str
    session_key: str
    session_id: str
    target: str
    created_by_session_key: str
    created_by_user_id: Optional[str]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = _datetime_to_json(self.created_at)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisibleSessionHandle":
        payload = dict(data)
        payload["created_at"] = _datetime_from_json(payload["created_at"])
        return cls(**payload)


@dataclass
class VisibleSessionRequest:
    """Normalized request for creating or prompting a visible session."""

    action: VisibleSessionAction
    platform: str = "telegram"
    parent_chat_id: Optional[str] = None
    topic_name: Optional[str] = None
    prompt: Optional[str] = None
    handle: Optional[str] = None
    mode: VisibleSessionPromptMode = VisibleSessionPromptMode.QUEUE
    profile: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    workdir: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


def sanitize_topic_name(name: str, *, max_chars: int = _MAX_TOPIC_NAME_CHARS) -> str:
    """Return a Telegram-safe, compact topic name.

    Telegram topic names are user-visible labels, so keep them short and on one
    line. This helper deliberately rejects empty labels instead of silently
    inventing one; callers should choose a meaningful fallback from task text.
    """

    if name is None:
        raise ValueError("topic name is required")
    cleaned = _CONTROL_CHARS_RE.sub(" ", str(name))
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if not cleaned:
        raise ValueError("topic name must not be empty")
    if _SECRET_LIKE_RE.search(cleaned):
        raise ValueError("topic name appears to contain a secret; choose a non-sensitive label")
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip(" -_./:")
    if not cleaned:
        raise ValueError("topic name must not be empty")
    return cleaned


def parse_visible_handle(handle: str) -> VisibleHandleRef:
    """Parse ``platform:chat_id:thread_id`` visible-session handles."""

    if not handle or not str(handle).strip():
        raise ValueError("visible session handle is required")
    parts = [part.strip() for part in str(handle).strip().split(":")]
    if len(parts) != 3:
        raise ValueError("visible session handle format must be platform:chat_id:thread_id")
    platform, chat_id, thread_id = parts
    if not platform:
        raise ValueError("visible session handle is missing platform")
    if not chat_id:
        raise ValueError("visible session handle is missing chat id")
    if not thread_id:
        raise ValueError("visible session handle is missing thread id")
    return VisibleHandleRef(platform=platform, chat_id=chat_id, thread_id=thread_id)


def format_visible_handle(platform: str, chat_id: str, thread_id: Optional[str]) -> str:
    """Format a visible-session handle suitable for tool/slash command args."""

    if not platform:
        raise ValueError("platform is required")
    if not chat_id:
        raise ValueError("chat_id is required")
    if not thread_id:
        raise ValueError("thread_id is required")
    return f"{platform}:{chat_id}:{thread_id}"


def parse_spawn_topic_args(args: str) -> tuple[str, str]:
    """Parse ``/spawn-topic <topic name> :: <prompt>`` arguments."""

    raw = str(args or "").strip()
    topic, sep, prompt = raw.partition("::")
    if not sep:
        raise ValueError("Usage: /spawn-topic <topic name> :: <prompt>")
    topic = sanitize_topic_name(topic)
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("spawn prompt is required after ::")
    return topic, prompt


def parse_prompt_topic_args(args: str) -> tuple[str, str]:
    """Parse ``/prompt-topic <handle> :: <prompt>`` arguments."""

    raw = str(args or "").strip()
    handle, sep, prompt = raw.partition("::")
    if not sep:
        raise ValueError("Usage: /prompt-topic <telegram:chat_id:thread_id> :: <prompt>")
    handle = handle.strip()
    parse_visible_handle(handle)
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("follow-up prompt is required after ::")
    return handle, prompt


def format_visible_seed_prompt(prompt: str) -> str:
    """Return a human-visible copy of the seed prompt sent to a child lane."""

    prompt_text = str(prompt or "").strip()
    if not prompt_text:
        raise ValueError("visible session prompt is required")

    fence = "```"
    while fence in prompt_text:
        fence += "`"

    return (
        "Seed prompt from parent to this child agent:\n\n"
        f"{fence}text\n"
        f"{prompt_text}\n"
        f"{fence}"
    )


def default_visible_session_registry_path(hermes_home: str | Path | None = None) -> Path:
    """Return the default visible-session registry path for a Hermes home."""

    home = Path(hermes_home) if hermes_home is not None else Path(os.environ.get("HERMES_HOME", "~/.hermes"))
    return home.expanduser() / _VISIBLE_SESSION_REGISTRY_FILE


def load_visible_session_handles(path: Path | None = None) -> list[VisibleSessionHandle]:
    """Load persisted visible-session handles from *path*.

    Missing files are treated as an empty registry. Invalid JSON should surface
    to callers because silent recovery would hide state corruption.
    """

    registry_path = path or default_visible_session_registry_path()
    if not registry_path.exists():
        return []
    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("visible session registry must be a JSON list")
    return [VisibleSessionHandle.from_dict(item) for item in raw]


def save_visible_session_handles(path: Path | None, handles: list[VisibleSessionHandle]) -> None:
    """Persist visible-session handles without storing secrets."""

    registry_path = path or default_visible_session_registry_path()
    payload = [handle.to_dict() for handle in handles]
    atomic_json_write(registry_path, payload, indent=2, sort_keys=True)


def _datetime_to_json(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _datetime_from_json(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed

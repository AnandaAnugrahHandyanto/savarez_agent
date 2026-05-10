"""
LINE Platform Adapter for Hermes Agent.

LINE Messaging API adapter:
- runs an aiohttp webhook server
- validates X-Line-Signature with channel secret
- accepts DM, group, and room text messages
- downloads inbound LINE images and forwards them into Hermes as photo media
- downloads inbound LINE voice/audio and forwards it into Hermes transcription
- maps LINE source IDs into Hermes SessionSource objects
- prefers replyToken for immediate replies, falls back to push messages

Configuration in config.yaml::

    platforms:
      line:
        enabled: true
        extra:
          port: 8787
          host: "0.0.0.0"
          webhook_path: "/line/webhook"
          # Optional safety gates. Env vars override these.
          allowed_users: []  # LINE userIds; closed by default unless allow_all_users=true
          allowed_chats: []  # LINE userId/groupId/roomId destinations
          allow_all_users: false
          max_message_length: 5000
          media_max_mb: 10

Environment variables:
    LINE_CHANNEL_SECRET
    LINE_CHANNEL_ACCESS_TOKEN
    LINE_PORT
    LINE_HOST
    LINE_WEBHOOK_PATH
    LINE_ENABLED                true only when ready to start the LINE adapter
    LINE_ALLOWED_USERS        comma-separated LINE userIds, or *
    LINE_ALLOWED_CHATS        comma-separated LINE userId/groupId/roomId, or *
    LINE_ALLOW_ALL_USERS      true/false; registered with Hermes auth gate
    LINE_HOME_CHANNEL         approved owner DM/group to notify about access requests
    LINE_NOTIFY_UNAUTHORIZED  true/false; push access-request notices to home channel
    LINE_UNAUTHORIZED_NOTICE_TTL_SECONDS  rate-limit access-request notices per source
    LINE_MEDIA_MAX_MB         max inbound LINE media download size in MiB
    LINE_MEDIA_MAX_BYTES      exact max inbound LINE media download size; overrides MB
    LINE_REQUIRE_MENTION_IN_GROUPS true/false; ignore free group messages unless @mentioned
    LINE_MENTION_NAMES        comma-separated visible @names accepted when bot_user_id is unknown
    LINE_MENTION_PATTERNS     comma-separated regexes for custom group wake mentions
    LINE_BOT_USER_ID          optional LINE bot userId for native mention object matching

Notes:
- LINE requires a public HTTPS webhook. This adapter only binds the local HTTP
  server; expose it via a public tunnel/proxy/Funnel separately.
- Reply tokens are short-lived and single-use. User-initiated replies should prefer
  reply API and avoid silently falling back to quota-counted push delivery.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import enum
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from hermes_constants import get_hermes_home

try:
    from aiohttp import ClientSession, ClientTimeout, web

    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by check_requirements
    AIOHTTP_AVAILABLE = False
    ClientSession = None  # type: ignore[assignment]
    ClientTimeout = None  # type: ignore[assignment]
    web = None  # type: ignore[assignment]

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_audio_from_bytes,
    cache_image_from_bytes,
)
from gateway.session import SessionSource

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 8787
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_WEBHOOK_PATH = "/line/webhook"
_REPLY_TOKEN_TTL_SECONDS = 55
_DEDUPE_TTL_SECONDS = 15 * 60
_MAX_DEDUPE_EVENTS = 4096
_LINE_REPLY_API = "https://api.line.me/v2/bot/message/reply"
_LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"
_LINE_LOADING_API = "https://api.line.me/v2/bot/chat/loading/start"
_LINE_CONTENT_API_TEMPLATE = "https://api-data.line.me/v2/bot/message/{message_id}/content"
_LINE_PROFILE_API_TEMPLATE = "https://api.line.me/v2/bot/profile/{user_id}"
_LINE_GROUP_MEMBER_PROFILE_API_TEMPLATE = "https://api.line.me/v2/bot/group/{group_id}/member/{user_id}"
_LINE_ROOM_MEMBER_PROFILE_API_TEMPLATE = "https://api.line.me/v2/bot/room/{room_id}/member/{user_id}"
_DEFAULT_MEDIA_MAX_BYTES = 10 * 1024 * 1024
_DEFAULT_PENDING_APPROVALS_FILE = "line_pending_approvals.jsonl"
_DEFAULT_CARE_EVENTS_DB_FILE = "care_events.sqlite"
_DEFAULT_CARE_EVENTS_AUDIT_FILE = "care_events.jsonl"
_DEFAULT_RECENT_CONTEXT_DB_FILE = "line_recent_context.sqlite"
_LINE_RICH_MARKER = "LINE_RICH:"
_MAX_LINE_MESSAGES_PER_REQUEST = 5
LINE_MAX_MESSAGES_PER_CALL = _MAX_LINE_MESSAGES_PER_REQUEST
LINE_PER_BUBBLE_CHARS = 5000
LINE_SAFE_BUBBLE_CHARS = 4500
_MAX_LINE_TEMPLATE_ACTIONS = 2
_MAX_LINE_QUICK_REPLY_ITEMS = 13
_EXEC_APPROVAL_TTL_SECONDS = 10 * 60
_DEFAULT_SYMPTOM_NOTE_TIMEOUT_SECONDS = 30 * 60
_DEFAULT_SLOW_RESPONSE_THRESHOLD = 45.0
_DEFAULT_PENDING_REPLY_TEXT = "Still working. Tap Check answer to check; if it is not ready, wait a bit and tap again."
_DEFAULT_BUTTON_LABEL = "Check answer"
_DEFAULT_DELIVERED_TEXT = "That answer was already delivered."
_DEFAULT_INTERRUPTED_TEXT = "That run was interrupted before an answer was ready."
_DEFAULT_MENTION_NAMES: Tuple[str, ...] = ()
_PENDING_GROUP_MEDIA_TTL_SECONDS = 10 * 60
_MAX_PENDING_GROUP_MEDIA_ITEMS = 10
_DEFAULT_RECENT_CONTEXT_TTL_SECONDS = 10 * 60
_DEFAULT_RECENT_CONTEXT_LIMIT = 12
_MAX_RECENT_CONTEXT_TEXT_CHARS = 1000
_LINE_PROFILE_CACHE_TTL_SECONDS = 6 * 60 * 60
_ALLOWED_CARE_STATUSES = {"done", "not_yet", "skipped", "not_needed", "taken", "unknown", "recorded"}
_ALLOWED_CARE_METRICS = {"pain", "right_arm_zing"}
_CARE_METRIC_LABELS = {"pain": "ปวดแขนขวา", "right_arm_zing": "เสียวแปลบแขนขวา"}
_CARE_SUBJECT_LABELS = {"mum": "คุณแม่", "dad": "คุณพ่อ"}
_CARE_ROUTINE_VERBS = {
    "medication": {"done": "กินยาแล้ว", "taken": "กินยาแล้ว", "not_yet": "ยังไม่ได้กินยา"},
    "stretch": {"done": "ยืดหลังแล้ว", "not_yet": "ยังไม่ได้ยืดหลัง"},
}
_SYMPTOM_NOTE_CANCEL_PHRASES = {
    "cancel",
    "skip",
    "ยกเลิก",
    "ไม่จด",
    "ไม่ต้องจด",
    "ไม่ต้องบันทึก",
    "ไม่ต้องเพิ่ม",
}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _config_list(value: Any) -> List[str]:
    """Return config/env list values, accepting YAML lists, CSV, or JSON arrays."""
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return _csv(parsed)
            except Exception:
                pass
    return _csv(value)


def _env_or_extra(name: str, extra: Dict[str, Any], key: str, default: Any = "") -> Any:
    env = os.getenv(name)
    if env is not None:
        return env
    return extra.get(key, default)


def _redacted_id(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _default_pending_approvals_path() -> str:
    return str(Path(get_hermes_home()) / "state" / _DEFAULT_PENDING_APPROVALS_FILE)


def _default_care_events_db_path() -> str:
    return str(Path(get_hermes_home()) / "state" / _DEFAULT_CARE_EVENTS_DB_FILE)


def _default_care_events_audit_path() -> str:
    return str(Path(get_hermes_home()) / "state" / _DEFAULT_CARE_EVENTS_AUDIT_FILE)


def _default_recent_context_db_path() -> str:
    return str(Path(get_hermes_home()) / "state" / _DEFAULT_RECENT_CONTEXT_DB_FILE)


def _utcish_event_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _now_local_pair() -> Tuple[str, str]:
    now = datetime.now().astimezone()
    return now.isoformat(timespec="seconds"), now.date().isoformat()


def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """Verify a LINE webhook X-Line-Signature value."""
    if not signature or not channel_secret:
        return False
    try:
        digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature.strip())
    except Exception:
        return False


def strip_markdown_preserving_urls(text: str) -> str:
    """Strip common Markdown that LINE renders literally while preserving URLs."""
    value = str(text or "")

    def _unfence(match: re.Match[str]) -> str:
        return match.group(1).rstrip("\n")

    value = re.sub(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]*?)```", _unfence, value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r"\1 (\2)", value)
    value = re.sub(r"^#{1,6}\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*+]\s+", "• ", value, flags=re.MULTILINE)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"__([^_]+)__", r"\1", value)
    value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", value)
    value = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", value)
    return value.strip()


def split_for_line(text: str, max_chars: int = LINE_SAFE_BUBBLE_CHARS) -> List[str]:
    """Split text into at most five LINE-safe text bubbles."""
    value = str(text or "").strip()
    if not value:
        return []
    limit = max(1, min(int(max_chars or LINE_SAFE_BUBBLE_CHARS), LINE_PER_BUBBLE_CHARS))
    chunks: List[str] = []
    remaining = value
    while remaining and len(chunks) < LINE_MAX_MESSAGES_PER_CALL:
        if len(remaining) <= limit:
            chunks.append(remaining)
            remaining = ""
            break
        cut = remaining.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining and chunks:
        suffix = "…"
        chunks[-1] = chunks[-1][: max(1, limit - len(suffix))].rstrip() + suffix
    return [chunk for chunk in chunks if chunk]


def _resolve_chat(source: Dict[str, Any]) -> Tuple[str, str]:
    source_type = str((source or {}).get("type") or "")
    if source_type == "group":
        return str(source.get("groupId") or ""), "group"
    if source_type == "room":
        return str(source.get("roomId") or ""), "room"
    return str(source.get("userId") or ""), "dm"


def _allowed_for_source(
    source: Dict[str, Any],
    *,
    allow_all: bool,
    user_ids: Set[str],
    group_ids: Set[str],
    room_ids: Set[str],
) -> bool:
    if allow_all:
        return True
    source_type = str((source or {}).get("type") or "")
    if source_type == "group":
        return "*" in group_ids or str(source.get("groupId") or "") in group_ids
    if source_type == "room":
        return "*" in room_ids or str(source.get("roomId") or "") in room_ids
    if source_type == "user":
        return "*" in user_ids or str(source.get("userId") or "") in user_ids
    return False


class State(enum.Enum):
    PENDING = "pending"
    READY = "ready"
    DELIVERED = "delivered"
    ERROR = "error"


@dataclass
class _CacheEntry:
    state: State
    chat_id: str
    created_at: float
    payload: Any = None


class RequestCache:
    """In-memory state machine for native LINE slow-response postback retrieval."""

    def __init__(self, ttl_seconds: float = 15 * 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: Dict[str, _CacheEntry] = {}

    def register_pending(self, chat_id: str) -> str:
        request_id = str(uuid.uuid4())
        self._entries[request_id] = _CacheEntry(State.PENDING, str(chat_id), time.time())
        return request_id

    def get(self, request_id: str) -> Optional[_CacheEntry]:
        return self._entries.get(request_id)

    def set_ready(self, request_id: str, payload: Any) -> None:
        entry = self._entries.get(request_id)
        if entry and entry.state is not State.DELIVERED:
            entry.state = State.READY
            entry.payload = payload

    def set_error(self, request_id: str, message: str) -> None:
        entry = self._entries.get(request_id)
        if entry and entry.state is not State.DELIVERED:
            entry.state = State.ERROR
            entry.payload = message

    def mark_delivered(self, request_id: str) -> None:
        entry = self._entries.get(request_id)
        if entry:
            entry.state = State.DELIVERED

    def find_pending_for_chat(self, chat_id: str) -> Optional[str]:
        for request_id, entry in self._entries.items():
            if entry.chat_id == chat_id and entry.state is State.PENDING:
                return request_id
        return None

    def prune(self) -> int:
        now = time.time()
        removed = 0
        for request_id, entry in list(self._entries.items()):
            if now - entry.created_at > self.ttl_seconds:
                self._entries.pop(request_id, None)
                removed += 1
        return removed


class _MessageDeduplicator:
    """Bounded LRU of LINE webhook event IDs to ignore retries."""

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max(1, int(max_size or 1000))
        self._seen: Dict[str, float] = {}

    def is_duplicate(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._seen:
            self._seen[event_id] = time.time()
            return True
        self._seen[event_id] = time.time()
        while len(self._seen) > self.max_size:
            oldest = min(self._seen, key=self._seen.get)  # type: ignore[arg-type]
            self._seen.pop(oldest, None)
        return False


_SYSTEM_BYPASS_PREFIXES: Tuple[str, ...] = (
    "⚡ Interrupting",
    "⏳ Queued",
    "⏩ Steered",
    "💾",
)


def _is_system_bypass(content: str) -> bool:
    return bool(content) and any(str(content).startswith(prefix) for prefix in _SYSTEM_BYPASS_PREFIXES)


def build_postback_button_message(text: str, button_label: str, request_id: str) -> Dict[str, Any]:
    truncated = str(text or "")[:160]
    alt_text = str(text or "")[:400]
    label = (str(button_label or "")[:20] or "Check answer")
    return {
        "type": "template",
        "altText": alt_text,
        "template": {
            "type": "buttons",
            "text": truncated,
            "actions": [
                {
                    "type": "postback",
                    "label": label,
                    "data": json.dumps({"action": "show_response", "request_id": request_id}),
                    "displayText": label,
                }
            ],
        },
    }


class LineRecentContextStore:
    """Profile-local, TTL-limited sidecar for approved LINE group context.

    This is intentionally separate from Hermes session history and long-term
    memory.  It keeps raw group text briefly so later authorized turns can
    understand "the message above," while query keys use hashes so raw LINE
    user/group IDs are not stored in the context database.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None, *, ttl_seconds: int, limit: int) -> None:
        self.db_path = str(db_path or _default_recent_context_db_path())
        self.ttl_seconds = max(1, int(ttl_seconds or _DEFAULT_RECENT_CONTEXT_TTL_SECONDS))
        self.limit = max(1, int(limit or _DEFAULT_RECENT_CONTEXT_LIMIT))
        self._initialized = False

    def record(
        self,
        *,
        chat_id: str,
        user_id: str,
        sender_name: str,
        message_id: str,
        webhook_event_id: str,
        message_type: str,
        text: str = "",
        occurred_at: Optional[float] = None,
    ) -> None:
        if not chat_id or not message_type:
            return
        now = time.time() if occurred_at is None else float(occurred_at)
        event_key_source = str(message_id or webhook_event_id or f"{chat_id}:{user_id}:{now}")
        event_key = _redacted_id(event_key_source)
        clean_text = " ".join(str(text or "").split())[:_MAX_RECENT_CONTEXT_TEXT_CHARS]
        row = {
            "event_key": event_key,
            "chat_hash": _redacted_id(str(chat_id)),
            "actor_hash": _redacted_id(str(user_id or "")),
            "sender_name": str(sender_name or "LINE user")[:120],
            "message_id": str(message_id or "")[:200],
            "webhook_event_id_hash": _redacted_id(str(webhook_event_id or "")),
            "message_type": str(message_type or "")[:40],
            "text": clean_text,
            "occurred_at": now,
            "schema_version": self.SCHEMA_VERSION,
        }
        with self._connect() as conn:
            self._prune(conn, now=now)
            conn.execute(
                """
                INSERT OR REPLACE INTO line_recent_context (
                    event_key, chat_hash, actor_hash, sender_name, message_id,
                    webhook_event_id_hash, message_type, text, occurred_at,
                    schema_version
                ) VALUES (
                    :event_key, :chat_hash, :actor_hash, :sender_name, :message_id,
                    :webhook_event_id_hash, :message_type, :text, :occurred_at,
                    :schema_version
                )
                """,
                row,
            )
            conn.commit()

    def recent_for_group(self, chat_id: str, *, limit: Optional[int] = None, now: Optional[float] = None) -> List[Dict[str, Any]]:
        if not chat_id:
            return []
        return self.recent_for_groups([chat_id], limit=limit, now=now)

    def recent_for_groups(
        self,
        chat_ids: Iterable[str],
        *,
        limit: Optional[int] = None,
        now: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        chat_hashes = [_redacted_id(str(chat_id)) for chat_id in chat_ids if str(chat_id or "").strip()]
        if not chat_hashes:
            return []
        current = time.time() if now is None else float(now)
        max_items = max(1, int(limit or self.limit))
        placeholders = ",".join("?" for _ in chat_hashes)
        with self._connect() as conn:
            self._prune(conn, now=current)
            rows = conn.execute(
                f"""
                SELECT * FROM line_recent_context
                WHERE chat_hash IN ({placeholders}) AND occurred_at >= ?
                ORDER BY occurred_at DESC, event_key DESC
                LIMIT ?
                """,
                [*chat_hashes, current - self.ttl_seconds, max_items],
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        if not self._initialized:
            self._init_schema(conn)
            self._initialized = True
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS line_recent_context (
                event_key TEXT PRIMARY KEY,
                chat_hash TEXT NOT NULL,
                actor_hash TEXT,
                sender_name TEXT,
                message_id TEXT,
                webhook_event_id_hash TEXT,
                message_type TEXT NOT NULL,
                text TEXT,
                occurred_at REAL NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_line_recent_context_chat_time
                ON line_recent_context(chat_hash, occurred_at);
            """
        )
        conn.commit()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _prune(self, conn: sqlite3.Connection, *, now: Optional[float] = None) -> None:
        current = time.time() if now is None else float(now)
        conn.execute("DELETE FROM line_recent_context WHERE occurred_at < ?", (current - self.ttl_seconds,))


class LineCareEventStore:
    """Profile-local reminder/event store for LINE care postbacks.

    Raw LINE identifiers are never stored in queryable columns; only short hashes
    are kept for attribution and dedupe. SQLite is the source of truth and JSONL
    is an append-only audit trail.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None, audit_path: Optional[str] = None) -> None:
        self.db_path = str(db_path or _default_care_events_db_path())
        self.audit_path = str(audit_path or _default_care_events_audit_path())
        self._initialized = False

    def create_reminder(
        self,
        *,
        subject: str,
        routine_id: str,
        routine_type: str,
        slot: str = "",
        scheduled_for: str = "",
        local_date: str = "",
        chat_type: str = "",
        recipient_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        subject = _normalise_required_token(subject, "subject")
        routine_id = _normalise_required_token(routine_id, "routine_id")
        routine_type = _normalise_required_token(routine_type, "routine_type")
        created_at, today = _now_local_pair()
        reminder_id = f"r_{uuid.uuid4().hex[:20]}"
        safe_metadata = dict(metadata or {})
        safe_metadata.pop("raw", None)
        safe_metadata.pop("token", None)
        row = {
            "reminder_id": reminder_id,
            "created_at": created_at,
            "scheduled_for": str(scheduled_for or ""),
            "local_date": str(local_date or today),
            "subject": subject,
            "routine_id": routine_id,
            "routine_type": routine_type,
            "slot": str(slot or ""),
            "chat_type": str(chat_type or ""),
            "recipient_hash": _redacted_id(str(recipient_id or "")),
            "line_message_id_hash": "",
            "status": "created",
            "metadata_json": json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True),
            "schema_version": self.SCHEMA_VERSION,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reminder_instances (
                    reminder_id, created_at, scheduled_for, local_date, subject,
                    routine_id, routine_type, slot, chat_type, recipient_hash,
                    line_message_id_hash, status, metadata_json, schema_version
                ) VALUES (
                    :reminder_id, :created_at, :scheduled_for, :local_date, :subject,
                    :routine_id, :routine_type, :slot, :chat_type, :recipient_hash,
                    :line_message_id_hash, :status, :metadata_json, :schema_version
                )
                """,
                row,
            )
        return reminder_id

    def mark_reminder_sent(self, reminder_id: str, *, line_message_id: str = "") -> bool:
        reminder = self.get_reminder(reminder_id)
        if reminder is None:
            return False
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reminder_instances
                SET status = 'sent', line_message_id_hash = ?
                WHERE reminder_id = ?
                """,
                (_redacted_id(line_message_id), reminder_id),
            )
        event = self._event_from_reminder(
            reminder,
            event_type="reminder_sent",
            status="sent",
            source="line_send",
            raw_json={"line_message_id_hash": _redacted_id(line_message_id)},
        )
        return self._insert_event(event)

    def mark_reminder_delivery_failed(self, reminder_id: str, *, error: str = "") -> bool:
        reminder = self.get_reminder(reminder_id)
        if reminder is None:
            return False
        with self._connect() as conn:
            conn.execute("UPDATE reminder_instances SET status = 'delivery_failed' WHERE reminder_id = ?", (reminder_id,))
        event = self._event_from_reminder(
            reminder,
            event_type="delivery_failed",
            status="delivery_failed",
            source="line_send",
            raw_json={"error": str(error or "")[:300]},
        )
        return self._insert_event(event)

    def record_response(
        self,
        *,
        reminder_id: str,
        status: str,
        metric: str = "",
        value: Optional[int] = None,
        actor_id: str = "",
        chat_id: str = "",
        line_webhook_event_id: str = "",
        note: str = "",
        raw_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reminder = self.get_reminder(reminder_id)
        if reminder is None:
            return {"ok": False, "reason": "unknown_reminder", "duplicate": False}
        status = _normalise_care_status(status)
        metric = _normalise_care_metric(metric) if metric else ""
        metric_value = _normalise_care_value(value) if value is not None else None
        event = self._event_from_reminder(
            reminder,
            event_type="response",
            status=status,
            source="line_postback",
            metric=metric,
            value=metric_value,
            actor_hash=_redacted_id(actor_id),
            chat_hash=_redacted_id(chat_id),
            line_webhook_event_id_hash=_redacted_id(line_webhook_event_id),
            note=note,
            raw_json=raw_json or {},
        )
        inserted = self._insert_event(event, ignore_duplicate=True)
        return {
            "ok": inserted,
            "reason": "recorded" if inserted else "duplicate",
            "duplicate": not inserted,
            "reminder": reminder,
            "event": event if inserted else None,
        }

    def record_manual_note(
        self,
        *,
        subject: str,
        routine_id: str,
        reminder_id: str = "",
        event_type: str = "manual_note",
        status: str = "recorded",
        actor_id: str = "",
        chat_id: str = "",
        line_webhook_event_id: str = "",
        note: str = "",
        raw_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        subject = _normalise_required_token(subject, "subject")
        routine_id = _normalise_required_token(routine_id, "routine_id")
        if event_type not in {"manual_note", "correction"}:
            raise ValueError(f"unsupported care note event type: {event_type or 'missing'}")
        status = _normalise_care_status(status) if status else ""
        reminder = self.get_reminder(reminder_id) if reminder_id else None
        occurred_at, today = _now_local_pair()
        event = {
            "event_id": _utcish_event_id("ev"),
            "reminder_id": str(reminder_id or ""),
            "occurred_at": occurred_at,
            "local_date": (reminder or {}).get("local_date") or today,
            "subject": subject,
            "routine_id": routine_id,
            "event_type": event_type,
            "status": status,
            "metric": "",
            "value": None,
            "source": "line_message",
            "actor_hash": _redacted_id(actor_id),
            "chat_hash": _redacted_id(chat_id),
            "line_webhook_event_id_hash": _redacted_id(line_webhook_event_id) or None,
            "note": str(note or "")[:1000],
            "raw_json": json.dumps(raw_json or {}, ensure_ascii=False, sort_keys=True),
            "schema_version": self.SCHEMA_VERSION,
        }
        inserted = self._insert_event(event, ignore_duplicate=True)
        return {
            "ok": inserted,
            "reason": "recorded" if inserted else "duplicate",
            "duplicate": not inserted,
            "event": event if inserted else None,
        }

    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reminder_instances WHERE reminder_id = ?",
                (str(reminder_id or ""),),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_reminders(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM reminder_instances ORDER BY created_at, reminder_id").fetchall()
        return [dict(row) for row in rows]

    def list_events(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM care_events ORDER BY occurred_at, event_id").fetchall()
        return [dict(row) for row in rows]

    def _event_from_reminder(
        self,
        reminder: Dict[str, Any],
        *,
        event_type: str,
        status: str = "",
        source: str,
        metric: str = "",
        value: Optional[int] = None,
        actor_hash: str = "",
        chat_hash: str = "",
        line_webhook_event_id_hash: str = "",
        note: str = "",
        raw_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        occurred_at, today = _now_local_pair()
        return {
            "event_id": _utcish_event_id("ev"),
            "reminder_id": reminder.get("reminder_id") or "",
            "occurred_at": occurred_at,
            "local_date": reminder.get("local_date") or today,
            "subject": reminder.get("subject") or "",
            "routine_id": reminder.get("routine_id") or "",
            "event_type": event_type,
            "status": status,
            "metric": metric,
            "value": value,
            "source": source,
            "actor_hash": actor_hash,
            "chat_hash": chat_hash,
            "line_webhook_event_id_hash": line_webhook_event_id_hash or None,
            "note": str(note or "")[:1000],
            "raw_json": json.dumps(raw_json or {}, ensure_ascii=False, sort_keys=True),
            "schema_version": self.SCHEMA_VERSION,
        }

    def _insert_event(self, event: Dict[str, Any], *, ignore_duplicate: bool = False) -> bool:
        statement = "INSERT OR IGNORE" if ignore_duplicate else "INSERT"
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                {statement} INTO care_events (
                    event_id, reminder_id, occurred_at, local_date, subject, routine_id,
                    event_type, status, metric, value, source, actor_hash, chat_hash,
                    line_webhook_event_id_hash, note, raw_json, schema_version
                ) VALUES (
                    :event_id, :reminder_id, :occurred_at, :local_date, :subject, :routine_id,
                    :event_type, :status, :metric, :value, :source, :actor_hash, :chat_hash,
                    :line_webhook_event_id_hash, :note, :raw_json, :schema_version
                )
                """,
                event,
            )
            inserted = cursor.rowcount > 0
        if inserted:
            self._append_audit({"type": "care_event", **event})
        return inserted

    def _connect(self) -> sqlite3.Connection:
        self._ensure_parent_modes()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if not self._initialized:
            self._init_schema(conn)
            self._initialized = True
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reminder_instances (
                reminder_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                scheduled_for TEXT,
                local_date TEXT NOT NULL,
                subject TEXT NOT NULL,
                routine_id TEXT NOT NULL,
                routine_type TEXT NOT NULL,
                slot TEXT,
                chat_type TEXT,
                recipient_hash TEXT,
                line_message_id_hash TEXT,
                status TEXT,
                metadata_json TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS care_events (
                event_id TEXT PRIMARY KEY,
                reminder_id TEXT,
                occurred_at TEXT NOT NULL,
                local_date TEXT NOT NULL,
                subject TEXT NOT NULL,
                routine_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT,
                metric TEXT,
                value INTEGER,
                source TEXT NOT NULL,
                actor_hash TEXT,
                chat_hash TEXT,
                line_webhook_event_id_hash TEXT UNIQUE,
                note TEXT,
                raw_json TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_care_events_reminder ON care_events(reminder_id);
            CREATE INDEX IF NOT EXISTS idx_care_events_subject_routine ON care_events(subject, routine_id, local_date);
            """
        )
        self._migrate_schema(conn)
        conn.commit()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass


    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("PRAGMA table_info(care_events)").fetchall()
        columns = {row[1] for row in rows}
        if "metric" not in columns:
            conn.execute("ALTER TABLE care_events ADD COLUMN metric TEXT")
        if "value" not in columns:
            conn.execute("ALTER TABLE care_events ADD COLUMN value INTEGER")

    def _ensure_parent_modes(self) -> None:
        db_parent = Path(self.db_path).expanduser().parent
        audit_parent = Path(self.audit_path).expanduser().parent
        db_parent.mkdir(parents=True, exist_ok=True)
        audit_parent.mkdir(parents=True, exist_ok=True)

    def _append_audit(self, record: Dict[str, Any]) -> None:
        path = Path(self.audit_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _normalise_required_token(value: Any, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError(f"care payload requires {field_name}")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise ValueError(f"care payload {field_name} contains unsupported characters")
    return text


def _normalise_care_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status not in _ALLOWED_CARE_STATUSES:
        raise ValueError(f"unsupported care status: {status or 'missing'}")
    return status


def _normalise_care_metric(value: Any) -> str:
    metric = str(value or "").strip().lower()
    if metric not in _ALLOWED_CARE_METRICS:
        raise ValueError(f"unsupported care metric: {metric or 'missing'}")
    return metric


def _normalise_care_value(value: Any) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("care metric value must be an integer 0-10")
    if number < 0 or number > 10:
        raise ValueError("care metric value must be between 0 and 10")
    return number


def _line_bearer_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _line_auth_headers(token: str) -> Dict[str, str]:
    return {**_line_bearer_headers(token), "Content-Type": "application/json"}


def _line_text_message(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": text}


def _truncate_line_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _line_message_action(action: Dict[str, Any]) -> Dict[str, str]:
    label = _truncate_line_text(action.get("label"), 20)
    text = _truncate_line_text(action.get("text"), 300)
    if not label or not text:
        raise ValueError("LINE rich message actions require label and text")
    return {"type": "message", "label": label, "text": text}


def _line_postback_action(action: Dict[str, Any]) -> Dict[str, str]:
    label = _truncate_line_text(action.get("label"), 20)
    data = _truncate_line_text(action.get("data"), 300)
    if not label or not data:
        raise ValueError("LINE postback actions require label and data")
    payload = {"type": "postback", "label": label, "data": data}
    display_text = _truncate_line_text(action.get("displayText") or action.get("display_text"), 300)
    if display_text:
        payload["displayText"] = display_text
    return payload


def _line_action(action: Dict[str, Any]) -> Dict[str, str]:
    action_type = str(action.get("type") or "").strip().lower()
    if action_type == "postback" or action.get("data"):
        return _line_postback_action(action)
    return _line_message_action(action)


def _line_quick_reply(actions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for action in list(actions)[:_MAX_LINE_QUICK_REPLY_ITEMS]:
        items.append({"type": "action", "action": _line_action(action)})
    if not items:
        raise ValueError("LINE quick reply requires at least one action")
    return {"items": items}


def _line_confirm_template_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    actions = [_line_action(action) for action in payload.get("actions") or []]
    if len(actions) != _MAX_LINE_TEMPLATE_ACTIONS:
        raise ValueError("LINE confirm template requires exactly two actions")
    text = _truncate_line_text(payload.get("text"), 240)
    alt_text = _truncate_line_text(payload.get("altText") or payload.get("alt_text") or text, 400)
    if not text or not alt_text:
        raise ValueError("LINE confirm template requires text and altText")
    return {
        "type": "template",
        "altText": alt_text,
        "template": {
            "type": "confirm",
            "text": text,
            "actions": actions,
        },
    }


def _line_text_with_quick_reply_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = _truncate_line_text(payload.get("text"), 5000)
    if not text:
        raise ValueError("LINE text rich payload requires text")
    message: Dict[str, Any] = _line_text_message(text)
    actions = payload.get("actions") or payload.get("quickReply") or payload.get("quick_reply")
    if actions:
        message["quickReply"] = _line_quick_reply(actions)
    return message


def _care_slot_label(slot: Any) -> str:
    value = str(slot or "").strip().lower()
    return {
        "morning": "ตอนเช้า",
        "night": "ก่อนนอน",
        "evening": "ตอนเย็น",
        "bedtime": "ก่อนนอน",
        "afternoon": "ตอนบ่าย",
    }.get(value, value)


def _care_flex_theme(care: Dict[str, Any]) -> Dict[str, str]:
    subject = str(care.get("subject") or "").strip().lower()
    routine_type = str(care.get("routine_type") or care.get("routineType") or "").strip().lower()
    subject_label = _CARE_SUBJECT_LABELS.get(subject, "")
    if routine_type == "stretch":
        return {
            "title": f"ยืดหลัง {subject_label}".strip(),
            "eyebrow": "กายภาพเบา ๆ",
            "accent": "#2563EB",
            "soft_bg": "#EFF6FF",
            "chip_bg": "#DBEAFE",
        }
    if routine_type == "medication":
        return {
            "title": f"เช็กยา {subject_label}".strip(),
            "eyebrow": "รายการวันนี้",
            "accent": "#EA580C",
            "soft_bg": "#FFF7ED",
            "chip_bg": "#FFEDD5",
        }
    title = f"เช็ก{subject_label}" if subject_label else "เช็กวันนี้"
    return {
        "title": title,
        "eyebrow": "ดูแลวันนี้",
        "accent": "#059669",
        "soft_bg": "#ECFDF5",
        "chip_bg": "#D1FAE5",
    }


def _line_care_body_contents(payload: Dict[str, Any], theme: Dict[str, str], fallback_text: str) -> List[Dict[str, Any]]:
    """Build compact, styled care-card body sections.

    LINE Flex does not understand Markdown, so emphasis must be expressed with
    text component weights, colors, and small semantic blocks.
    """
    contents: List[Dict[str, Any]] = []

    subtitle = _truncate_line_text(payload.get("subtitle"), 90)
    if subtitle:
        contents.append(
            {
                "type": "text",
                "text": subtitle,
                "wrap": True,
                "size": "sm",
                "weight": "bold",
                "color": "#111827",
            }
        )

    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    for section in sections[:4]:
        if not isinstance(section, dict):
            continue
        label = _truncate_line_text(section.get("label"), 60)
        items = section.get("items") if isinstance(section.get("items"), list) else []
        if not label and not items:
            continue
        section_contents: List[Dict[str, Any]] = []
        if label:
            section_contents.append(
                {
                    "type": "text",
                    "text": label,
                    "size": "xs",
                    "weight": "bold",
                    "color": theme["accent"],
                    "wrap": True,
                }
            )
        for item in items[:4]:
            detail = ""
            if isinstance(item, dict):
                item_text = _truncate_line_text(item.get("name") or item.get("text") or item.get("label"), 90)
                detail = _truncate_line_text(item.get("detail") or item.get("note") or item.get("description"), 120)
            else:
                item_text = _truncate_line_text(item, 90)
            if not item_text:
                continue
            section_contents.append(
                {
                    "type": "text",
                    "text": f"• {item_text}",
                    "size": "sm",
                    "weight": "bold",
                    "color": "#111827",
                    "wrap": True,
                    "margin": "xs",
                }
            )
            if detail:
                section_contents.append(
                    {
                        "type": "text",
                        "text": f"  {detail}",
                        "size": "xs",
                        "color": "#6B7280",
                        "wrap": True,
                        "margin": "none",
                    }
                )
        contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": theme["soft_bg"],
                "cornerRadius": "md",
                "paddingAll": "8px",
                "margin": "sm" if contents else "none",
                "contents": section_contents,
            }
        )

    facts = payload.get("facts") if isinstance(payload.get("facts"), list) else []
    for fact in facts[:4]:
        if isinstance(fact, dict):
            label = _truncate_line_text(fact.get("label"), 36)
            value = _truncate_line_text(fact.get("value"), 80)
        else:
            label = ""
            value = _truncate_line_text(fact, 100)
        if not value:
            continue
        row_contents: List[Dict[str, Any]] = []
        if label:
            row_contents.append(
                {
                    "type": "text",
                    "text": label,
                    "size": "xs",
                    "weight": "bold",
                    "color": theme["accent"],
                    "flex": 3,
                    "wrap": True,
                }
            )
        row_contents.append(
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "weight": "bold" if isinstance(fact, dict) and fact.get("strong", True) else "regular",
                "color": "#111827",
                "flex": 7,
                "wrap": True,
            }
        )
        contents.append(
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "margin": "sm" if contents else "none",
                "contents": row_contents,
            }
        )

    note = _truncate_line_text(payload.get("note"), 100)
    if note:
        contents.append(
            {
                "type": "text",
                "text": note,
                "wrap": True,
                "size": "xs",
                "style": "italic",
                "color": "#6B7280",
                "margin": "md" if contents else "none",
            }
        )

    if contents:
        return contents

    return [
        {
            "type": "text",
            "text": fallback_text,
            "wrap": True,
            "size": "sm",
            "color": "#374151",
        }
    ]


def _symptom_scale_config(metric: str) -> Dict[str, Any]:
    metric = _normalise_care_metric(metric)
    if metric == "pain":
        return {
            "default_title": "🩷 เช็กระดับความปวดแขนขวาคุณแม่",
            "default_alt": "เช็กระดับความปวดแขนขวาคุณแม่ 0–10",
            "display_prefix": "คุณแม่ปวดแขนขวา",
            "bands": [
                ("⚪ ไม่ปวด", "ไม่มีอาการปวดตอนนี้", [0], "#F0FDF4", "#BBF7D0", "#166534", "#16A34A"),
                ("🟢 ปวดเล็กน้อย", "ยังพอทำกิจวัตรได้", [1, 2, 3], "#F7FEE7", "#D9F99D", "#3F6212", "#84CC16"),
                ("🟡 ปวดปานกลาง", "เริ่มรบกวนการขยับหรือพักผ่อน", [4, 5, 6], "#FFFBEB", "#FDE68A", "#92400E", "#F59E0B"),
                ("🔴 ปวดมาก", "ทำอะไรลำบาก ต้องระวังเป็นพิเศษ", [7, 8, 9], "#FEF2F2", "#FECACA", "#991B1B", "#EF4444"),
                ("🚨 ปวดที่สุด", "ทนไม่ไหว หรือรู้สึกรุนแรงมาก", [10], "#FFF1F2", "#FDA4AF", "#7F1D1D", "#991B1B"),
            ],
        }
    return {
        "default_title": "⚡ เช็กอาการเสียวแปลบที่แขนขวาคุณแม่",
        "default_alt": "เช็กอาการเสียวแปลบแขนขวาคุณแม่ 0–10",
        "display_prefix": "คุณแม่เสียวแปลบแขนขวา",
        "bands": [
            ("⚪ ไม่มีอาการ", "ไม่มีเสียวหรือแปลบตอนนี้", [0], "#F8FAFC", "#E2E8F0", "#334155", "#64748B"),
            ("🟢 เสียวเล็กน้อย", "เป็นบางครั้ง ยังไม่ค่อยรบกวน", [1, 2, 3], "#F0FDF4", "#BBF7D0", "#166534", "#16A34A"),
            ("🟡 เสียวปานกลาง", "รู้สึกชัด เริ่มรบกวนการใช้แขน", [4, 5, 6], "#FFFBEB", "#FDE68A", "#92400E", "#F59E0B"),
            ("🔴 เสียวมาก", "เสียวแปลบมาก ใช้แขนลำบาก", [7, 8, 9], "#FEF2F2", "#FECACA", "#991B1B", "#EF4444"),
            ("🚨 รุนแรงมาก", "ทนไม่ไหว หรือรู้สึกผิดปกติมาก", [10], "#FFF1F2", "#FDA4AF", "#7F1D1D", "#991B1B"),
        ],
    }


def _line_symptom_scale_flex_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    care = payload.get("_care") if isinstance(payload.get("_care"), dict) else {}
    metric = _normalise_care_metric(care.get("metric") or payload.get("metric"))
    reminder_id = str(care.get("reminder_id") or "")
    if not reminder_id:
        raise ValueError("LINE symptom scale card requires reminder id")
    config = _symptom_scale_config(metric)
    title = _truncate_line_text(payload.get("title") or config["default_title"], 80)
    subtitle = _truncate_line_text(payload.get("subtitle") or "แตะตัวเลขที่ใกล้เคียงที่สุดนะคะ", 90)
    alt_text = _truncate_line_text(payload.get("altText") or payload.get("alt_text") or config["default_alt"], 400)

    body_contents: List[Dict[str, Any]] = []
    for title_text, desc, nums, bg, border, text_color, button_color in config["bands"]:
        number_boxes: List[Dict[str, Any]] = []
        for number in nums:
            action = _line_action(
                {
                    "type": "postback",
                    "label": str(number),
                    "data": f"care:v1;rid={reminder_id};metric={metric};value={number}",
                    "displayText": f"{config['display_prefix']} {number}/10",
                }
            )
            number_boxes.append(
                {
                    "type": "box",
                    "layout": "vertical",
                    "height": "36px",
                    "cornerRadius": "11px",
                    "backgroundColor": button_color,
                    "justifyContent": "center",
                    "alignItems": "center",
                    "action": action,
                    "contents": [
                        {
                            "type": "text",
                            "text": str(number),
                            "size": "sm",
                            "weight": "bold",
                            "color": "#FFFFFF",
                            "align": "center",
                        }
                    ],
                }
            )
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "cornerRadius": "16px",
                "backgroundColor": bg,
                "borderWidth": "1px",
                "borderColor": border,
                "spacing": "xs",
                "contents": [
                    {"type": "text", "text": title_text, "size": "sm", "weight": "bold", "color": text_color, "wrap": True},
                    {"type": "text", "text": desc, "size": "xs", "color": "#4B5563", "wrap": True, "margin": "xs"},
                    {"type": "box", "layout": "horizontal", "spacing": "sm", "margin": "sm", "contents": number_boxes},
                ],
            }
        )

    note = _truncate_line_text(
        payload.get("note")
        or "📝 มีอะไรอยากให้จดเพิ่มไหมคะ? พิมพ์บอกต่อได้เลยค่ะ",
        160,
    )
    if note:
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "cornerRadius": "16px",
                "backgroundColor": "#FFF7ED",
                "borderWidth": "1px",
                "borderColor": "#FED7AA",
                "margin": "sm",
                "contents": [
                    {"type": "text", "text": note, "size": "xs", "color": "#7C2D12", "wrap": True}
                ],
            }
        )

    return {
        "type": "flex",
        "altText": alt_text,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "17px",
                "backgroundColor": "#FFF1F2" if metric == "pain" else "#F5F3FF",
                "contents": [
                    {"type": "text", "text": title, "weight": "bold", "size": "lg", "color": "#9F1239" if metric == "pain" else "#6D28D9", "wrap": True},
                    {"type": "text", "text": subtitle, "size": "sm", "color": "#6B7280", "margin": "xs", "wrap": True},
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "spacing": "sm",
                "backgroundColor": "#FFFFFF",
                "contents": body_contents,
            },
        },
    }


def _line_care_flex_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Render care reminders as clean Flex bubbles with postback actions."""
    actions = [_line_action(action) for action in payload.get("actions") or []]
    if len(actions) != _MAX_LINE_TEMPLATE_ACTIONS:
        raise ValueError("LINE care flex card requires exactly two actions")
    text = _truncate_line_text(payload.get("text"), 240)
    alt_text = _truncate_line_text(payload.get("altText") or payload.get("alt_text") or text, 400)
    if not text or not alt_text:
        raise ValueError("LINE care flex card requires text and altText")

    care = payload.get("_care") if isinstance(payload.get("_care"), dict) else {}
    theme = _care_flex_theme(care)
    title = _truncate_line_text(payload.get("title") or theme["title"], 80)
    eyebrow_source = payload.get("eyebrow") if "eyebrow" in payload else theme["eyebrow"]
    eyebrow = _truncate_line_text(eyebrow_source, 50)

    buttons = []
    for index, action in enumerate(actions):
        button: Dict[str, Any] = {
            "type": "button",
            "style": "primary" if index == 0 else "secondary",
            "height": "sm",
            "flex": 1,
            "action": action,
        }
        if index == 0:
            button["color"] = theme["accent"]
        buttons.append(button)

    header_contents: List[Dict[str, Any]] = []
    if eyebrow:
        header_contents.append(
            {
                "type": "text",
                "text": eyebrow,
                "size": "xxs",
                "weight": "bold",
                "color": theme["accent"],
                "wrap": True,
            }
        )
    header_contents.append(
        {
            "type": "text",
            "text": title,
            "size": "md",
            "weight": "bold",
            "color": "#111827",
            "wrap": True,
            "margin": "xs" if eyebrow else "none",
        }
    )

    return {
        "type": "flex",
        "altText": alt_text,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "10px",
                "backgroundColor": theme["soft_bg"],
                "spacing": "xs",
                "contents": header_contents,
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "10px",
                "paddingBottom": "6px",
                "spacing": "xs",
                "contents": _line_care_body_contents(payload, theme, text),
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "paddingAll": "10px",
                "paddingTop": "0px",
                "spacing": "sm",
                "contents": buttons,
                "flex": 0,
            },
        },
    }


def _validate_raw_line_message(message: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(message, dict):
        raise ValueError("LINE rich messages must be objects")
    message_type = str(message.get("type") or "").strip().lower()
    if message_type not in {"text", "template", "flex"}:
        raise ValueError(f"unsupported LINE rich message type: {message_type or 'missing'}")
    return message


def _line_messages_from_rich_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        messages = [_validate_raw_line_message(message) for message in payload]
    elif isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        messages = [_validate_raw_line_message(message) for message in payload["messages"]]
    elif isinstance(payload, dict):
        payload_type = str(payload.get("type") or "").strip().lower()
        if payload_type == "confirm":
            messages = [_line_confirm_template_message(payload)]
        elif payload_type == "text":
            messages = [_line_text_with_quick_reply_message(payload)]
        elif payload_type == "flex":
            alt_text = _truncate_line_text(payload.get("altText") or payload.get("alt_text"), 400)
            contents = payload.get("contents")
            if not alt_text or not isinstance(contents, dict):
                raise ValueError("LINE flex payload requires altText and contents")
            messages = [{"type": "flex", "altText": alt_text, "contents": contents}]
        else:
            raise ValueError(f"unsupported LINE rich payload type: {payload_type or 'missing'}")
    else:
        raise ValueError("LINE rich payload must be an object or list")

    if not messages:
        raise ValueError("LINE rich payload produced no messages")
    if len(messages) > _MAX_LINE_MESSAGES_PER_REQUEST:
        raise ValueError("LINE rich payload exceeds LINE's 5-message request limit")
    return messages


def _looks_like_line_rich_payload(payload: Any) -> bool:
    """Return True when bare JSON is intentionally a LINE rich payload.

    Marker-prefixed payloads are always interpreted as rich.  Bare JSON is
    accepted only when it has a LINE-rich shape, so ordinary JSON text remains
    ordinary text.
    """
    if isinstance(payload, dict):
        payload_type = str(payload.get("type") or "").strip().lower()
        return payload_type in {"confirm", "text", "flex"} or isinstance(payload.get("messages"), list)
    if isinstance(payload, list):
        return all(
            isinstance(item, dict)
            and str(item.get("type") or "").strip().lower() in {"text", "template", "flex"}
            for item in payload
        )
    return False


def _extract_line_rich_payload(text: str) -> Optional[Any]:
    value = text or ""
    marker_index = value.find(_LINE_RICH_MARKER)
    if marker_index >= 0:
        raw = value[marker_index + len(_LINE_RICH_MARKER):].lstrip()
        try:
            payload, _end = json.JSONDecoder().raw_decode(raw)
        except Exception as exc:
            raise ValueError(f"invalid LINE_RICH JSON payload: {exc}") from exc
        return payload

    # Cron/model responses sometimes drop the sentinel and return the JSON card
    # itself.  Treat that as rich only when the entire response is JSON with a
    # known LINE-rich shape; do not hijack arbitrary JSON text.
    raw = value.strip()
    if not raw or raw[0] not in "[{":
        return None
    try:
        payload, end = json.JSONDecoder().raw_decode(raw)
    except Exception:
        return None
    if raw[end:].strip():
        return None
    if not _looks_like_line_rich_payload(payload):
        return None
    return payload


def _extract_line_rich_messages(text: str) -> Optional[List[Dict[str, Any]]]:
    payload = _extract_line_rich_payload(text)
    if payload is None:
        return None
    return _line_messages_from_rich_payload(payload)


def _sanitize_line_plain_text(text: str) -> str:
    """Remove chat-platform markdown from plain LINE text.

    LINE does not render Markdown. Keep rich payloads untouched by calling this
    only after LINE_RICH parsing has failed.
    """
    value = str(text or "")
    value = value.replace("—", "-").replace("–", "-").replace("→", "->")
    value = re.sub(r"```[a-zA-Z0-9_-]*\n?", "", value)
    value = value.replace("```", "")
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", value)
    for token in ("**", "__", "~~", "`"):
        value = value.replace(token, "")

    cleaned_lines: List[str] = []
    for line in value.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
        line = re.sub(r"^\s{0,3}>\s?", "", line)
        line = re.sub(r"^\s*[-*+•]\s+", "", line)
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines).strip()


def _content_type_without_params(value: str) -> str:
    return str(value or "").split(";", 1)[0].strip().lower()


def _coerce_media_max_bytes(extra: Dict[str, Any]) -> int:
    explicit = _env_or_extra("LINE_MEDIA_MAX_BYTES", extra, "media_max_bytes", "")
    if str(explicit or "").strip():
        try:
            parsed = int(float(str(explicit).strip()))
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            logger.warning("[line] invalid media_max_bytes value; using default")

    mb_value = _env_or_extra("LINE_MEDIA_MAX_MB", extra, "media_max_mb", 10)
    try:
        parsed_mb = float(str(mb_value).strip())
        if parsed_mb > 0:
            return int(parsed_mb * 1024 * 1024)
    except (TypeError, ValueError):
        logger.warning("[line] invalid media_max_mb value; using default")
    return _DEFAULT_MEDIA_MAX_BYTES


def _extension_for_image(data: bytes, content_type: str = "") -> str:
    mime = _content_type_without_params(content_type)
    if mime in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if mime == "image/png":
        return ".png"
    if mime == "image/gif":
        return ".gif"
    if mime == "image/webp":
        return ".webp"
    if mime == "image/bmp":
        return ".bmp"

    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"BM"):
        return ".bmp"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


def _image_mime_for_extension(ext: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(str(ext or "").lower(), "image/jpeg")


def _extension_for_audio(data: bytes, content_type: str = "") -> str:
    mime = _content_type_without_params(content_type)
    if mime in {"audio/mp4", "audio/x-m4a", "audio/m4a"}:
        return ".m4a"
    if mime in {"audio/mpeg", "audio/mp3"}:
        return ".mp3"
    if mime in {"audio/ogg", "application/ogg"}:
        return ".ogg"
    if mime == "audio/wav" or mime == "audio/x-wav":
        return ".wav"
    if mime == "audio/webm":
        return ".webm"
    if mime in {"audio/amr", "audio/3gpp", "video/3gpp"}:
        return ".amr"

    # MP4-family audio from LINE commonly arrives as M4A. Sniff the ftyp box
    # rather than trusting application/octet-stream/no Content-Type responses.
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12].decode("ascii", errors="ignore").lower()
        if brand.strip() in {"m4a", "m4b", "m4p", "m4r", "f4a", "f4b", "mp4"}:
            return ".m4a"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return ".mp3"
    if data.startswith(b"OggS"):
        return ".ogg"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"#!AMR"):
        return ".amr"
    return ""


def _audio_mime_for_extension(ext: str) -> str:
    return {
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".amr": "audio/amr",
    }.get(str(ext or "").lower(), "audio/mp4")


class _LineClient:
    """Small native-upstream compatible LINE client used by standalone send/tests."""

    def __init__(self, channel_access_token: str, *, timeout: float = 15.0) -> None:
        self.channel_access_token = channel_access_token
        self.timeout = timeout

    async def reply(self, reply_token: str, messages: List[Dict[str, Any]]) -> None:
        await self._post(_LINE_REPLY_API, {"replyToken": reply_token, "messages": messages})

    async def push(self, chat_id: str, messages: List[Dict[str, Any]]) -> None:
        await self._post(_LINE_PUSH_API, {"to": chat_id, "messages": messages})

    async def _post(self, url: str, payload: Dict[str, Any]) -> None:
        if not AIOHTTP_AVAILABLE or ClientSession is None:
            raise RuntimeError("aiohttp is required for LINE API calls")
        timeout = ClientTimeout(total=self.timeout) if ClientTimeout else None
        async with ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=_line_auth_headers(self.channel_access_token), json=payload) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(f"LINE API HTTP {response.status}: {body[:200]}")


def check_requirements() -> bool:
    """Return True when LINE credentials and aiohttp are present.

    LINE_ENABLED still gates live startup in profile config; this native plugin
    hook is intentionally credential-based so `hermes status/setup` can discover
    the adapter without enabling live webhook handling accidentally.
    """
    return (
        AIOHTTP_AVAILABLE
        and bool(os.getenv("LINE_CHANNEL_SECRET") and os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
    )


def validate_config(config) -> bool:
    """Return True when the LINE channel credentials are configured."""
    extra = getattr(config, "extra", {}) or {}
    channel_secret = os.getenv("LINE_CHANNEL_SECRET") or extra.get("channel_secret", "")
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or extra.get("channel_access_token", "")
    return bool(channel_secret and access_token)


def is_connected(config) -> bool:
    """Check whether LINE is configured (env or config.yaml)."""
    return validate_config(config)


def _env_enablement() -> Optional[Dict[str, Any]]:
    if not (os.getenv("LINE_CHANNEL_ACCESS_TOKEN") and os.getenv("LINE_CHANNEL_SECRET")):
        return None
    seeded: Dict[str, Any] = {}
    if os.getenv("LINE_PORT"):
        try:
            seeded["port"] = int(os.environ["LINE_PORT"])
        except ValueError:
            pass
    if os.getenv("LINE_HOST"):
        seeded["host"] = os.environ["LINE_HOST"]
    if os.getenv("LINE_PUBLIC_URL"):
        seeded["public_url"] = os.environ["LINE_PUBLIC_URL"]
    if os.getenv("LINE_HOME_CHANNEL"):
        seeded["home_channel"] = os.environ["LINE_HOME_CHANNEL"]
    return seeded or {}


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id: Optional[str] = None,
    media_files: Optional[List[str]] = None,
    force_document: bool = False,
) -> Dict[str, Any]:
    extra = getattr(pconfig, "extra", {}) or {}
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or extra.get("channel_access_token", "")
    if not token or not chat_id:
        return {"error": "LINE standalone send: missing token or chat_id"}
    chunks = split_for_line(strip_markdown_preserving_urls(message or "")) or [""]
    messages = [_line_text_message(chunk) for chunk in chunks[:_MAX_LINE_MESSAGES_PER_REQUEST]]
    if media_files:
        messages.append(_line_text_message(f"[{len(media_files)} attachment(s) generated; not deliverable from standalone LINE push]"))
        messages = messages[:_MAX_LINE_MESSAGES_PER_REQUEST]
    try:
        await _LineClient(str(token)).push(str(chat_id), messages)
        return {"success": True, "message_id": None}
    except Exception as exc:
        return {"error": str(exc)}


class LineAdapter(BasePlatformAdapter):
    """Hermes gateway adapter for LINE Messaging API webhooks."""

    MAX_MESSAGE_LENGTH = 5000

    def __init__(self, config: PlatformConfig, **kwargs: Any) -> None:
        super().__init__(config=config, platform=Platform("line"))
        extra = getattr(config, "extra", {}) or {}

        self.channel_secret = str(_env_or_extra("LINE_CHANNEL_SECRET", extra, "channel_secret", "") or "")
        self.channel_access_token = str(
            _env_or_extra("LINE_CHANNEL_ACCESS_TOKEN", extra, "channel_access_token", "") or ""
        )
        self.host = str(_env_or_extra("LINE_HOST", extra, "host", _DEFAULT_HOST) or _DEFAULT_HOST)
        self.port = int(_env_or_extra("LINE_PORT", extra, "port", _DEFAULT_PORT) or _DEFAULT_PORT)
        # Native upstream compatibility aliases.
        self.webhook_host = self.host
        self.webhook_port = self.port
        self.public_base_url = str(
            _env_or_extra("LINE_PUBLIC_URL", extra, "public_url", "") or ""
        ).rstrip("/")
        self.webhook_path = str(
            _env_or_extra("LINE_WEBHOOK_PATH", extra, "webhook_path", _DEFAULT_WEBHOOK_PATH)
            or _DEFAULT_WEBHOOK_PATH
        )
        if not self.webhook_path.startswith("/"):
            self.webhook_path = f"/{self.webhook_path}"

        self.max_message_length = int(extra.get("max_message_length") or self.MAX_MESSAGE_LENGTH)
        self.media_max_bytes = _coerce_media_max_bytes(extra)
        self.allowed_users = set(_csv(os.getenv("LINE_ALLOWED_USERS") or extra.get("allowed_users")))
        self.allowed_chats = set(_csv(os.getenv("LINE_ALLOWED_CHATS") or extra.get("allowed_chats")))
        self.allowed_groups = set(_csv(os.getenv("LINE_ALLOWED_GROUPS") or extra.get("allowed_groups")))
        self.allowed_rooms = set(_csv(os.getenv("LINE_ALLOWED_ROOMS") or extra.get("allowed_rooms")))
        self.allowed_chats.update(self.allowed_groups)
        self.allowed_chats.update(self.allowed_rooms)
        self.allow_all_users = _truthy(os.getenv("LINE_ALLOW_ALL_USERS")) or _truthy(
            extra.get("allow_all_users")
        )
        self.allow_all = self.allow_all_users
        self.slow_response_threshold = float(
            _env_or_extra(
                "LINE_SLOW_RESPONSE_THRESHOLD",
                extra,
                "slow_response_threshold",
                _DEFAULT_SLOW_RESPONSE_THRESHOLD,
            )
            or _DEFAULT_SLOW_RESPONSE_THRESHOLD
        )
        self.pending_text = str(
            _env_or_extra("LINE_PENDING_TEXT", extra, "pending_text", _DEFAULT_PENDING_REPLY_TEXT)
            or _DEFAULT_PENDING_REPLY_TEXT
        )
        self.button_label = str(
            _env_or_extra("LINE_BUTTON_LABEL", extra, "button_label", _DEFAULT_BUTTON_LABEL)
            or _DEFAULT_BUTTON_LABEL
        )
        self.delivered_text = str(
            _env_or_extra("LINE_DELIVERED_TEXT", extra, "delivered_text", _DEFAULT_DELIVERED_TEXT)
            or _DEFAULT_DELIVERED_TEXT
        )
        self.interrupted_text = str(
            _env_or_extra("LINE_INTERRUPTED_TEXT", extra, "interrupted_text", _DEFAULT_INTERRUPTED_TEXT)
            or _DEFAULT_INTERRUPTED_TEXT
        )
        self.require_mention_in_groups = _truthy(
            _env_or_extra("LINE_REQUIRE_MENTION_IN_GROUPS", extra, "require_mention_in_groups", False)
        )
        self.respond_in_groups_when_relevant = _truthy(
            _env_or_extra("LINE_RESPOND_IN_GROUPS_WHEN_RELEVANT", extra, "respond_in_groups_when_relevant", True)
        )
        mention_names_raw = _env_or_extra(
            "LINE_MENTION_NAMES",
            extra,
            "mention_names",
            list(_DEFAULT_MENTION_NAMES),
        )
        self.mention_names = {
            name.strip().lstrip("@").casefold()
            for name in _config_list(mention_names_raw)
            if name.strip().lstrip("@")
        }
        if not self.mention_names:
            self.mention_names = {name.casefold() for name in _DEFAULT_MENTION_NAMES}
        self.mention_patterns = self._compile_mention_patterns(
            _env_or_extra("LINE_MENTION_PATTERNS", extra, "mention_patterns", [])
        )
        self.bot_user_id = str(_env_or_extra("LINE_BOT_USER_ID", extra, "bot_user_id", "") or "").strip()
        self.home_channel = str(_env_or_extra("LINE_HOME_CHANNEL", extra, "home_channel", "") or "").strip()
        self.notify_unauthorized = not str(
            _env_or_extra("LINE_NOTIFY_UNAUTHORIZED", extra, "notify_unauthorized", "true")
            or "true"
        ).strip().lower() in {"0", "false", "no", "n", "off"}
        self.unauthorized_notice_ttl_seconds = int(
            _env_or_extra("LINE_UNAUTHORIZED_NOTICE_TTL_SECONDS", extra, "unauthorized_notice_ttl_seconds", 300)
            or 300
        )
        self.pending_approvals_path = str(
            _env_or_extra(
                "LINE_PENDING_APPROVALS_PATH",
                extra,
                "pending_approvals_path",
                _default_pending_approvals_path(),
            )
            or _default_pending_approvals_path()
        ).strip()
        self.care_events_db_path = str(
            _env_or_extra(
                "LINE_CARE_EVENTS_DB_PATH",
                extra,
                "care_events_db_path",
                _default_care_events_db_path(),
            )
            or _default_care_events_db_path()
        ).strip()
        self.care_events_audit_path = str(
            _env_or_extra(
                "LINE_CARE_EVENTS_AUDIT_PATH",
                extra,
                "care_events_audit_path",
                _default_care_events_audit_path(),
            )
            or _default_care_events_audit_path()
        ).strip()
        self.care_store = LineCareEventStore(
            db_path=self.care_events_db_path,
            audit_path=self.care_events_audit_path,
        )
        self.recent_context_enabled = not str(
            _env_or_extra("LINE_RECENT_CONTEXT_ENABLED", extra, "recent_context_enabled", "true")
            or "true"
        ).strip().lower() in {"0", "false", "no", "n", "off"}
        self.recent_context_ttl_seconds = self._coerce_positive_int(
            _env_or_extra(
                "LINE_RECENT_CONTEXT_TTL_SECONDS",
                extra,
                "recent_context_ttl_seconds",
                _DEFAULT_RECENT_CONTEXT_TTL_SECONDS,
            ),
            default=_DEFAULT_RECENT_CONTEXT_TTL_SECONDS,
        )
        self.recent_context_limit = self._coerce_positive_int(
            _env_or_extra(
                "LINE_RECENT_CONTEXT_LIMIT",
                extra,
                "recent_context_limit",
                _DEFAULT_RECENT_CONTEXT_LIMIT,
            ),
            default=_DEFAULT_RECENT_CONTEXT_LIMIT,
        )
        self.recent_context_db_path = str(
            _env_or_extra(
                "LINE_RECENT_CONTEXT_DB_PATH",
                extra,
                "recent_context_db_path",
                _default_recent_context_db_path(),
            )
            or _default_recent_context_db_path()
        ).strip()
        configured_context_chats = set(
            _csv(os.getenv("LINE_RECENT_CONTEXT_ALLOWED_CHATS") or extra.get("recent_context_allowed_chats"))
        )
        # Do not inherit wildcard chat approval into recent-context capture.  A
        # bot may be broadly reachable while recent family history must remain
        # explicitly scoped.
        self.recent_context_allowed_chats = configured_context_chats or {
            chat_id for chat_id in self.allowed_chats if chat_id != "*"
        }
        configured_context_operators = set(
            _csv(os.getenv("LINE_RECENT_CONTEXT_OPERATOR_USERS") or extra.get("recent_context_operator_users"))
        )
        self.recent_context_operator_users = configured_context_operators or {
            user_id for user_id in self.allowed_users if user_id != "*"
        }
        self.recent_context_store = LineRecentContextStore(
            db_path=self.recent_context_db_path,
            ttl_seconds=self.recent_context_ttl_seconds,
            limit=self.recent_context_limit,
        )
        self.symptom_note_timeout_seconds = self._coerce_positive_int(
            _env_or_extra(
                "LINE_SYMPTOM_NOTE_TIMEOUT_SECONDS",
                extra,
                "symptom_note_timeout_seconds",
                _DEFAULT_SYMPTOM_NOTE_TIMEOUT_SECONDS,
            ),
            default=_DEFAULT_SYMPTOM_NOTE_TIMEOUT_SECONDS,
        )

        self._runner: Optional["web.AppRunner"] = None
        self._site: Optional["web.TCPSite"] = None
        self._client_session: Optional["ClientSession"] = None
        self._client: Optional[Any] = None
        # message_id -> (reply_token, chat_id, stored_at)
        self._reply_tokens: Dict[str, Tuple[str, str, float]] = {}
        self._reply_message_ids_by_chat: Dict[str, str] = {}
        self._cache = RequestCache()
        self._pending_buttons: Dict[str, str] = {}
        self._dedup = _MessageDeduplicator()
        self._seen_events: "OrderedDict[str, float]" = OrderedDict()
        self._approval_notices: Dict[str, float] = {}
        self._exec_approvals: Dict[str, Dict[str, Any]] = {}
        self._symptom_note_states: Dict[str, Dict[str, Any]] = {}
        self._pending_group_media: Dict[str, List[Dict[str, Any]]] = {}
        # Cache LINE display names so group conversations can distinguish
        # participants without making a profile API call on every message.
        self._profile_cache: Dict[str, Tuple[float, str]] = {}
        self._lock_key: Optional[str] = None

    @staticmethod
    def _coerce_positive_int(value: Any, *, default: int) -> int:
        try:
            parsed = int(float(str(value).strip()))
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass
        return default

    @staticmethod
    def _compile_mention_patterns(value: Any) -> List[re.Pattern[str]]:
        patterns: List[re.Pattern[str]] = []
        for raw in _config_list(value):
            try:
                patterns.append(re.compile(raw, flags=re.IGNORECASE))
            except re.error as exc:
                logger.warning("[line] ignoring invalid mention pattern %r: %s", raw, exc)
        return patterns

    @property
    def name(self) -> str:
        return "LINE"

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return minimal chat metadata for Hermes channel-directory/session display."""
        chat_id = str(chat_id or "")
        if chat_id.startswith("U"):
            chat_type = "dm"
            name = "LINE DM"
        elif chat_id.startswith(("G", "C")):
            chat_type = "group"
            name = "LINE group"
        elif chat_id.startswith("R"):
            chat_type = "channel"
            name = "LINE room"
        else:
            chat_type = "dm"
            name = "LINE chat"
        return {"id": chat_id, "name": name, "type": chat_type}

    async def connect(self) -> bool:
        if not AIOHTTP_AVAILABLE:
            self._set_fatal_error(
                "missing_dependency",
                "aiohttp is required for the LINE platform adapter",
                retryable=False,
            )
            return False

        if not self.channel_secret or not self.channel_access_token:
            self._set_fatal_error(
                "missing_credentials",
                "LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN are required",
                retryable=False,
            )
            return False

        try:
            # Prevent two Hermes profiles from consuming the same LINE channel.
            try:
                from gateway.status import acquire_scoped_lock

                lock_identity = _redacted_id(self.channel_secret)
                acquired, existing_lock = acquire_scoped_lock(
                    "line",
                    lock_identity,
                    metadata={"platform": "line", "adapter": "line-platform"},
                )
                if not acquired:
                    self._set_fatal_error(
                        "lock_conflict",
                        "LINE channel is already in use by another Hermes gateway profile",
                        retryable=False,
                    )
                    logger.warning("[line] lock conflict for LINE channel; existing owner=%s", existing_lock)
                    return False
                self._lock_key = lock_identity
            except ImportError:
                self._lock_key = None

            timeout = ClientTimeout(total=30) if ClientTimeout else None
            self._client_session = ClientSession(timeout=timeout)

            app = web.Application()
            app.router.add_get("/health", self._handle_health)
            app.router.add_post(self.webhook_path, self._handle_webhook)
            # A trailing-slash alias saves pain when proxies normalize paths.
            if not self.webhook_path.endswith("/"):
                app.router.add_post(f"{self.webhook_path}/", self._handle_webhook)

            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, self.host, self.port)
            await self._site.start()

            self._running = True
            self._mark_connected()
            logger.info("[line] Webhook server listening on %s:%d%s", self.host, self.port, self.webhook_path)
            return True
        except Exception as exc:
            await self.disconnect()
            self._set_fatal_error("connect_failed", f"LINE connection failed: {exc}", retryable=True)
            logger.error("[line] Failed to connect: %s", exc, exc_info=True)
            return False

    async def disconnect(self) -> None:
        self._running = False

        if self._runner is not None:
            try:
                await self._runner.cleanup()
            except Exception:
                logger.debug("[line] runner cleanup failed", exc_info=True)
            self._runner = None
            self._site = None

        if self._client_session is not None:
            try:
                await self._client_session.close()
            except Exception:
                logger.debug("[line] client session close failed", exc_info=True)
            self._client_session = None

        if self._lock_key:
            try:
                from gateway.status import release_scoped_lock

                release_scoped_lock("line", self._lock_key)
            except Exception:
                logger.debug("[line] lock release failed", exc_info=True)
            self._lock_key = None

        self._mark_disconnected()

    def _prepare_rich_messages_for_send(
        self,
        payload: Any,
        *,
        chat_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        reminder_ids: List[str] = []
        prepared_payload = payload
        if isinstance(payload, dict) and isinstance(payload.get("care"), dict):
            prepared_payload, reminder_id = self._prepare_care_rich_payload(
                payload,
                chat_id=chat_id,
                metadata=metadata,
            )
            reminder_ids.append(reminder_id)
            payload_type = str(prepared_payload.get("type") or "").strip().lower()
            if payload_type == "symptom_scale":
                return [_line_symptom_scale_flex_message(prepared_payload)], reminder_ids
            return [_line_care_flex_message(prepared_payload)], reminder_ids
        return _line_messages_from_rich_payload(prepared_payload), reminder_ids

    def _prepare_care_rich_payload(
        self,
        payload: Dict[str, Any],
        *,
        chat_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        care = payload.get("care") or {}
        if not isinstance(care, dict):
            raise ValueError("care payload must be an object")

        subject = _normalise_required_token(care.get("subject"), "subject")
        if subject not in _CARE_SUBJECT_LABELS:
            raise ValueError("care payload subject must be one of: mum, dad")
        routine_id = _normalise_required_token(care.get("routine_id") or care.get("routineId"), "routine_id")
        routine_type = _normalise_required_token(care.get("routine_type") or care.get("routineType"), "routine_type")
        slot = str(care.get("slot") or "").strip().lower()
        if slot and not all(ch.isalnum() or ch in {"_", "-"} for ch in slot):
            raise ValueError("care payload slot contains unsupported characters")

        metric = ""
        body_part = str(care.get("body_part") or care.get("bodyPart") or "").strip().lower()
        if care.get("metric") is not None:
            metric = _normalise_care_metric(care.get("metric"))
        if metric == "pain" and not body_part:
            body_part = "right_arm"
        if metric == "right_arm_zing":
            body_part = "right_arm"

        reminder_id = self.care_store.create_reminder(
            subject=subject,
            routine_id=routine_id,
            routine_type=routine_type,
            slot=slot,
            scheduled_for=str(care.get("scheduled_for") or care.get("scheduledFor") or ""),
            local_date=str(care.get("local_date") or care.get("localDate") or ""),
            chat_type=self._chat_type_for_destination(chat_id),
            recipient_id=chat_id,
            metadata={
                "care": {
                    "subject": subject,
                    "routine_id": routine_id,
                    "routine_type": routine_type,
                    "slot": slot,
                    "metric": metric,
                    "body_part": body_part,
                },
                "line_rich_followup_payload": self._care_followup_payload_for_metadata(payload),
                "send_metadata_keys": sorted((metadata or {}).keys()),
            },
        )

        prepared = copy.deepcopy(payload)
        prepared.pop("care", None)
        prepared["_care"] = {
            "subject": subject,
            "routine_id": routine_id,
            "routine_type": routine_type,
            "slot": slot,
            "metric": metric,
            "body_part": body_part,
            "reminder_id": reminder_id,
        }
        actions = []
        for action in prepared.get("actions") or []:
            if not isinstance(action, dict):
                raise ValueError("LINE rich actions must be objects")
            action_copy = dict(action)
            if action_copy.get("status") is not None:
                status = _normalise_care_status(action_copy.pop("status"))
                action_copy["type"] = "postback"
                action_copy["data"] = self._care_postback_data(reminder_id=reminder_id, status=status)
                if not (action_copy.get("displayText") or action_copy.get("display_text")):
                    action_copy["displayText"] = str(action_copy.get("label") or "")
            elif action_copy.get("metric") is not None and action_copy.get("value") is not None:
                metric_value = _normalise_care_value(action_copy.pop("value"))
                metric_name = _normalise_care_metric(action_copy.pop("metric"))
                action_copy["type"] = "postback"
                action_copy["data"] = self._care_postback_data(reminder_id=reminder_id, metric=metric_name, value=metric_value)
                if not (action_copy.get("displayText") or action_copy.get("display_text")):
                    action_copy["displayText"] = str(action_copy.get("label") or "")
            actions.append(action_copy)
        prepared["actions"] = actions
        return prepared, reminder_id

    def _care_followup_payload_for_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        followup = copy.deepcopy(payload)
        actions = []
        for action in followup.get("actions") or []:
            if not isinstance(action, dict):
                continue
            clean_action = {
                "label": action.get("label"),
                "status": action.get("status"),
            }
            actions.append({k: v for k, v in clean_action.items() if v is not None})
        followup["actions"] = actions
        return followup

    def _care_postback_data(
        self,
        *,
        reminder_id: str,
        status: str = "",
        metric: str = "",
        value: Optional[int] = None,
    ) -> str:
        parts = [f"care:v1", f"rid={reminder_id}"]
        if metric:
            metric_name = _normalise_care_metric(metric)
            metric_value = _normalise_care_value(value)
            parts.extend([f"metric={metric_name}", f"value={metric_value}"])
        else:
            parts.append(f"status={_normalise_care_status(status)}")
        data = ";".join(parts)
        if len(data) > 300:
            raise ValueError("LINE care postback data exceeds 300 characters")
        return data

    def _chat_type_for_destination(self, chat_id: str) -> str:
        chat_id = str(chat_id or "")
        if chat_id.startswith("U"):
            return "dm"
        if chat_id.startswith("G"):
            return "group"
        if chat_id.startswith("R"):
            return "room"
        return "unknown"

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        text = (content or "").strip()
        if not text:
            return SendResult(success=True)

        if not _is_system_bypass(text):
            pending_rid = self._pending_buttons.get(str(chat_id))
            if pending_rid:
                self._cache.set_ready(pending_rid, text)
                return SendResult(success=True, message_id=pending_rid)

        # Native upstream tests and standalone shims use a lightweight _LineClient
        # with chat_id-keyed reply tokens. Live gateway replies continue to
        # use message_id-keyed reply_to below so reply failures never spill into
        # Push quota.
        if reply_to is None and self._client is not None and self._client_session is None:
            return await self._send_native_client_compat(str(chat_id), text)

        try:
            rich_payload = _extract_line_rich_payload(text)
            rich_messages: Optional[List[Dict[str, Any]]] = None
            care_reminder_ids: List[str] = []
            if rich_payload is not None:
                rich_messages, care_reminder_ids = self._prepare_rich_messages_for_send(
                    rich_payload,
                    chat_id=str(chat_id),
                    metadata=metadata,
                )
        except ValueError as exc:
            return SendResult(success=False, error=str(exc), retryable=False)
        if rich_messages is not None:
            result = await self._send_message_objects(str(chat_id), rich_messages, reply_to=reply_to)
            for reminder_id in care_reminder_ids:
                try:
                    if result.success:
                        self.care_store.mark_reminder_sent(reminder_id, line_message_id=result.message_id or "")
                    else:
                        self.care_store.mark_reminder_delivery_failed(reminder_id, error=result.error or "")
                except Exception:
                    logger.warning("[line] failed to update care reminder state", exc_info=True)
            return result

        chunks = self._split_text(_sanitize_line_plain_text(text))
        if not chunks:
            return SendResult(success=True)

        first_message_id: Optional[str] = None
        raw_responses: List[Any] = []

        # User-initiated LINE replies must stay on the reply API.  The reply
        # token is one-time and short-lived, while push quota is scarce and
        # reserved for proactive reminders.  Never spill reply overflow or reply
        # failures into push.
        if reply_to:
            token_entry = self._reply_tokens.pop(reply_to, None)
            if str(chat_id):
                self._reply_message_ids_by_chat.pop(str(chat_id), None)
            if not token_entry:
                return SendResult(
                    success=False,
                    error="LINE reply token unavailable; not falling back to push quota",
                    retryable=False,
                )
            reply_token, token_chat_id, stored_at = token_entry
            if token_chat_id != str(chat_id) or time.time() - stored_at > _REPLY_TOKEN_TTL_SECONDS:
                return SendResult(
                    success=False,
                    error="LINE reply token stale or mismatched; not falling back to push quota",
                    retryable=False,
                )

            reply_chunks = self._fit_reply_chunks(chunks)
            result = await self._reply_with_token(reply_token, reply_chunks)
            raw_responses.append(result.raw_response)
            if result.success:
                return SendResult(
                    success=True,
                    message_id=result.message_id or "line-reply",
                    raw_response=raw_responses,
                )
            return SendResult(
                success=False,
                message_id=result.message_id,
                error=f"LINE reply failed; not falling back to push quota: {result.error or 'unknown'}",
                raw_response=raw_responses,
                retryable=False,
            )

        for chunk in chunks:
            result = await self._push_message(str(chat_id), chunk)
            raw_responses.append(result.raw_response)
            if not result.success:
                return SendResult(
                    success=False,
                    message_id=first_message_id,
                    error=result.error,
                    raw_response=raw_responses,
                    retryable=result.retryable,
                )
            if not first_message_id:
                first_message_id = result.message_id

        return SendResult(
            success=True,
            message_id=first_message_id,
            raw_response=raw_responses,
        )

    async def _send_native_client_compat(self, chat_id: str, text: str) -> SendResult:
        if self._client is None:
            return SendResult(success=False, error="LINE adapter not connected")
        chunks = split_for_line(strip_markdown_preserving_urls(text)) or [""]
        messages = [_line_text_message(chunk) for chunk in chunks[:_MAX_LINE_MESSAGES_PER_REQUEST]]
        token_entry = self._reply_tokens.pop(chat_id, None)
        if token_entry:
            if len(token_entry) == 2:
                reply_token, expires_at = token_entry  # native shape: (token, expires_at)
                usable = bool(reply_token) and time.time() < float(expires_at)
            else:
                reply_token, token_chat_id, stored_at = token_entry
                usable = bool(reply_token) and token_chat_id == chat_id and time.time() - float(stored_at) <= _REPLY_TOKEN_TTL_SECONDS
            if usable:
                try:
                    await self._client.reply(reply_token, messages)
                    return SendResult(success=True, message_id=str(reply_token))
                except Exception as exc:
                    logger.info("[line] native-compat reply failed; falling back to push: %s", exc)
        try:
            await self._client.push(chat_id, messages)
            return SendResult(success=True)
        except Exception as exc:
            return SendResult(success=False, error=str(exc), retryable=True)

    def format_message(self, content: str) -> str:
        return strip_markdown_preserving_urls(content)

    def _cached_response_messages(self, payload: Any) -> List[Dict[str, Any]]:
        text = str(payload or "")
        try:
            rich_messages = _extract_line_rich_messages(text)
        except Exception:
            rich_messages = None
        if rich_messages is not None:
            return self._fit_reply_messages(rich_messages)
        chunks = self._fit_reply_chunks(self._split_text(_sanitize_line_plain_text(text)))
        return [_line_text_message(chunk) for chunk in chunks[:_MAX_LINE_MESSAGES_PER_REQUEST]]

    async def _maybe_handle_show_response_postback(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        data: str,
    ) -> bool:
        try:
            parsed = json.loads(data or "{}")
        except (TypeError, json.JSONDecodeError):
            return False
        if not isinstance(parsed, dict) or parsed.get("action") != "show_response":
            return False
        request_id = str(parsed.get("request_id") or "")
        if not request_id:
            return True
        reply_token = str(event.get("replyToken") or "")
        if not reply_token:
            return True
        entry = self._cache.get(request_id)
        if entry is None:
            return True
        chat_id = str(source.chat_id or entry.chat_id or "")
        try:
            if entry.state is State.READY:
                messages = self._cached_response_messages(entry.payload)
                if not messages:
                    messages = [_line_text_message(self.interrupted_text)]
                result = await self._reply_message_objects(reply_token, messages)
                if result.success:
                    self._cache.mark_delivered(request_id)
                    self._pending_buttons.pop(chat_id, None)
                return True
            if entry.state is State.ERROR:
                text = str(entry.payload or self.interrupted_text)
                result = await self._reply_with_token(reply_token, [text])
                if result.success:
                    self._cache.mark_delivered(request_id)
                    self._pending_buttons.pop(chat_id, None)
                return True
            if entry.state is State.DELIVERED:
                await self._reply_with_token(reply_token, [self.delivered_text])
                return True
            if entry.state is State.PENDING:
                await self._reply_with_token(reply_token, [self.pending_text])
                return True
        except Exception:
            logger.debug("[line] show_response postback handling failed", exc_info=True)
            return True
        return True

    async def _send_slow_response_button(self, chat_id: str) -> None:
        chat_id = str(chat_id or "")
        if not chat_id or chat_id in self._pending_buttons:
            return
        message_id = self._reply_message_ids_by_chat.get(chat_id)
        if not message_id:
            return
        token_entry = self._reply_tokens.pop(message_id, None)
        self._reply_message_ids_by_chat.pop(chat_id, None)
        if not token_entry:
            return
        reply_token, token_chat_id, stored_at = token_entry
        if token_chat_id != chat_id or time.time() - stored_at > _REPLY_TOKEN_TTL_SECONDS:
            return
        request_id = self._cache.register_pending(chat_id)
        self._pending_buttons[chat_id] = request_id
        message = build_postback_button_message(self.pending_text, self.button_label, request_id)
        result = await self._reply_message_objects(reply_token, [message])
        if not result.success:
            self._pending_buttons.pop(chat_id, None)
            self._cache.set_error(request_id, result.error or self.interrupted_text)
            logger.info("[line] slow-response button reply failed: %s", result.error or "unknown")

    async def _keep_typing(self, chat_id: str, *args, **kwargs) -> None:
        if self.slow_response_threshold <= 0 or not chat_id:
            await super()._keep_typing(chat_id, *args, **kwargs)
            return

        async def _fire_postback() -> None:
            try:
                await asyncio.sleep(float(self.slow_response_threshold))
                await self._send_slow_response_button(str(chat_id))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("[line] slow-response postback task failed", exc_info=True)

        post_task = asyncio.create_task(_fire_postback())
        try:
            await super()._keep_typing(chat_id, *args, **kwargs)
        finally:
            if not post_task.done():
                post_task.cancel()
                try:
                    await post_task
                except BaseException:
                    pass

    async def interrupt_session_activity(self, session_key: str, chat_id: str) -> None:
        await super().interrupt_session_activity(session_key, chat_id)
        rid = self._pending_buttons.pop(str(chat_id or ""), None)
        if rid:
            self._cache.set_error(rid, self.interrupted_text)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """Best-effort LINE loading animation for DMs only.

        LINE only supports loading animation in 1:1 chats. Group/room calls fail,
        so we quietly ignore those errors.
        """
        if not chat_id or not str(chat_id).startswith("U"):
            return
        try:
            await self._post_json(
                _LINE_LOADING_API,
                {"chatId": str(chat_id), "loadingSeconds": 5},
                expect_body=False,
            )
        except Exception:
            logger.debug("[line] loading animation failed", exc_info=True)

    async def send_exec_approval(
        self,
        *,
        chat_id: str,
        command: str,
        session_key: str,
        description: str = "dangerous command",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send LINE postback buttons for a blocking dangerous-command approval."""
        approval_id = f"a_{uuid.uuid4().hex[:16]}"
        self._prune_exec_approvals()
        self._exec_approvals[approval_id] = {
            "session_key": str(session_key or ""),
            "command": str(command or ""),
            "created_at": time.time(),
        }

        cmd_preview = str(command or "").strip()
        if len(cmd_preview) > 800:
            cmd_preview = cmd_preview[:797].rstrip() + "..."
        desc = str(description or "dangerous command").strip() or "dangerous command"
        text = (
            "⚠️ Dangerous command requires approval:\n"
            f"{cmd_preview}\n\n"
            f"Reason: {desc}\n\n"
            "เลือกปุ่มด้านล่างเพื่อให้ agent ทำต่อ หรือปฏิเสธคำสั่งนี้"
        )
        actions = [
            {"type": "postback", "label": "Approve once", "data": self._exec_approval_postback_data(approval_id, "once"), "displayText": "Approve once"},
            {"type": "postback", "label": "This session", "data": self._exec_approval_postback_data(approval_id, "session"), "displayText": "Approve session"},
            {"type": "postback", "label": "Always", "data": self._exec_approval_postback_data(approval_id, "always"), "displayText": "Approve always"},
            {"type": "postback", "label": "Deny", "data": self._exec_approval_postback_data(approval_id, "deny"), "displayText": "Deny"},
        ]
        message = _line_text_with_quick_reply_message({"text": text, "actions": actions})
        return await self._push_message_objects(str(chat_id), [message])

    def _exec_approval_postback_data(self, approval_id: str, choice: str, *, resolve_all: bool = False) -> str:
        data = f"exec_approval:v1;aid={approval_id};choice={choice}"
        if resolve_all:
            data += ";all=1"
        if len(data) > 300:
            raise ValueError("LINE exec approval postback data exceeds 300 characters")
        return data

    def _parse_exec_approval_postback_data(self, data: str) -> Optional[Dict[str, Any]]:
        data = str(data or "").strip()
        if not data.startswith("exec_approval:v1;"):
            return None
        parsed: Dict[str, str] = {}
        for part in data.split(";")[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            parsed[key.strip()] = value.strip()
        approval_id = parsed.get("aid", "")
        choice = parsed.get("choice", "")
        if not approval_id or choice not in {"once", "session", "always", "deny"}:
            return None
        return {
            "approval_id": approval_id,
            "choice": choice,
            "resolve_all": parsed.get("all") in {"1", "true", "yes"},
        }

    async def _handle_exec_approval_postback(
        self,
        event: Dict[str, Any],
        parsed: Dict[str, Any],
    ) -> None:
        self._prune_exec_approvals()
        approval_id = str(parsed.get("approval_id") or "")
        entry = self._exec_approvals.pop(approval_id, None)
        reply_token = str(event.get("replyToken") or "")
        if not entry:
            if reply_token:
                await self._reply_with_token(reply_token, ["ปุ่มอนุมัตินี้หมดอายุแล้ว หรือคำสั่งถูกจัดการไปแล้วค่ะ"])
            return

        session_key = str(entry.get("session_key") or "")
        choice = str(parsed.get("choice") or "")
        resolve_all = bool(parsed.get("resolve_all"))
        try:
            from tools.approval import resolve_gateway_approval

            count = resolve_gateway_approval(session_key, choice, resolve_all=resolve_all)
        except Exception as exc:
            logger.warning("[line] failed to resolve exec approval postback: %s", exc)
            count = 0

        if not reply_token:
            return
        if not count:
            await self._reply_with_token(reply_token, ["ไม่มีคำสั่งที่รออนุมัติแล้วค่ะ"])
            return
        if choice == "deny":
            await self._reply_with_token(reply_token, ["ปฏิเสธคำสั่งแล้วค่ะ Agent จะทำต่อโดยไม่รันคำสั่งนี้"])
            return
        scope = {
            "once": "ครั้งนี้",
            "session": "ทั้ง session นี้",
            "always": "ถาวรสำหรับ pattern นี้",
        }.get(choice, "ครั้งนี้")
        await self._reply_with_token(reply_token, [f"อนุมัติคำสั่งแล้วค่ะ ({scope}) Agent กำลังทำต่อ..."])

    def _prune_exec_approvals(self) -> None:
        now = time.time()
        for key, value in list(self._exec_approvals.items()):
            if now - float(value.get("created_at") or 0) > _EXEC_APPROVAL_TTL_SECONDS:
                self._exec_approvals.pop(key, None)

    async def _handle_health(self, request: "web.Request") -> "web.Response":
        return web.json_response({"ok": True, "platform": "line"})

    def _line_sticker_description(self, message: Dict[str, Any]) -> str:
        """Build an agent-visible description from LINE sticker metadata."""
        package_id = str(message.get("packageId") or "").strip()
        sticker_id = str(message.get("stickerId") or "").strip()
        resource_type = str(message.get("stickerResourceType") or "").strip()
        raw_keywords = message.get("keywords") or []
        if isinstance(raw_keywords, str):
            keywords = [raw_keywords]
        elif isinstance(raw_keywords, (list, tuple, set)):
            keywords = [str(item).strip() for item in raw_keywords if str(item).strip()]
        else:
            keywords = []

        details = []
        if package_id:
            details.append(f"package {package_id}")
        if sticker_id:
            details.append(f"sticker {sticker_id}")
        if resource_type:
            details.append(f"resource {resource_type}")
        if keywords:
            details.append("keywords: " + ", ".join(keywords[:8]))

        description = "a LINE sticker"
        if details:
            description += " (" + "; ".join(details) + ")"
        return description

    async def _handle_sticker_message(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        message_id: str,
    ) -> None:
        """Forward LINE stickers as sticker chat events instead of unsupported media."""
        from gateway.sticker_cache import build_sticker_injection

        message = event.get("message") or {}
        text = build_sticker_injection(self._line_sticker_description(message))
        msg_event = MessageEvent(
            text=text,
            message_type=MessageType.STICKER,
            source=source,
            raw_message=event,
            message_id=message_id,
        )
        await self.handle_message(msg_event)

    async def _handle_webhook(self, request: "web.Request") -> "web.Response":
        body = await request.read()
        signature = request.headers.get("X-Line-Signature", "")
        if not self._verify_signature(body, signature):
            logger.warning("[line] rejected webhook with invalid signature")
            return web.Response(status=401, text="invalid signature")

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            logger.warning("[line] rejected webhook with invalid JSON")
            return web.Response(status=400, text="invalid json")

        events = payload.get("events") or []
        for event in events:
            try:
                await self._handle_line_event(event)
            except Exception:
                logger.error("[line] failed handling event", exc_info=True)

        return web.Response(status=200, text="OK")

    async def _handle_line_event(self, event: Dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        if self._is_duplicate(event):
            return

        event_type = str(event.get("type") or "")
        message = event.get("message") or {}
        message_id = str(message.get("id") or event.get("webhookEventId") or "")
        source_data = event.get("source") or {}
        source = self._source_from_line(source_data, message_id=message_id)
        if source is None:
            logger.warning("[line] dropped event with unsupported/missing source")
            return

        if not self._adapter_allows(source):
            logger.warning(
                "[line] dropped unauthorized source before gateway auth: chat=%s user=%s event=%s",
                _redacted_id(source.chat_id or ""),
                _redacted_id(source.user_id or ""),
                event_type,
            )
            self._record_pending_approval(event, source)
            await self._notify_approval_required(event, source)
            return

        await self._enrich_source_profile(source, source_data)

        # Follow/join events are authorization-relevant but not chat messages.
        if event_type == "postback":
            await self._handle_postback_event(event, source)
            return
        if event_type != "message":
            return

        reply_token = str(event.get("replyToken") or "")
        if message_id and reply_token:
            self._reply_tokens[message_id] = (reply_token, str(source.chat_id), time.time())
            if source.chat_id:
                self._reply_message_ids_by_chat[str(source.chat_id)] = message_id
            self._prune_reply_tokens()

        message_type = str(message.get("type") or "")
        if message_type != "text" and self._group_message_requires_mention(source) and not self._line_event_mentions_bot(event):
            if message_type == "image":
                self._remember_pending_group_media(event, source, message_id=message_id, line_message_type="image")
                self._remember_recent_group_context(
                    event,
                    source,
                    message_type="image",
                    message_id=message_id,
                )
            self._ignore_unmentioned_group_message(source)
            self._reply_tokens.pop(message_id, None)
            return
        if message_type == "image":
            await self._handle_image_message(event, source, message_id=message_id)
            return
        if message_type == "audio":
            await self._handle_audio_message(event, source, message_id=message_id)
            return
        if message_type == "sticker":
            await self._handle_sticker_message(event, source, message_id=message_id)
            return

        if message_type != "text":
            await self._maybe_reply_unsupported(
                event,
                "ตอนนี้ดูรูปภาพ ฟังเสียง และอ่านข้อความได้ก่อนนะคะ ถ้าเป็นวิดีโอหรือไฟล์ ขอให้ส่งเป็นข้อความมาก่อนค่ะ",
            )
            return

        text = str(message.get("text") or "").strip()
        if not text:
            return
        if await self._maybe_capture_symptom_note(event, source, text):
            self._reply_tokens.pop(message_id, None)
            return
        if self._group_message_requires_mention(source) and not self._line_event_mentions_bot(event):
            self._remember_recent_group_context(
                event,
                source,
                message_type="text",
                text=text,
                message_id=message_id,
            )
            self._ignore_unmentioned_group_message(source)
            self._reply_tokens.pop(message_id, None)
            return

        pending_photo_event = await self._message_event_with_pending_group_image(
            event,
            source,
            text=text,
            message_id=message_id,
        )
        if pending_photo_event is not None:
            await self.handle_message(pending_photo_event)
            return

        operator_context_event = await self._message_event_with_operator_recent_context(
            event,
            source,
            text=text,
            message_id=message_id,
        )
        if operator_context_event is not None:
            await self.handle_message(operator_context_event)
            return

        msg_event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            source=source,
            raw_message=event,
            message_id=message_id,
            channel_prompt=self._recent_context_prompt_for_group(source),
        )
        await self.handle_message(msg_event)

    async def _handle_postback_event(self, event: Dict[str, Any], source: SessionSource) -> None:
        postback = event.get("postback") or {}
        if not isinstance(postback, dict):
            return
        data = str(postback.get("data") or "")
        if await self._maybe_handle_show_response_postback(event, source, data):
            return
        exec_approval = self._parse_exec_approval_postback_data(data)
        if exec_approval is not None:
            await self._handle_exec_approval_postback(event, exec_approval)
            return

        parsed = self._parse_care_postback_data(data)
        if parsed is None:
            return

        result = self.care_store.record_response(
            reminder_id=parsed["reminder_id"],
            status=parsed.get("status", "recorded"),
            metric=parsed.get("metric", ""),
            value=parsed.get("value"),
            actor_id=source.user_id or "",
            chat_id=source.chat_id or "",
            line_webhook_event_id=str(event.get("webhookEventId") or ""),
            raw_json={
                "kind": "line_care_postback",
                "data": str(postback.get("data") or "")[:300],
                "params": postback.get("params") or {},
                "source_type": (event.get("source") or {}).get("type") or "",
            },
        )
        if result.get("duplicate"):
            return

        if result.get("ok") and parsed.get("metric"):
            self._remember_symptom_note_state(result.get("reminder") or {}, parsed, source)

        reply_token = str(event.get("replyToken") or "")
        if not reply_token:
            return
        if result.get("ok"):
            followup_at = None
            if parsed.get("status") == "not_yet":
                followup_at = self._schedule_care_followup(result.get("reminder") or {}, source)
            if parsed.get("metric"):
                reminder = result.get("reminder") or {}
                text = self._care_metric_confirmation_text(
                    reminder,
                    str(parsed.get("metric") or ""),
                    int(parsed.get("value")),
                )
                if self._is_symptom_note_reminder(reminder):
                    text = f"{text}\nถ้ามีรายละเอียดเพิ่ม พิมพ์ต่อได้เลยค่ะ หรือพิมพ์ “ไม่ต้องจด”"
            else:
                text = self._care_confirmation_text(result.get("reminder") or {}, parsed.get("status", "recorded"), followup_at=followup_at)
        else:
            text = "ขอโทษค่ะ ปุ่มนี้หมดอายุหรือหา reminder เดิมไม่เจอ เลยยังไม่บันทึกนะคะ"
        try:
            await self._reply_with_token(reply_token, [text])
        except Exception:
            logger.debug("[line] care postback confirmation failed", exc_info=True)

    def _symptom_note_state_key(self, source: SessionSource) -> str:
        return str(source.chat_id or source.user_id or "")

    def _is_symptom_note_reminder(self, reminder: Dict[str, Any]) -> bool:
        if str(reminder.get("subject") or "").strip().lower() != "mum":
            return False
        if str(reminder.get("routine_type") or "").strip().lower() != "symptom_check":
            return False
        metadata = self._care_metadata(reminder)
        care = metadata.get("care") if isinstance(metadata.get("care"), dict) else {}
        metric = str(care.get("metric") or "").strip().lower()
        if metric in _ALLOWED_CARE_METRICS:
            return True
        routine_id = str(reminder.get("routine_id") or "").strip().lower()
        return "right_arm_pain" in routine_id or "right_arm_zing" in routine_id

    def _care_metadata(self, reminder: Dict[str, Any]) -> Dict[str, Any]:
        try:
            parsed = json.loads(str(reminder.get("metadata_json") or "{}"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _symptom_note_slot(self, reminder: Dict[str, Any]) -> str:
        slot = str(reminder.get("slot") or "").strip().lower()
        routine_id = str(reminder.get("routine_id") or "").strip().lower()
        if slot:
            return slot
        if "night" in routine_id or "evening" in routine_id:
            return "night"
        if "morning" in routine_id or "am" in routine_id:
            return "morning"
        return "unknown"

    def _symptom_note_group_routine_id(self, reminder: Dict[str, Any]) -> str:
        subject = str(reminder.get("subject") or "mum").strip().lower() or "mum"
        slot = self._symptom_note_slot(reminder)
        if slot in {"morning", "night"}:
            return f"{subject}_right_arm_symptom_check_{slot}"
        return f"{subject}_right_arm_symptom_check"

    def _remember_symptom_note_state(
        self,
        reminder: Dict[str, Any],
        parsed: Dict[str, Any],
        source: SessionSource,
    ) -> None:
        if not self._is_symptom_note_reminder(reminder):
            return
        key = self._symptom_note_state_key(source)
        if not key:
            return
        now = time.time()
        metric = str(parsed.get("metric") or "").strip().lower()
        self._symptom_note_states[key] = {
            "created_at": now,
            "expires_at": now + max(1, int(self.symptom_note_timeout_seconds or _DEFAULT_SYMPTOM_NOTE_TIMEOUT_SECONDS)),
            "reminder_id": str(reminder.get("reminder_id") or parsed.get("reminder_id") or ""),
            "subject": str(reminder.get("subject") or "mum").strip().lower() or "mum",
            "routine_id": self._symptom_note_group_routine_id(reminder),
            "source_routine_id": str(reminder.get("routine_id") or ""),
            "slot": self._symptom_note_slot(reminder),
            "linked_metric": metric,
            "linked_value": parsed.get("value"),
        }
        self._prune_symptom_note_states()

    def _prune_symptom_note_states(self) -> None:
        now = time.time()
        for key, state in list(self._symptom_note_states.items()):
            if float(state.get("expires_at") or 0) <= now:
                self._symptom_note_states.pop(key, None)

    def _is_symptom_note_cancel_text(self, text: str) -> bool:
        normalized = " ".join(str(text or "").strip().lower().split())
        if not normalized:
            return False
        return any(phrase in normalized for phrase in _SYMPTOM_NOTE_CANCEL_PHRASES)

    async def _maybe_capture_symptom_note(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        text: str,
    ) -> bool:
        self._prune_symptom_note_states()
        key = self._symptom_note_state_key(source)
        state = self._symptom_note_states.get(key)
        if not state:
            return False

        reply_token = str(event.get("replyToken") or "")
        webhook_event_id = str(event.get("webhookEventId") or "")
        raw_common = {
            "slot": state.get("slot") or "",
            "source_routine_id": state.get("source_routine_id") or "",
            "linked_metric": state.get("linked_metric") or "",
            "linked_value": state.get("linked_value"),
        }
        if self._is_symptom_note_cancel_text(text):
            self._symptom_note_states.pop(key, None)
            self.care_store.record_manual_note(
                reminder_id=str(state.get("reminder_id") or ""),
                subject=str(state.get("subject") or "mum"),
                routine_id=str(state.get("routine_id") or "mum_right_arm_symptom_check"),
                event_type="correction",
                status="skipped",
                actor_id=source.user_id or "",
                chat_id=source.chat_id or "",
                line_webhook_event_id=webhook_event_id,
                raw_json={"kind": "line_symptom_note_cancel", **raw_common},
            )
            if reply_token:
                await self._reply_with_token(reply_token, ["ได้ค่ะ รอบนี้ไม่จดรายละเอียดเพิ่มนะคะ"])
            return True

        result = self.care_store.record_manual_note(
            reminder_id=str(state.get("reminder_id") or ""),
            subject=str(state.get("subject") or "mum"),
            routine_id=str(state.get("routine_id") or "mum_right_arm_symptom_check"),
            event_type="manual_note",
            status="recorded",
            actor_id=source.user_id or "",
            chat_id=source.chat_id or "",
            line_webhook_event_id=webhook_event_id,
            note=text,
            raw_json={"kind": "line_symptom_note", **raw_common},
        )
        self._symptom_note_states.pop(key, None)
        if reply_token and result.get("ok"):
            await self._reply_with_token(reply_token, ["จดเพิ่มให้แล้วค่ะ 📝"])
        return True

    def _parse_care_postback_data(self, data: str) -> Optional[Dict[str, Any]]:
        data = str(data or "").strip()
        if not data.startswith("care:v1;"):
            return None
        params: Dict[str, str] = {}
        for part in data.split(";")[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            params[key.strip()] = value.strip()
        reminder_id = params.get("rid") or ""
        if not reminder_id:
            raise ValueError("care postback missing reminder id")
        if params.get("metric") is not None:
            metric = _normalise_care_metric(params.get("metric"))
            metric_value = _normalise_care_value(params.get("value"))
            return {"reminder_id": reminder_id, "status": "recorded", "metric": metric, "value": metric_value}
        status = _normalise_care_status(params.get("status"))
        return {"reminder_id": reminder_id, "status": status}

    def _care_metric_confirmation_text(self, reminder: Dict[str, Any], metric: str, value: int) -> str:
        metric = _normalise_care_metric(metric)
        value = _normalise_care_value(value)
        subject_label = _CARE_SUBJECT_LABELS.get(str(reminder.get("subject") or "").strip().lower(), "คุณแม่")
        label = _CARE_METRIC_LABELS.get(metric, metric)
        if metric == "pain":
            if value == 0:
                band = "ไม่ปวด"
            elif value <= 3:
                band = "ปวดเล็กน้อย"
            elif value <= 6:
                band = "ปวดปานกลาง"
            elif value <= 9:
                band = "ปวดมาก"
            else:
                band = "ปวดที่สุด"
            return f"บันทึกให้แล้วค่ะ {subject_label}{label} {value}/10 — {band} 📝"
        if value == 0:
            band = "ไม่มีอาการ"
        elif value <= 3:
            band = "เสียวเล็กน้อย"
        elif value <= 6:
            band = "เสียวปานกลาง"
        elif value <= 9:
            band = "เสียวมาก"
        else:
            band = "รุนแรงมาก"
        return f"บันทึกให้แล้วค่ะ {subject_label}{label} {value}/10 — {band} 📝"

    def _care_confirmation_text(
        self,
        reminder: Dict[str, Any],
        status: str,
        *,
        followup_at: Optional[datetime] = None,
    ) -> str:
        subject = str(reminder.get("subject") or "").strip().lower()
        routine_type = str(reminder.get("routine_type") or "").strip().lower()
        subject_label = _CARE_SUBJECT_LABELS.get(subject, "รายการนี้")
        verb = (_CARE_ROUTINE_VERBS.get(routine_type) or {}).get(status)
        if status == "not_yet":
            if followup_at is not None:
                return f"รับทราบค่ะ ตั้งเตือนอีกครั้งแล้วนะคะ\nจะเตือนอีกทีใน 1 ชั่วโมง เวลา {followup_at.strftime('%H.%M')} น."
            return "รับทราบค่ะ แต่ยังตั้งเตือนซ้ำให้อัตโนมัติไม่สำเร็จนะคะ"
        if verb:
            if status in {"done", "taken"}:
                return f"บันทึกให้แล้วค่ะ: {subject_label}{verb} ✅"
            return f"รับทราบค่ะ บันทึกว่า{subject_label}{verb}ตอนนี้"
        if status == "not_needed":
            return f"บันทึกให้แล้วค่ะ: {subject_label}ยังไม่จำเป็นต้องใช้ตอนนี้"
        if status == "skipped":
            return f"รับทราบค่ะ บันทึกว่า{subject_label}ข้ามรอบนี้"
        return f"บันทึกให้แล้วค่ะ: {subject_label} ({status})"

    def _schedule_care_followup(self, reminder: Dict[str, Any], source: SessionSource) -> Optional[datetime]:
        """Create a one-shot follow-up reminder one hour after a not-yet tap."""
        try:
            metadata = json.loads(str(reminder.get("metadata_json") or "{}"))
            payload = metadata.get("line_rich_followup_payload")
            if not isinstance(payload, dict):
                raise ValueError("missing follow-up payload")

            followup_at = datetime.now().astimezone() + timedelta(hours=1)
            payload = copy.deepcopy(payload)
            care = payload.setdefault("care", {})
            if isinstance(care, dict):
                care["scheduled_for"] = followup_at.strftime("%H:%M")

            prompt_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            prompt = (
                "Send this LINE care reminder again because the user tapped "
                "Remind me later. Return exactly the LINE_RICH payload below, including the literal "
                "LINE_RICH: prefix, and no extra text. Do not return bare JSON.\n\n"
                f"LINE_RICH:{prompt_payload}"
            )
            from cron.jobs import create_job

            create_job(
                prompt=prompt,
                schedule=followup_at.isoformat(),
                name=f"line-care-followup-{reminder.get('routine_id') or 'care'}",
                repeat=1,
                deliver=f"line:{source.chat_id}",
                enabled_toolsets=[],
            )
            return followup_at
        except Exception:
            logger.warning("[line] failed to schedule care follow-up reminder", exc_info=True)
            return None

    def _effective_recent_context_allowed_chats(self) -> set[str]:
        configured = {chat_id for chat_id in self.recent_context_allowed_chats if chat_id}
        if configured:
            return configured
        return {chat_id for chat_id in self.allowed_chats if chat_id and chat_id != "*"}

    def _recent_context_group_allowed(self, source: SessionSource) -> bool:
        if not self.recent_context_enabled:
            return False
        if str(source.chat_type or "").lower() != "group":
            return False
        chat_id = str(source.chat_id or "")
        if not chat_id:
            return False
        allowed_chats = self._effective_recent_context_allowed_chats()
        return "*" in allowed_chats or chat_id in allowed_chats

    def _recent_context_operator_allowed(self, source: SessionSource) -> bool:
        if not self.recent_context_enabled:
            return False
        if str(source.chat_type or "").lower() != "dm":
            return False
        user_id = str(source.user_id or "")
        if not user_id:
            return False
        return "*" in self.recent_context_operator_users or user_id in self.recent_context_operator_users

    def _operator_text_requests_recent_group_context(self, text: str) -> bool:
        value = str(text or "").casefold()
        if not value:
            return False
        needles = (
            "กลุ่ม",
            "ไลน์กลุ่ม",
            "ในกรุ๊ป",
            "กรุ๊ป",
            "รูป",
            "ภาพ",
            "ข้างบน",
            "เมื่อกี้",
            "ที่คุณแม่ส่ง",
            "ที่คุณพ่อส่ง",
            "group",
            "recent",
            "above",
            "sent",
        )
        return any(needle.casefold() in value for needle in needles)

    def _operator_text_requests_recent_group_image(self, text: str) -> bool:
        value = str(text or "").casefold()
        image_needles = ("รูป", "ภาพ", "image", "photo", "picture")
        group_needles = ("กลุ่ม", "ไลน์กลุ่ม", "กรุ๊ป", "group", "ข้างบน", "เมื่อกี้")
        return any(needle in value for needle in image_needles) and any(
            needle in value for needle in group_needles
        )

    def _remember_recent_group_context(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        message_type: str,
        text: str = "",
        message_id: str = "",
    ) -> None:
        if not self._recent_context_group_allowed(source):
            return
        try:
            self.recent_context_store.record(
                chat_id=str(source.chat_id or ""),
                user_id=str(source.user_id or ""),
                sender_name=str(source.user_name or "LINE user"),
                message_id=str(message_id or (event.get("message") or {}).get("id") or ""),
                webhook_event_id=str(event.get("webhookEventId") or ""),
                message_type=str(message_type or ""),
                text=text,
            )
        except Exception:
            logger.debug("[line] failed to record recent group context", exc_info=True)

    def _recent_context_rows_for_group(self, source: SessionSource) -> List[Dict[str, Any]]:
        if not self._recent_context_group_allowed(source):
            return []
        try:
            return self.recent_context_store.recent_for_group(
                str(source.chat_id or ""),
                limit=self.recent_context_limit,
            )
        except Exception:
            logger.debug("[line] failed to read recent group context", exc_info=True)
            return []

    def _recent_context_rows_for_operator(self, source: SessionSource, text: str) -> List[Dict[str, Any]]:
        if not self._recent_context_operator_allowed(source):
            return []
        if not self._operator_text_requests_recent_group_context(text):
            return []
        chat_ids = [chat_id for chat_id in self._effective_recent_context_allowed_chats() if chat_id != "*"]
        if not chat_ids:
            return []
        try:
            return self.recent_context_store.recent_for_groups(
                chat_ids,
                limit=self.recent_context_limit,
            )
        except Exception:
            logger.debug("[line] failed to read operator recent group context", exc_info=True)
            return []

    def _recent_context_prompt_from_rows(self, rows: List[Dict[str, Any]]) -> Optional[str]:
        if not rows:
            return None
        lines = [
            "Recent approved LINE group context (ephemeral; use only if relevant to this turn; do not imply access to unrelated chats):"
        ]
        for row in rows[-self.recent_context_limit:]:
            try:
                ts = datetime.fromtimestamp(float(row.get("occurred_at") or 0)).astimezone().strftime("%H:%M")
            except Exception:
                ts = "recent"
            sender = str(row.get("sender_name") or "LINE user").strip() or "LINE user"
            message_type = str(row.get("message_type") or "").strip().lower()
            text = str(row.get("text") or "").strip()
            if message_type == "text" and text:
                summary = f"{sender}: {text}"
            elif message_type == "image":
                summary = f"{sender} sent an image"
            elif message_type:
                summary = f"{sender} sent a {message_type} message"
            else:
                summary = f"{sender} sent a message"
            lines.append(f"- [{ts}] {summary}")
        return "\n".join(lines)

    def _recent_context_prompt_for_group(self, source: SessionSource) -> Optional[str]:
        return self._recent_context_prompt_from_rows(self._recent_context_rows_for_group(source))

    async def _message_event_with_operator_recent_context(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        text: str,
        message_id: str,
    ) -> Optional[MessageEvent]:
        rows = self._recent_context_rows_for_operator(source, text)
        if not rows:
            return None
        prompt = self._recent_context_prompt_from_rows(rows)
        media_urls: List[str] = []
        media_types: List[str] = []
        linked_media: List[Dict[str, str]] = []
        if self._operator_text_requests_recent_group_image(text):
            image_rows = [
                row for row in rows
                if str(row.get("message_type") or "").lower() == "image" and str(row.get("message_id") or "")
            ][-_MAX_PENDING_GROUP_MEDIA_ITEMS:]
            for row in image_rows:
                image_message_id = str(row.get("message_id") or "")
                media = await self._download_line_media(image_message_id, line_message_type="image")
                if media is None:
                    continue
                path, content_type = media
                media_urls.append(path)
                media_types.append(content_type)
                linked_media.append({"messageId": image_message_id, "type": "image"})

        raw = copy.deepcopy(event)
        if linked_media:
            raw["linked_line_recent_context_media"] = linked_media
        return MessageEvent(
            text=text,
            message_type=MessageType.PHOTO if media_urls else MessageType.TEXT,
            source=source,
            raw_message=raw,
            message_id=message_id,
            media_urls=media_urls,
            media_types=media_types,
            channel_prompt=prompt,
        )

    def _pending_group_media_key(self, source: SessionSource) -> str:
        if str(source.chat_type or "").lower() != "group":
            return ""
        return str(source.chat_id or "")

    def _prune_pending_group_media(self, now: Optional[float] = None) -> None:
        current = time.time() if now is None else float(now)
        for key, entries in list(self._pending_group_media.items()):
            kept = [
                entry for entry in entries
                if current - float(entry.get("stored_at") or 0) <= _PENDING_GROUP_MEDIA_TTL_SECONDS
            ]
            if kept:
                self._pending_group_media[key] = kept[-_MAX_PENDING_GROUP_MEDIA_ITEMS:]
            else:
                self._pending_group_media.pop(key, None)

    def _remember_pending_group_media(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        message_id: str,
        line_message_type: str,
    ) -> None:
        key = self._pending_group_media_key(source)
        if not key or not message_id:
            return
        self._prune_pending_group_media()
        entries = self._pending_group_media.setdefault(key, [])
        entries.append(
            {
                "message_id": str(message_id),
                "line_message_type": str(line_message_type or ""),
                "stored_at": time.time(),
                "event": copy.deepcopy(event),
            }
        )
        self._pending_group_media[key] = entries[-_MAX_PENDING_GROUP_MEDIA_ITEMS:]

    def _take_pending_group_media(
        self,
        source: SessionSource,
        *,
        line_message_type: str,
    ) -> List[Dict[str, Any]]:
        self._prune_pending_group_media()
        key = self._pending_group_media_key(source)
        if not key:
            return []
        entries = self._pending_group_media.get(key) or []
        matching = [
            entry for entry in entries
            if str(entry.get("line_message_type") or "") == str(line_message_type or "")
        ]
        if matching:
            self._pending_group_media.pop(key, None)
        return matching

    async def _message_event_with_pending_group_image(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        text: str,
        message_id: str,
    ) -> Optional[MessageEvent]:
        if not self._group_message_requires_mention(source):
            return None
        pending_items = self._take_pending_group_media(source, line_message_type="image")
        if not pending_items:
            return None
        media_urls: List[str] = []
        media_types: List[str] = []
        linked_media: List[Dict[str, str]] = []
        for pending in pending_items:
            image_message_id = str(pending.get("message_id") or "")
            if not image_message_id:
                continue
            media = await self._download_line_media(image_message_id, line_message_type="image")
            if media is None:
                continue
            path, content_type = media
            media_urls.append(path)
            media_types.append(content_type)
            linked_media.append({"messageId": image_message_id, "type": "image"})
        if not media_urls:
            return None
        raw = copy.deepcopy(event)
        raw["linked_line_media"] = linked_media
        return MessageEvent(
            text=text,
            message_type=MessageType.PHOTO,
            source=source,
            raw_message=raw,
            message_id=message_id,
            media_urls=media_urls,
            media_types=media_types,
            channel_prompt=self._recent_context_prompt_for_group(source),
        )

    async def _handle_image_message(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        message_id: str,
    ) -> None:
        if not message_id:
            await self._maybe_reply_image_download_failed(event)
            return

        media = await self._download_line_media(message_id, line_message_type="image")
        if media is None:
            await self._maybe_reply_image_download_failed(event)
            return

        path, content_type = media
        msg_event = MessageEvent(
            text="",
            message_type=MessageType.PHOTO,
            source=source,
            raw_message=event,
            message_id=message_id,
            media_urls=[path],
            media_types=[content_type],
        )
        await self.handle_message(msg_event)

    async def _handle_audio_message(
        self,
        event: Dict[str, Any],
        source: SessionSource,
        *,
        message_id: str,
    ) -> None:
        if not message_id:
            await self._maybe_reply_audio_download_failed(event)
            return

        media = await self._download_line_media(message_id, line_message_type="audio")
        if media is None:
            await self._maybe_reply_audio_download_failed(event)
            return

        path, content_type = media
        msg_event = MessageEvent(
            text="",
            message_type=MessageType.VOICE,
            source=source,
            raw_message=event,
            message_id=message_id,
            media_urls=[path],
            media_types=[content_type],
        )
        await self.handle_message(msg_event)

    async def _download_line_media(
        self,
        message_id: str,
        *,
        line_message_type: str,
    ) -> Optional[Tuple[str, str]]:
        """Download media bytes from LINE and cache supported Hermes media."""
        if self._client_session is None:
            logger.warning("[line] cannot download media: client session is not connected")
            return None

        url = _LINE_CONTENT_API_TEMPLATE.format(message_id=message_id)
        try:
            async with self._client_session.get(
                url,
                headers=_line_bearer_headers(self.channel_access_token),
            ) as response:
                status = int(getattr(response, "status", 0) or 0)
                headers = getattr(response, "headers", {}) or {}
                content_type = _content_type_without_params(str(headers.get("Content-Type", "")))
                if status >= 400:
                    body = ""
                    try:
                        body = (await response.text())[:300]
                    except Exception:
                        body = ""
                    logger.warning(
                        "[line] media download failed message=%s status=%s body=%s",
                        _redacted_id(message_id),
                        status,
                        body,
                    )
                    return None

                data = await self._read_limited_response(response)
        except ValueError as exc:
            logger.warning("[line] media download rejected message=%s: %s", _redacted_id(message_id), exc)
            return None
        except asyncio.TimeoutError:
            logger.warning("[line] media download timed out message=%s", _redacted_id(message_id))
            return None
        except Exception as exc:
            logger.warning("[line] media download failed message=%s: %s", _redacted_id(message_id), exc)
            return None

        if line_message_type == "image":
            ext = _extension_for_image(data, content_type)
            try:
                path = cache_image_from_bytes(data, ext)
            except ValueError as exc:
                logger.warning("[line] rejected non-image media message=%s: %s", _redacted_id(message_id), exc)
                return None
            mime = content_type if content_type.startswith("image/") else _image_mime_for_extension(ext)
            return path, mime

        if line_message_type == "audio":
            ext = _extension_for_audio(data, content_type)
            if not ext:
                logger.warning(
                    "[line] rejected non-audio media message=%s content_type=%s",
                    _redacted_id(message_id),
                    content_type,
                )
                return None
            path = cache_audio_from_bytes(data, ext)
            mime = content_type if content_type.startswith("audio/") else _audio_mime_for_extension(ext)
            return path, mime

        logger.debug("[line] unsupported downloadable LINE media type: %s", line_message_type)
        return None

    async def _read_limited_response(self, response: Any) -> bytes:
        headers = getattr(response, "headers", {}) or {}
        declared_size = str(headers.get("Content-Length", "") or "").strip()
        if declared_size:
            try:
                if int(declared_size) > self.media_max_bytes:
                    raise ValueError(f"media exceeds size limit ({declared_size} > {self.media_max_bytes})")
            except ValueError as exc:
                if "exceeds" in str(exc):
                    raise

        content = getattr(response, "content", None)
        if content is not None and hasattr(content, "iter_chunked"):
            total = 0
            chunks: List[bytes] = []
            async for chunk in content.iter_chunked(64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.media_max_bytes:
                    raise ValueError(f"media exceeds size limit ({total} > {self.media_max_bytes})")
                chunks.append(bytes(chunk))
            return b"".join(chunks)

        data = await response.read()
        if len(data) > self.media_max_bytes:
            raise ValueError(f"media exceeds size limit ({len(data)} > {self.media_max_bytes})")
        return data

    async def _enrich_source_profile(self, source: SessionSource, source_data: Dict[str, Any]) -> None:
        """Populate source.user_name with the LINE display name when available."""
        user_id = str(source_data.get("userId") or "").strip()
        if not user_id or self._client_session is None:
            return
        source_type = str(source_data.get("type") or "").strip()
        display_name = await self._line_display_name(
            source_type=source_type,
            chat_id=str(source.chat_id or ""),
            user_id=user_id,
        )
        if display_name:
            source.user_name = display_name

    async def _line_display_name(self, *, source_type: str, chat_id: str, user_id: str) -> str:
        cache_key = f"{source_type}:{chat_id}:{user_id}"
        now = time.time()
        cached = self._profile_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        if source_type == "user":
            url = _LINE_PROFILE_API_TEMPLATE.format(user_id=user_id)
        elif source_type == "group":
            url = _LINE_GROUP_MEMBER_PROFILE_API_TEMPLATE.format(group_id=chat_id, user_id=user_id)
        elif source_type == "room":
            url = _LINE_ROOM_MEMBER_PROFILE_API_TEMPLATE.format(room_id=chat_id, user_id=user_id)
        else:
            return ""

        try:
            async with self._client_session.get(
                url,
                headers=_line_bearer_headers(self.channel_access_token),
            ) as response:
                status = int(getattr(response, "status", 0) or 0)
                if status >= 400:
                    logger.debug(
                        "[line] profile lookup failed source=%s chat=%s user=%s status=%s",
                        source_type,
                        _redacted_id(chat_id),
                        _redacted_id(user_id),
                        status,
                    )
                    return ""
                body = await response.json(content_type=None)
        except Exception as exc:
            logger.debug(
                "[line] profile lookup failed source=%s chat=%s user=%s: %s",
                source_type,
                _redacted_id(chat_id),
                _redacted_id(user_id),
                exc,
            )
            return ""

        display_name = str((body or {}).get("displayName") or "").strip()
        if display_name:
            self._profile_cache[cache_key] = (now + _LINE_PROFILE_CACHE_TTL_SECONDS, display_name)
            while len(self._profile_cache) > 1024:
                self._profile_cache.pop(next(iter(self._profile_cache)))
        return display_name

    def _group_message_requires_mention(self, source: SessionSource) -> bool:
        if str(source.chat_type or "").lower() != "group":
            return False
        # respond_in_groups_when_relevant is a higher-level idea. The LINE
        # adapter cannot infer relevance safely, so false means "mention-only".
        return bool(self.require_mention_in_groups or not self.respond_in_groups_when_relevant)

    def _ignore_unmentioned_group_message(self, source: SessionSource) -> None:
        logger.debug(
            "[line] ignored unmentioned group message chat=%s user=%s",
            _redacted_id(source.chat_id or ""),
            _redacted_id(source.user_id or ""),
        )

    def _line_event_mentions_bot(self, event: Dict[str, Any]) -> bool:
        message = event.get("message") or {}
        if not isinstance(message, dict):
            return False
        text = str(message.get("text") or "")
        mention = message.get("mention") or {}
        mentionees = mention.get("mentionees") if isinstance(mention, dict) else None
        if isinstance(mentionees, list):
            for mentionee in mentionees:
                if not isinstance(mentionee, dict):
                    continue
                if mentionee.get("isSelf") is True:
                    return True
                mentioned_user = str(mentionee.get("userId") or "").strip()
                if self.bot_user_id and mentioned_user == self.bot_user_id:
                    return True
                try:
                    index = int(mentionee.get("index"))
                    length = int(mentionee.get("length"))
                except (TypeError, ValueError):
                    continue
                if index < 0 or length <= 0:
                    continue
                fragment = text[index:index + length].strip().lstrip("@").casefold()
                if fragment in self.mention_names:
                    return True
        return self._text_mentions_bot(text)

    def _text_mentions_bot(self, text: str) -> bool:
        value = str(text or "")
        if not value:
            return False
        for pattern in self.mention_patterns:
            if pattern.search(value):
                return True
        folded = value.casefold()
        return any(f"@{name}" in folded for name in self.mention_names)

    def _source_from_line(self, source_data: Dict[str, Any], *, message_id: str = "") -> Optional[SessionSource]:
        source_type = str(source_data.get("type") or "")
        user_id = str(source_data.get("userId") or "") or None

        if source_type == "user":
            chat_id = user_id
            chat_type = "dm"
            chat_name = "LINE DM"
        elif source_type == "group":
            chat_id = str(source_data.get("groupId") or "") or None
            chat_type = "group"
            chat_name = "LINE group"
        elif source_type == "room":
            chat_id = str(source_data.get("roomId") or "") or None
            chat_type = "group"
            chat_name = "LINE room"
        else:
            return None

        if not chat_id:
            return None

        # LINE can omit userId in some group webhook cases. Hermes auth requires
        # a user_id, so fall back to chat_id rather than emitting an empty source.
        stable_user_id = user_id or chat_id
        return SessionSource(
            platform=Platform("line"),
            chat_id=str(chat_id),
            chat_name=chat_name,
            chat_type=chat_type,
            user_id=str(stable_user_id),
            user_name="LINE user",
            message_id=message_id or None,
        )

    def _adapter_allows(self, source: SessionSource) -> bool:
        chat_allowed = "*" in self.allowed_chats or source.chat_id in self.allowed_chats
        user_allowed = "*" in self.allowed_users or source.user_id in self.allowed_users

        if self.allow_all_users:
            return True
        # User and chat allowlists are independent lanes:
        # - allowed_users approves owner/DM identities;
        # - allowed_chats approves family groups/rooms.
        # Having a group allowlist must not accidentally block an explicitly
        # approved DM user.
        if user_allowed:
            return True
        if chat_allowed:
            return True
        # Closed by default. A family-facing LINE bot should never become public
        # just because an allowlist env var/config key is missing.
        return False

    def _record_pending_approval(self, event: Dict[str, Any], source: SessionSource) -> None:
        """Persist raw LINE IDs locally so the owner can approve later.

        Logs intentionally use redacted IDs only; this profile-local JSONL file is the
        approval queue. It contains LINE user/chat IDs and must stay mode 0600.
        """
        if not self.pending_approvals_path:
            return
        try:
            msg = event.get("message") or {}
            text = str(msg.get("text") or "").strip()
            if len(text) > 160:
                text = text[:157] + "..."
            record = {
                "ts": time.time(),
                "event_type": str(event.get("type") or "unknown"),
                "webhookEventId": str(event.get("webhookEventId") or ""),
                "messageId": str(msg.get("id") or ""),
                "messageType": str(msg.get("type") or ""),
                "chat_type": str(source.chat_type or "unknown"),
                "userId": source.user_id,
                "chatId": source.chat_id,
                "userHash": _redacted_id(source.user_id or ""),
                "chatHash": _redacted_id(source.chat_id or ""),
                "text_preview": text,
            }
            path = Path(self.pending_approvals_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.warning("[line] failed to record pending approval: %s", exc)

    async def _notify_approval_required(self, event: Dict[str, Any], source: SessionSource) -> None:
        if not self.notify_unauthorized or not self.home_channel:
            return
        if self.home_channel == source.chat_id:
            return

        now = time.time()
        key = f"{source.chat_id}:{source.user_id}:{event.get('type') or ''}"
        last = self._approval_notices.get(key, 0)
        if now - last < max(1, self.unauthorized_notice_ttl_seconds):
            return
        self._approval_notices[key] = now

        msg = event.get("message") or {}
        text = str(msg.get("text") or "").strip()
        if len(text) > 160:
            text = text[:157] + "..."
        event_type = str(event.get("type") or "unknown")
        chat_type = str(source.chat_type or "unknown")
        lines = [
            "ได้รับการติดต่อจาก LINE ที่ยังไม่ได้อนุมัติ จึงยังไม่ตอบกลับค่ะ",
            f"event: {event_type}",
            f"chat_type: {chat_type}",
            f"userId: {source.user_id}",
            f"chatId: {source.chat_id}",
        ]
        if text:
            lines.append(f"ข้อความ: {text}")
        lines.append("ถ้าจะอนุมัติ ให้เพิ่ม userId หรือ chatId นี้ใน allowlist")

        result = await self._push_message(self.home_channel, "\n".join(lines))
        if not result.success:
            logger.warning("[line] failed to notify home channel about unauthorized source: %s", result.error)

    def _verify_signature(self, body: bytes, signature: str) -> bool:
        if not signature or not self.channel_secret:
            return False
        digest = hmac.new(self.channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature.strip())

    def _is_duplicate(self, event: Dict[str, Any]) -> bool:
        self._prune_dedupe()
        event_id = str(event.get("webhookEventId") or "")
        if not event_id:
            msg = event.get("message") or {}
            event_id = str(msg.get("id") or "")
        if not event_id:
            return False
        delivery = event.get("deliveryContext") or {}
        if event_id in self._seen_events:
            logger.debug("[line] dropped duplicate event %s", event_id)
            return True
        if delivery.get("isRedelivery") is True:
            logger.debug("[line] dropped LINE redelivery event %s", event_id)
            self._seen_events[event_id] = time.time()
            return True
        self._seen_events[event_id] = time.time()
        return False

    def _prune_dedupe(self) -> None:
        now = time.time()
        for key, ts in list(self._seen_events.items()):
            if now - ts > _DEDUPE_TTL_SECONDS:
                self._seen_events.pop(key, None)
        while len(self._seen_events) > _MAX_DEDUPE_EVENTS:
            self._seen_events.popitem(last=False)

    def _prune_reply_tokens(self) -> None:
        now = time.time()
        for key, (_, _, stored_at) in list(self._reply_tokens.items()):
            if now - stored_at > _REPLY_TOKEN_TTL_SECONDS:
                self._reply_tokens.pop(key, None)

    def _split_text(self, text: str) -> List[str]:
        limit = max(1, int(self.max_message_length or self.MAX_MESSAGE_LENGTH))
        if len(text) <= limit:
            return [text]
        chunks: List[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            cut = remaining.rfind("\n", 0, limit)
            if cut < limit // 2:
                cut = remaining.rfind(" ", 0, limit)
            if cut < limit // 2:
                cut = limit
            chunks.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        return [c for c in chunks if c]

    def _fit_reply_chunks(self, chunks: List[str]) -> List[str]:
        """Fit text chunks into LINE's single reply request without using push.

        LINE reply requests allow at most five messages.  When a model response
        is longer than that, send the first four chunks plus a visibly truncated
        fifth chunk instead of consuming push quota for overflow.
        """
        max_messages = _MAX_LINE_MESSAGES_PER_REQUEST
        if len(chunks) <= max_messages:
            return list(chunks)

        fitted = list(chunks[:max_messages])
        notice = "\n\n[truncated to fit LINE reply. Ask me to continue if needed.]"
        limit = max(1, int(self.max_message_length or self.MAX_MESSAGE_LENGTH))
        room = max(0, limit - len(notice))
        prefix = fitted[-1][:room].rstrip() if room else ""
        fitted[-1] = f"{prefix}{notice}" if prefix else notice.strip()[:limit]
        return fitted

    def _fit_reply_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fit rich/object messages into one LINE reply request without push overflow."""
        max_messages = _MAX_LINE_MESSAGES_PER_REQUEST
        if len(messages) <= max_messages:
            return list(messages)
        fitted = list(messages[:max_messages])
        fitted[-1] = _line_text_message("[truncated to fit LINE reply. Ask me to continue if needed.]")
        return fitted

    async def _reply_message_objects(self, reply_token: str, messages: List[Dict[str, Any]]) -> SendResult:
        payload = {
            "replyToken": reply_token,
            "messages": messages[:_MAX_LINE_MESSAGES_PER_REQUEST],
        }
        return await self._post_json(_LINE_REPLY_API, payload)

    async def _push_message_objects(self, chat_id: str, messages: List[Dict[str, Any]]) -> SendResult:
        payload = {"to": str(chat_id), "messages": messages[:_MAX_LINE_MESSAGES_PER_REQUEST]}
        return await self._post_json(_LINE_PUSH_API, payload)

    async def _send_message_objects(
        self,
        chat_id: str,
        messages: List[Dict[str, Any]],
        *,
        reply_to: Optional[str] = None,
    ) -> SendResult:
        remaining = list(messages)
        first_message_id: Optional[str] = None
        raw_responses: List[Any] = []

        token_entry = self._reply_tokens.pop(reply_to, None) if reply_to else None
        if reply_to:
            if not token_entry:
                return SendResult(
                    success=False,
                    error="LINE reply token unavailable; not falling back to push quota",
                    retryable=False,
                )
            reply_token, token_chat_id, stored_at = token_entry
            if token_chat_id != str(chat_id) or time.time() - stored_at > _REPLY_TOKEN_TTL_SECONDS:
                return SendResult(
                    success=False,
                    error="LINE reply token stale or mismatched; not falling back to push quota",
                    retryable=False,
                )
            reply_messages = self._fit_reply_messages(remaining)
            result = await self._reply_message_objects(reply_token, reply_messages)
            raw_responses.append(result.raw_response)
            if result.success:
                return SendResult(
                    success=True,
                    message_id=result.message_id or "line-reply",
                    raw_response=raw_responses,
                )
            return SendResult(
                success=False,
                message_id=result.message_id,
                error=f"LINE reply failed; not falling back to push quota: {result.error or 'unknown'}",
                raw_response=raw_responses,
                retryable=False,
            )

        for start in range(0, len(remaining), _MAX_LINE_MESSAGES_PER_REQUEST):
            batch = remaining[start:start + _MAX_LINE_MESSAGES_PER_REQUEST]
            result = await self._push_message_objects(chat_id, batch)
            raw_responses.append(result.raw_response)
            if not result.success:
                return SendResult(
                    success=False,
                    message_id=first_message_id,
                    error=result.error,
                    raw_response=raw_responses,
                    retryable=result.retryable,
                )
            if not first_message_id:
                first_message_id = result.message_id

        return SendResult(
            success=True,
            message_id=first_message_id,
            raw_response=raw_responses,
        )

    async def _reply_with_token(self, reply_token: str, chunks: List[str]) -> SendResult:
        return await self._reply_message_objects(
            reply_token,
            [_line_text_message(chunk) for chunk in chunks[:_MAX_LINE_MESSAGES_PER_REQUEST]],
        )

    async def _push_message(self, chat_id: str, text: str) -> SendResult:
        return await self._push_message_objects(str(chat_id), [_line_text_message(text)])

    async def _post_json(self, url: str, payload: Dict[str, Any], *, expect_body: bool = True) -> SendResult:
        if self._client_session is None:
            return SendResult(success=False, error="LINE client session is not connected", retryable=True)

        try:
            async with self._client_session.post(
                url,
                headers=_line_auth_headers(self.channel_access_token),
                json=payload,
            ) as response:
                body_text = await response.text()
                raw: Any = None
                if body_text:
                    try:
                        raw = json.loads(body_text)
                    except Exception:
                        raw = {"body": body_text[:1000]}
                elif expect_body:
                    raw = {}

                if response.status >= 400:
                    detail = ""
                    if isinstance(raw, dict):
                        detail = str(raw.get("message") or raw.get("error") or "").strip()
                    if response.status == 429:
                        if url == _LINE_PUSH_API:
                            error = "LINE push quota/rate limit HTTP 429"
                        else:
                            error = "LINE API HTTP 429 rate limited"
                        if detail:
                            error = f"{error}: {detail}"
                        return SendResult(
                            success=False,
                            error=error,
                            raw_response=raw,
                            retryable=False,
                        )
                    retryable = response.status >= 500
                    error = f"LINE API HTTP {response.status}"
                    if detail:
                        error = f"{error}: {detail}"
                    return SendResult(
                        success=False,
                        error=error,
                        raw_response=raw,
                        retryable=retryable,
                    )

                message_id = None
                if isinstance(raw, dict):
                    sent = raw.get("sentMessages") or []
                    if sent and isinstance(sent[0], dict):
                        message_id = sent[0].get("id")
                return SendResult(success=True, message_id=message_id, raw_response=raw)
        except asyncio.TimeoutError:
            return SendResult(success=False, error="LINE API timeout", retryable=True)
        except Exception as exc:
            return SendResult(success=False, error=f"LINE API error: {exc}", retryable=True)

    async def _maybe_reply_unsupported(self, event: Dict[str, Any], text: str) -> None:
        reply_token = str(event.get("replyToken") or "")
        if not reply_token:
            return
        try:
            await self._reply_with_token(reply_token, [text])
        except Exception:
            logger.debug("[line] unsupported-message notice failed", exc_info=True)

    async def _maybe_reply_image_download_failed(self, event: Dict[str, Any]) -> None:
        await self._maybe_reply_unsupported(
            event,
            "ขอโทษค่ะ เปิดรูปนี้ไม่ได้ ลองส่งรูปใหม่อีกครั้งได้ไหมคะ",
        )

    async def _maybe_reply_audio_download_failed(self, event: Dict[str, Any]) -> None:
        await self._maybe_reply_unsupported(
            event,
            "ขอโทษค่ะ ฟังเสียงนี้ไม่ได้ ลองส่งเสียงใหม่หรือพิมพ์เป็นข้อความได้ไหมคะ",
        )


def interactive_setup() -> None:
    """Interactive `hermes gateway setup` flow for LINE."""
    from hermes_cli.setup import (
        get_env_value,
        print_info,
        print_success,
        print_warning,
        prompt,
        prompt_yes_no,
        save_env_value,
    )

    print_info("Connect Hermes to LINE Messaging API.")
    print_info("Create a LINE Messaging API channel, then set its webhook to your public HTTPS /line/webhook URL.")
    print()

    existing_secret = get_env_value("LINE_CHANNEL_SECRET")
    if existing_secret:
        print_info("LINE: already has a channel secret configured")
        if not prompt_yes_no("Reconfigure LINE?", False):
            return

    secret = prompt("LINE channel secret", password=True)
    if not secret:
        print_warning("LINE channel secret is required — skipping LINE setup")
        return
    save_env_value("LINE_CHANNEL_SECRET", secret.strip())

    token = prompt("LINE channel access token", password=True)
    if not token:
        print_warning("LINE channel access token is required — skipping LINE setup")
        return
    save_env_value("LINE_CHANNEL_ACCESS_TOKEN", token.strip())
    save_env_value("LINE_ENABLED", "false")

    port = prompt("Local webhook port", default=get_env_value("LINE_PORT") or str(_DEFAULT_PORT))
    if port:
        try:
            save_env_value("LINE_PORT", str(int(port)))
        except ValueError:
            print_warning(f"Invalid port — using default {_DEFAULT_PORT}")

    path = prompt("Webhook path", default=get_env_value("LINE_WEBHOOK_PATH") or _DEFAULT_WEBHOOK_PATH)
    if path:
        save_env_value("LINE_WEBHOOK_PATH", path.strip())

    print()
    print_info("🔒 Access control")
    print_info("Use LINE_ALLOWED_USERS for LINE userIds and LINE_ALLOWED_CHATS for group/room/user destinations.")
    allow_all = prompt_yes_no("Temporarily allow all LINE users?", False)
    save_env_value("LINE_ALLOW_ALL_USERS", "true" if allow_all else "false")
    if allow_all:
        print_warning("⚠️ Open access — lock this down after discovering parent/group LINE IDs.")
    else:
        users = prompt("Allowed LINE userIds (comma-separated, blank for none)", default=get_env_value("LINE_ALLOWED_USERS") or "")
        save_env_value("LINE_ALLOWED_USERS", users.replace(" ", ""))
        chats = prompt(
            "Allowed LINE chat IDs: userId/groupId/roomId (comma-separated, blank for none)",
            default=get_env_value("LINE_ALLOWED_CHATS") or "",
        )
        save_env_value("LINE_ALLOWED_CHATS", chats.replace(" ", ""))

    print()
    print_success("LINE configuration saved to the active profile .env")
    print_info("LINE_ENABLED was left false. When webhook + allowlists are ready, set LINE_ENABLED=true and platforms.line.enabled=true, then restart that profile's gateway.")


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system."""
    ctx.register_platform(
        name="line",
        label="LINE",
        adapter_factory=lambda cfg: LineAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN"],
        install_hint="aiohttp is required (bundled with Hermes in normal installs)",
        setup_fn=interactive_setup,
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="LINE_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
        allowed_users_env="LINE_ALLOWED_USERS",
        allow_all_env="LINE_ALLOW_ALL_USERS",
        max_message_length=LINE_SAFE_BUBBLE_CHARS,
        pii_safe=True,
        emoji="💚",
        allow_update_command=True,
        platform_hint=(
            "You are chatting via LINE. This adapter supports LINE text, inbound images, and inbound voice/audio. "
            "Keep replies short, warm, Thai-first when users write Thai, and avoid heavy markdown. "
            "For video and PDF/file messages, ask users to resend or describe the content until those media paths are enabled."
        ),
    )

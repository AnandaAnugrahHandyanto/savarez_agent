"""Drain Ockham notification outbox records and deliver them via Hermes.

Ockham writes structured notification records to ~/.config/ockham/outbox.db.
Hermes owns transport and quiet-hours delivery policy.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class OckhamNotification:
    id: str
    type: str
    title: str
    body: str
    priority: int
    status: str
    created_at: int
    deliver_after: int
    sent_at: int
    dedup_key: str
    coalesce_key: str


def _default_user_config_root() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".config"


def _ockham_dir() -> Path:
    return Path(os.getenv("OCKHAM_CONFIG_DIR", _default_user_config_root() / "ockham")).expanduser()


def outbox_path() -> Path:
    return Path(os.getenv("OCKHAM_OUTBOX_PATH", _ockham_dir() / "outbox.db")).expanduser()


def config_path() -> Path:
    return Path(os.getenv("OCKHAM_CONFIG_PATH", _ockham_dir() / "ockham.yaml")).expanduser()


def _load_notify_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data.get("notify", {}) or {}


def _next_quiet_end(now: datetime, start: str, end: str) -> Optional[datetime]:
    try:
        sh, sm = map(int, start.split(":", 1))
        eh, em = map(int, end.split(":", 1))
    except Exception:
        return None
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    cur = now.hour * 60 + now.minute
    overnight = start_min >= end_min
    quiet = (cur >= start_min or cur < end_min) if overnight else (start_min <= cur < end_min)
    if not quiet:
        return None
    end_dt = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    if overnight and cur >= start_min:
        end_dt = end_dt + timedelta(days=1)
    return end_dt


def is_quiet_now(now: Optional[datetime] = None) -> bool:
    notify_cfg = _load_notify_config()
    quiet = notify_cfg.get("quiet_hours") or {}
    start = quiet.get("start")
    end = quiet.get("end")
    if not start or not end:
        return False
    now = now or datetime.now()
    return _next_quiet_end(now, start, end) is not None


def should_send(notification_type: str, now: Optional[datetime] = None) -> bool:
    if notification_type == "alert":
        return True
    return not is_quiet_now(now)


def resolve_delivery_target() -> Optional[str]:
    notify_cfg = _load_notify_config()
    telegram_cfg = notify_cfg.get("telegram") or {}
    if telegram_cfg.get("enabled", True) is False:
        return None
    chat_id = str(telegram_cfg.get("chat_id", "")).strip()
    if chat_id:
        return f"telegram:{chat_id}"
    return "telegram"


def list_ready(now_ts: Optional[int] = None) -> list[OckhamNotification]:
    path = outbox_path()
    if not path.exists():
        return []
    now_ts = int(now_ts if now_ts is not None else datetime.now().timestamp())
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
            SELECT id, type, title, body, priority, status, created_at,
                   deliver_after, sent_at, dedup_key, coalesce_key
            FROM outbox
            WHERE status = 'pending' AND deliver_after <= ?
            ORDER BY priority DESC, created_at ASC, id ASC
            """,
            (now_ts,),
        ).fetchall()
        return [OckhamNotification(*row) for row in rows]
    finally:
        conn.close()


def mark_sent(notification_id: str, sent_at: Optional[int] = None) -> None:
    path = outbox_path()
    if not path.exists():
        return
    sent_at = int(sent_at if sent_at is not None else datetime.now().timestamp())
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE outbox SET status = 'sent', sent_at = ? WHERE id = ?",
            (sent_at, notification_id),
        )
        conn.commit()
    finally:
        conn.close()


def render_message(n: OckhamNotification) -> str:
    title = (n.title or "").strip()
    body = (n.body or "").strip()
    if title and body:
        return f"{title}\n\n{body}"
    return title or body


def drain(deliver_fn, now: Optional[datetime] = None) -> tuple[int, list[str]]:
    """Deliver ready Ockham notifications.

    Args:
        deliver_fn: callable(notification, target, content) -> Optional[str]
            Returns None on success, or an error string on failure.
        now: optional datetime override for tests.

    Returns:
        (delivered_count, error_messages)
    """
    now = now or datetime.now()
    target = resolve_delivery_target()
    if not target:
        return 0, []

    delivered = 0
    errors: list[str] = []
    for n in list_ready(int(now.timestamp())):
        if not should_send(n.type, now):
            continue
        content = render_message(n)
        err = deliver_fn(n, target, content)
        if err:
            errors.append(err)
            continue
        mark_sent(n.id, int(now.timestamp()))
        delivered += 1
    return delivered, errors

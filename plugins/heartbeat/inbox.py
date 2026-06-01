"""Durable, profile-scoped Heartbeat inbox."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from hermes_constants import get_hermes_home


def inbox_path() -> Path:
    return get_hermes_home() / "heartbeat" / "inbox.db"


class HeartbeatInbox:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or inbox_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    started_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    trigger TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    reason TEXT,
                    context_digest TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    recommended_action TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    notified_at INTEGER,
                    last_injected_at INTEGER,
                    injection_count INTEGER NOT NULL DEFAULT 0,
                    acknowledged_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_heartbeat_findings_active
                    ON findings(expires_at, acknowledged_at, created_at);
                CREATE INDEX IF NOT EXISTS idx_heartbeat_findings_fingerprint
                    ON findings(fingerprint, created_at);
                CREATE TABLE IF NOT EXISTS deliveries (
                    id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    attempted_at INTEGER NOT NULL,
                    delivered_at INTEGER,
                    targets_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                """
            )

    def start_run(self, trigger: str) -> str:
        run_id = f"hbr_{uuid.uuid4().hex}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs(id, started_at, trigger, status) VALUES (?, ?, ?, ?)",
                (run_id, int(time.time()), trigger, "running"),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        decision: str = "",
        reason: str = "",
        context_digest: str = "",
        error: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs SET completed_at = ?, status = ?, decision = ?,
                    reason = ?, context_digest = ?, error = ? WHERE id = ?
                """,
                (int(time.time()), status, decision, reason, context_digest, error, run_id),
            )

    def add_finding(
        self,
        run_id: str,
        *,
        fingerprint: str,
        priority: str,
        summary: str,
        recommended_action: str,
        ttl_hours: int,
    ) -> Dict[str, Any]:
        now = int(time.time())
        finding_id = f"hb_{uuid.uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO findings(
                    id, run_id, fingerprint, priority, summary,
                    recommended_action, status, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending_delivery', ?, ?)
                """,
                (
                    finding_id,
                    run_id,
                    fingerprint,
                    priority,
                    summary,
                    recommended_action,
                    now,
                    now + int(ttl_hours) * 3600,
                ),
            )
        return self.get_finding(finding_id) or {}

    def get_finding(self, finding_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        return dict(row) if row else None

    def active_findings(self, limit: int = 20) -> List[Dict[str, Any]]:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                "UPDATE findings SET status = 'expired' "
                "WHERE expires_at <= ? AND status != 'expired'",
                (now,),
            )
            rows = conn.execute(
                """
                SELECT * FROM findings
                WHERE expires_at > ? AND acknowledged_at IS NULL
                ORDER BY
                    CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    created_at DESC
                LIMIT ?
                """,
                (now, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def has_recent_fingerprint(self, fingerprint: str, cooldown_minutes: int) -> bool:
        since = int(time.time()) - int(cooldown_minutes) * 60
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM findings WHERE fingerprint = ? AND created_at >= ? LIMIT 1",
                (fingerprint, since),
            ).fetchone()
        return row is not None

    def notifications_today(self) -> int:
        now = int(time.time())
        day_start = now - (now % 86400)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM findings WHERE notified_at >= ?",
                (day_start,),
            ).fetchone()
        return int(row[0]) if row else 0

    def record_delivery(
        self,
        finding_id: str,
        *,
        idempotency_key: str,
        targets: Iterable[Dict[str, Any]],
        delivered: bool,
        result: Dict[str, Any],
    ) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO deliveries(
                    id, finding_id, idempotency_key, attempted_at, delivered_at,
                    targets_json, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"hbd_{uuid.uuid4().hex}",
                    finding_id,
                    idempotency_key,
                    now,
                    now if delivered else None,
                    json.dumps(list(targets), sort_keys=True),
                    json.dumps(result, sort_keys=True, default=str),
                ),
            )
            conn.execute(
                "UPDATE findings SET status = ?, notified_at = ? WHERE id = ?",
                ("notified" if delivered else "delivery_failed", now if delivered else None, finding_id),
            )

    def recent_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, fingerprint, priority, summary, notified_at, status
                FROM findings WHERE notified_at IS NOT NULL
                ORDER BY notified_at DESC LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_injected(self, finding_ids: Iterable[str]) -> None:
        ids = [item for item in finding_ids if item]
        if not ids:
            return
        now = int(time.time())
        with self._connect() as conn:
            conn.executemany(
                """
                UPDATE findings SET last_injected_at = ?,
                    injection_count = injection_count + 1 WHERE id = ?
                """,
                [(now, finding_id) for finding_id in ids],
            )

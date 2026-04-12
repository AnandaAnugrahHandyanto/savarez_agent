"""Execution receipt ledger for delegated work.

Receipts remain JSON artifacts on disk, but this module also indexes them in a
small SQLite ledger so they can be queried and pruned without scanning the
filesystem.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

RECEIPTS_DIR = get_hermes_home() / "artifacts" / "execution-receipts"
INDEX_DB = RECEIPTS_DIR / "index.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_receipts (
    receipt_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    parent_session_id TEXT,
    child_session_id TEXT,
    task_index INTEGER,
    goal TEXT,
    task_spec TEXT,
    status TEXT,
    fallback_reason TEXT,
    execution_envelope_digest TEXT,
    model TEXT,
    api_calls INTEGER,
    duration_seconds REAL,
    execution_path TEXT,
    worker_mode TEXT,
    worker_lease_key TEXT,
    worker_task_id TEXT,
    worker_reused INTEGER DEFAULT 0,
    worker_reuse_count INTEGER DEFAULT 0,
    worker_runtime_id TEXT,
    worker_runtime_kind TEXT,
    worker_runtime_reused INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_execution_receipts_created_at ON execution_receipts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_receipts_parent_session ON execution_receipts(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_execution_receipts_child_session ON execution_receipts(child_session_id);
CREATE INDEX IF NOT EXISTS idx_execution_receipts_status ON execution_receipts(status);
"""


def get_execution_receipts_dir() -> Path:
    path = get_hermes_home() / "artifacts" / "execution-receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_execution_receipts_index_path() -> Path:
    return get_execution_receipts_dir() / "index.sqlite"


def _connect_index() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_execution_receipts_index_path()), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    _ensure_index_columns(conn)
    return conn


def _ensure_index_columns(conn: sqlite3.Connection) -> None:
    expected = {
        "execution_path": "TEXT",
        "worker_mode": "TEXT",
        "worker_lease_key": "TEXT",
        "worker_task_id": "TEXT",
        "worker_reused": "INTEGER DEFAULT 0",
        "worker_reuse_count": "INTEGER DEFAULT 0",
        "worker_runtime_id": "TEXT",
        "worker_runtime_kind": "TEXT",
        "worker_runtime_reused": "INTEGER DEFAULT 0",
    }
    rows = conn.execute("PRAGMA table_info(execution_receipts)").fetchall()
    existing = {row[1] for row in rows}
    for column, ddl in expected.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE execution_receipts ADD COLUMN {column} {ddl}")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _normalize_receipt(receipt: dict[str, Any], now: Optional[float] = None) -> dict[str, Any]:
    now_ts = float(now if now is not None else time.time())
    normalized = dict(receipt)
    normalized.setdefault("receipt_id", normalized.get("child_session_id") or f"receipt-{uuid.uuid4().hex}")
    normalized.setdefault("ledger_created_at", now_ts)
    return normalized


def _index_receipt(conn: sqlite3.Connection, normalized: dict[str, Any], file_path: Path) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO execution_receipts (
            receipt_id, file_path, parent_session_id, child_session_id,
            task_index, goal, task_spec, status, fallback_reason,
            execution_envelope_digest, model, api_calls, duration_seconds,
            execution_path, worker_mode, worker_lease_key, worker_task_id, worker_reused,
            worker_reuse_count, worker_runtime_id, worker_runtime_kind,
            worker_runtime_reused, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(normalized["receipt_id"]),
            str(file_path),
            ((normalized.get("context_package") or {}).get("parent_session_id")),
            normalized.get("child_session_id"),
            normalized.get("task_index"),
            normalized.get("goal"),
            ((normalized.get("execution_envelope") or {}).get("task_spec")),
            normalized.get("status"),
            normalized.get("fallback_reason"),
            normalized.get("execution_envelope_digest"),
            normalized.get("model"),
            normalized.get("api_calls"),
            normalized.get("duration_seconds"),
            normalized.get("execution_path"),
            normalized.get("worker_mode"),
            normalized.get("worker_lease_key"),
            normalized.get("worker_task_id"),
            1 if normalized.get("worker_reused") else 0,
            int(normalized.get("worker_reuse_count", 0) or 0),
            normalized.get("worker_runtime_id"),
            normalized.get("worker_runtime_kind"),
            1 if normalized.get("worker_runtime_reused") else 0,
            normalized.get("ledger_created_at"),
        ),
    )


def persist_execution_receipt(receipt: dict[str, Any]) -> str | None:
    if not isinstance(receipt, dict):
        return None
    normalized = _normalize_receipt(receipt)
    receipt_id = str(normalized["receipt_id"])
    receipts_dir = get_execution_receipts_dir()
    file_path = receipts_dir / f"{receipt_id}.json"
    previous_content: str | None = None
    if file_path.exists():
        try:
            previous_content = file_path.read_text(encoding="utf-8")
        except OSError:
            previous_content = None
    try:
        _atomic_write_text(file_path, json.dumps(normalized, indent=2, ensure_ascii=False, sort_keys=True))
        with _connect_index() as conn:
            _index_receipt(conn, normalized, file_path)
        return str(file_path)
    except Exception as exc:
        try:
            if previous_content is not None:
                _atomic_write_text(file_path, previous_content)
            elif file_path.exists():
                file_path.unlink()
        except OSError as cleanup_exc:
            logger.warning("Execution receipt cleanup failed for %s: %s", file_path, cleanup_exc)
        logger.warning("Execution receipt persist failed for %s: %s", receipt_id, exc)
        return None


def reconcile_execution_receipts(*, delete_missing_rows: bool = True) -> dict[str, Any]:
    receipts_dir = get_execution_receipts_dir()
    indexed = {row["receipt_id"]: row for row in query_execution_receipts(limit=100000)}
    discovered = []
    inserted = []
    parse_errors = []
    for file_path in receipts_dir.glob("*.json"):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            parse_errors.append(str(file_path))
            continue
        normalized = _normalize_receipt(data)
        receipt_id = str(normalized["receipt_id"])
        discovered.append(receipt_id)
        if receipt_id in indexed:
            continue
        with _connect_index() as conn:
            _index_receipt(conn, normalized, file_path)
        inserted.append(receipt_id)

    removed_missing = []
    if delete_missing_rows:
        discovered_set = set(discovered)
        missing_ids = [receipt_id for receipt_id in indexed if receipt_id not in discovered_set]
        if missing_ids:
            placeholders = ",".join("?" * len(missing_ids))
            with _connect_index() as conn:
                conn.execute(f"DELETE FROM execution_receipts WHERE receipt_id IN ({placeholders})", missing_ids)
            removed_missing.extend(missing_ids)

    return {
        "inserted_count": len(inserted),
        "inserted_receipt_ids": inserted,
        "removed_missing_count": len(removed_missing),
        "removed_missing_receipt_ids": removed_missing,
        "parse_errors": parse_errors,
    }


def query_execution_receipts(
    *,
    limit: int = 20,
    status: str | None = None,
    parent_session_id: str | None = None,
    child_session_id: str | None = None,
) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if parent_session_id:
        where.append("parent_session_id = ?")
        params.append(parent_session_id)
    if child_session_id:
        where.append("child_session_id = ?")
        params.append(child_session_id)
    sql = "SELECT * FROM execution_receipts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, int(limit)))
    with _connect_index() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def prune_execution_receipts(*, max_age_seconds: float, keep_failed: bool = True, limit: int = 100) -> dict[str, Any]:
    max_age = float(max_age_seconds)
    if max_age <= 0:
        raise ValueError("max_age_seconds must be > 0")
    cutoff = time.time() - max_age
    where = ["created_at < ?"]
    params: list[Any] = [cutoff]
    if keep_failed:
        where.append("(status IS NULL OR status != 'failed')")
    sql = (
        "SELECT receipt_id, file_path, status FROM execution_receipts "
        f"WHERE {' AND '.join(where)} ORDER BY created_at ASC LIMIT ?"
    )
    params.append(max(1, int(limit)))
    deleted: list[str] = []
    missing_files = 0
    with _connect_index() as conn:
        rows = conn.execute(sql, params).fetchall()
        for row in rows:
            file_path = Path(row["file_path"])
            try:
                if file_path.exists():
                    file_path.unlink()
                else:
                    missing_files += 1
            except OSError:
                continue
            conn.execute("DELETE FROM execution_receipts WHERE receipt_id = ?", (row["receipt_id"],))
            deleted.append(row["receipt_id"])
    return {
        "deleted_count": len(deleted),
        "deleted_receipt_ids": deleted,
        "missing_files": missing_files,
        "cutoff": cutoff,
    }

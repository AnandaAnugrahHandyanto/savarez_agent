"""Session store diagnostics and archive-before-prune maintenance.

This module is intentionally SQLite-only and avoids importing the agent runtime.
It is used by ``hermes sessions doctor`` and ``hermes sessions archive-prune``
so operators can audit and safely shrink large session stores without first
hydrating full conversation state into memory.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def doctor_report(db_path: Path, *, now: float | None = None) -> dict[str, Any]:
    """Return a compact, non-secret operational report for a Hermes state DB."""
    now = time.time() if now is None else now
    db_path = Path(db_path).expanduser()
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    with _connect(db_path) as conn:
        if not _table_exists(conn, "sessions") or not _table_exists(conn, "messages"):
            raise RuntimeError(f"{db_path} is not a Hermes state DB with sessions/messages")

        report: dict[str, Any] = {
            "db_path": str(db_path),
            "db_size_mb": round(db_path.stat().st_size / 1024 / 1024, 2),
            "generated_at": now,
            "counts": {
                "sessions": conn.execute("SELECT count(*) FROM sessions").fetchone()[0],
                "messages": conn.execute("SELECT count(*) FROM messages").fetchone()[0],
            },
            "by_source": _fetch_dicts(
                conn,
                """
                SELECT source,
                       count(*) AS sessions,
                       sum(message_count) AS messages,
                       sum(input_tokens) AS input_tokens,
                       sum(output_tokens) AS output_tokens,
                       round(sum(length(coalesce(system_prompt,''))
                               + length(coalesce(model_config,''))
                               + length(coalesce(handoff_state,''))) / 1024.0 / 1024.0, 2)
                           AS session_text_mb
                FROM sessions
                GROUP BY source
                ORDER BY sessions DESC
                """,
            ),
            "active_by_source": _fetch_dicts(
                conn,
                """
                SELECT source, count(*) AS sessions
                FROM sessions
                WHERE ended_at IS NULL
                GROUP BY source
                ORDER BY sessions DESC
                """,
            ),
            "recent_daily": _fetch_dicts(
                conn,
                """
                SELECT substr(datetime(started_at,'unixepoch','localtime'),1,10) AS day,
                       source,
                       count(*) AS sessions,
                       sum(message_count) AS messages
                FROM sessions
                GROUP BY day, source
                ORDER BY day DESC, sessions DESC
                LIMIT 40
                """,
            ),
            "message_storage_by_role": _fetch_dicts(
                conn,
                """
                SELECT role,
                       count(*) AS messages,
                       round(sum(length(coalesce(content,''))
                               + length(coalesce(tool_calls,''))
                               + length(coalesce(reasoning,''))
                               + length(coalesce(reasoning_details,''))
                               + length(coalesce(codex_reasoning_items,''))
                               + length(coalesce(reasoning_content,''))
                               + length(coalesce(codex_message_items,''))) / 1024.0 / 1024.0, 2)
                           AS text_mb
                FROM messages
                GROUP BY role
                ORDER BY messages DESC
                """,
            ),
        }
        report["risk_flags"] = []
        cron_count = next((r["sessions"] for r in report["by_source"] if r.get("source") == "cron"), 0) or 0
        total = report["counts"]["sessions"] or 1
        if cron_count / total >= 0.5:
            report["risk_flags"].append({
                "code": "CRON_DOMINATES_SESSION_STORE",
                "detail": f"cron sessions are {cron_count}/{total} ({cron_count / total:.1%})",
            })
        if report["db_size_mb"] >= 500:
            report["risk_flags"].append({
                "code": "STATE_DB_LARGE",
                "detail": f"state.db is {report['db_size_mb']} MB",
            })
        return report


def plan_archive_prune(
    db_path: Path,
    *,
    source: str = "cron",
    older_than_days: int = 7,
    now: float | None = None,
) -> dict[str, Any]:
    """Return how many ended sessions would be archive-pruned."""
    now = time.time() if now is None else now
    cutoff = now - older_than_days * 86400
    db_path = Path(db_path).expanduser()
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT count(*) AS sessions,
                   coalesce(sum(message_count), 0) AS messages,
                   min(started_at) AS oldest_started_at,
                   max(started_at) AS newest_started_at
            FROM sessions
            WHERE source = ? AND ended_at IS NOT NULL AND started_at < ?
            """,
            (source, cutoff),
        ).fetchone()
        return {
            "db_path": str(db_path),
            "source": source,
            "older_than_days": older_than_days,
            "cutoff": cutoff,
            "candidate_sessions": int(row["sessions"] or 0),
            "candidate_messages": int(row["messages"] or 0),
            "oldest_started_at": row["oldest_started_at"],
            "newest_started_at": row["newest_started_at"],
        }


def archive_prune(
    db_path: Path,
    archive_path: Path,
    *,
    source: str = "cron",
    older_than_days: int = 7,
    backup_path: Path | None = None,
    vacuum: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Archive ended sessions to another SQLite DB, then prune them.

    The archive is created before any delete. The source DB is modified only
    after the archive row counts match the candidate counts.
    """
    now = time.time() if now is None else now
    db_path = Path(db_path).expanduser()
    archive_path = Path(archive_path).expanduser()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        raise FileExistsError(f"archive already exists: {archive_path}")
    if backup_path:
        backup_path = Path(backup_path).expanduser()
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if backup_path.exists():
            raise FileExistsError(f"backup already exists: {backup_path}")
        shutil.copy2(db_path, backup_path)

    before_size = db_path.stat().st_size
    plan = plan_archive_prune(db_path, source=source, older_than_days=older_than_days, now=now)
    if plan["candidate_sessions"] == 0:
        return {
            **plan,
            "archive_path": str(archive_path),
            "backup_path": str(backup_path) if backup_path else None,
            "archived_sessions": 0,
            "archived_messages": 0,
            "deleted_sessions": 0,
            "deleted_messages": 0,
            "vacuumed": False,
            "before_size_mb": round(before_size / 1024 / 1024, 2),
            "after_size_mb": round(before_size / 1024 / 1024, 2),
        }

    cutoff = plan["cutoff"]
    with _connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("CREATE TEMP TABLE _archive_prune_ids(id TEXT PRIMARY KEY)")
        conn.execute(
            """
            INSERT INTO _archive_prune_ids(id)
            SELECT id FROM sessions
            WHERE source = ? AND ended_at IS NOT NULL AND started_at < ?
            """,
            (source, cutoff),
        )
        selected = conn.execute("SELECT count(*) FROM _archive_prune_ids").fetchone()[0]
        if selected != plan["candidate_sessions"]:
            raise RuntimeError("candidate count changed while preparing archive")

        conn.execute("ATTACH DATABASE ? AS archive", (str(archive_path),))
        session_cols = _column_names(conn, "sessions")
        message_cols = _column_names(conn, "messages")
        session_col_sql = ", ".join(_quote_ident(c) for c in session_cols)
        message_col_sql = ", ".join(_quote_ident(c) for c in message_cols)
        conn.execute("CREATE TABLE archive.sessions AS SELECT * FROM main.sessions WHERE 0")
        conn.execute("CREATE TABLE archive.messages AS SELECT * FROM main.messages WHERE 0")
        conn.execute(
            f"INSERT INTO archive.sessions ({session_col_sql}) "
            f"SELECT {session_col_sql} FROM main.sessions "
            "WHERE id IN (SELECT id FROM _archive_prune_ids)"
        )
        conn.execute(
            f"INSERT INTO archive.messages ({message_col_sql}) "
            f"SELECT {message_col_sql} FROM main.messages "
            "WHERE session_id IN (SELECT id FROM _archive_prune_ids)"
        )
        archived_sessions = conn.execute("SELECT count(*) FROM archive.sessions").fetchone()[0]
        archived_messages = conn.execute("SELECT count(*) FROM archive.messages").fetchone()[0]
        if archived_sessions != plan["candidate_sessions"]:
            raise RuntimeError("archive session count mismatch; refusing to delete")

        with conn:
            conn.execute(
                "UPDATE sessions SET parent_session_id = NULL "
                "WHERE parent_session_id IN (SELECT id FROM _archive_prune_ids)"
            )
            deleted_messages = conn.execute(
                "DELETE FROM messages WHERE session_id IN (SELECT id FROM _archive_prune_ids)"
            ).rowcount
            deleted_sessions = conn.execute(
                "DELETE FROM sessions WHERE id IN (SELECT id FROM _archive_prune_ids)"
            ).rowcount
        conn.execute("DETACH DATABASE archive")
        vacuumed = False
        if vacuum and deleted_sessions:
            conn.execute("VACUUM")
            vacuumed = True

    after_size = db_path.stat().st_size
    return {
        **plan,
        "archive_path": str(archive_path),
        "backup_path": str(backup_path) if backup_path else None,
        "archived_sessions": int(archived_sessions),
        "archived_messages": int(archived_messages),
        "deleted_sessions": int(deleted_sessions),
        "deleted_messages": int(deleted_messages),
        "vacuumed": vacuumed,
        "before_size_mb": round(before_size / 1024 / 1024, 2),
        "after_size_mb": round(after_size / 1024 / 1024, 2),
        "reclaimed_mb": round((before_size - after_size) / 1024 / 1024, 2),
    }


def write_json_report(report: dict[str, Any], output_path: Path) -> None:
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

"""
DB migration runner for the workflow engine.

Mirrors the TS migrate.ts logic exactly:
- Migrations live in engine/db/migrations/*.sql, named NNN_*.sql
- schema_meta.schema_version tracks the current version
- Each migration runs in a transaction; schema_version is upserted after

Usage:
    from engine.db.client import open_db
    from engine.db.migrate import ensure_schema

    with open_db("/path/to/workflow.db") as conn:
        ensure_schema(conn)
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _migration_version(filename: str) -> int:
    match = re.match(r"^(\d+)_", filename)
    if not match:
        raise ValueError(
            f"Migration filename must start with numeric prefix: {filename}"
        )
    return int(match.group(1))


def ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Apply all pending migrations to *conn* in ascending version order.

    Safe to call on a fresh DB (no schema_meta table yet) and on an existing
    DB that is already at the latest version (no-op).
    """
    current_version = 0

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone()

    if row is not None:
        version_row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        if version_row is None:
            raise RuntimeError(
                "schema_meta table exists but schema_version row is missing. "
                "DB may be corrupted."
            )
        try:
            current_version = int(version_row[0])
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected schema_version value: '{version_row[0]}'. "
                "Expected a numeric string."
            ) from exc

    migration_files = sorted(
        [f for f in _MIGRATIONS_DIR.iterdir() if f.suffix == ".sql"],
        key=lambda f: _migration_version(f.name),
    )

    for migration_file in migration_files:
        version = _migration_version(migration_file.name)
        if version <= current_version:
            continue

        sql = migration_file.read_text(encoding="utf-8")

        # Strip PRAGMA statements from the top of 001_init.sql — SQLite
        # doesn't allow PRAGMAs inside transactions and the pragmas are
        # already applied by open_db() via _apply_pragmas().
        sql_for_exec = re.sub(
            r"^\s*PRAGMA\s+\S.*?;\s*", "", sql, flags=re.MULTILINE | re.IGNORECASE
        )

        conn.execute("BEGIN")
        try:
            conn.executescript(sql_for_exec)
            conn.execute(
                "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(version),),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

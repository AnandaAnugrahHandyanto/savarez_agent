#!/usr/bin/env python3
"""Inventory and migrate Hermes Kanban SQLite boards to PostgreSQL.

The script is intentionally conservative: every detected board must have a
chosen readable source, destination counts must not be lower than source
counts, and corrupted active databases are reported instead of silently
turning into empty boards.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DATA_TABLES = (
    "tasks",
    "task_links",
    "task_comments",
    "task_events",
    "task_runs",
    "kanban_notify_subs",
)


@dataclass
class SourceReport:
    path: Path
    role: str
    size: int = 0
    mtime: str | None = None
    exists: bool = False
    tables: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    integrity_check: str | None = None
    error: str | None = None
    candidate: bool = True

    @property
    def ok(self) -> bool:
        return self.exists and self.error is None and self.integrity_check == "ok"


@dataclass
class BoardPlan:
    board_id: str
    board_json: Path | None
    metadata: dict[str, Any]
    active_db: Path
    reports: list[SourceReport]
    selected: SourceReport | None = None
    warnings: list[str] = field(default_factory=list)


def _utc_from_mtime(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def inspect_sqlite(path: Path, role: str, *, candidate: bool = True) -> SourceReport:
    report = SourceReport(path=path, role=role, candidate=candidate)
    report.exists = path.exists()
    if not report.exists:
        return report
    report.size = path.stat().st_size
    report.mtime = _utc_from_mtime(path)
    if not candidate:
        return report
    try:
        with _connect_readonly(path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            report.tables = [str(row["name"]) for row in rows]
            for table in DATA_TABLES:
                if table in report.tables:
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        report.counts[table] = int(count)
                    except Exception as exc:  # pragma: no cover - sqlite error varies
                        report.counts[table] = -1
                        report.error = f"count {table}: {exc}"
            try:
                report.integrity_check = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            except Exception as exc:
                report.error = f"integrity_check: {exc}"
    except Exception as exc:
        report.error = str(exc)
    return report


def _load_board_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_warning": f"could not read board.json: {exc}"}


def _candidate_paths(active_db: Path) -> list[tuple[Path, str, bool]]:
    parent = active_db.parent
    names: list[tuple[Path, str, bool]] = [(active_db, "active", True)]
    for path in sorted(parent.glob(active_db.name + "*")):
        if path == active_db:
            continue
        suffix = path.name[len(active_db.name) :]
        if suffix in {"-wal", "-shm"} or suffix.endswith("-wal") or suffix.endswith("-shm"):
            names.append((path, "sidecar", False))
        elif suffix == ".recovered-preview":
            names.append((path, "recovered-preview", True))
        elif suffix.startswith(".bak"):
            names.append((path, "backup", True))
        elif suffix.startswith(".corrupt-"):
            names.append((path, "corrupt-snapshot", True))
        else:
            names.append((path, "other", False))
    return names


def discover_boards(hermes_home: Path) -> list[BoardPlan]:
    plans: list[BoardPlan] = []
    default_db = hermes_home / "kanban.db"
    plans.append(
        BoardPlan(
            board_id="default",
            board_json=None,
            metadata={"display_name": "Default"},
            active_db=default_db,
            reports=[inspect_sqlite(p, role, candidate=c) for p, role, c in _candidate_paths(default_db)],
        )
    )

    boards_root = hermes_home / "kanban" / "boards"
    if boards_root.exists():
        for board_dir in sorted(p for p in boards_root.iterdir() if p.is_dir()):
            active_db = board_dir / "kanban.db"
            board_json = board_dir / "board.json"
            if not active_db.exists() and not board_json.exists():
                continue
            plans.append(
                BoardPlan(
                    board_id=board_dir.name,
                    board_json=board_json if board_json.exists() else None,
                    metadata=_load_board_json(board_json),
                    active_db=active_db,
                    reports=[
                        inspect_sqlite(p, role, candidate=c)
                        for p, role, c in _candidate_paths(active_db)
                    ],
                )
            )
    return plans


def _total_rows(report: SourceReport) -> int:
    return sum(v for v in report.counts.values() if v > 0)


def select_sources(plans: list[BoardPlan]) -> None:
    for plan in plans:
        candidates = [r for r in plan.reports if r.candidate and r.exists]
        active = next((r for r in candidates if r.role == "active"), None)
        if active and active.ok:
            plan.selected = active
            continue
        if active and active.exists:
            plan.warnings.append(f"active db unusable: {active.error or active.integrity_check}")

        recovered = [r for r in candidates if r.role == "recovered-preview" and r.ok]
        if recovered:
            plan.selected = max(recovered, key=_total_rows)
            continue

        backups = sorted(
            [r for r in candidates if r.role == "backup" and r.ok],
            key=lambda r: (r.mtime or "", _total_rows(r)),
            reverse=True,
        )
        if backups:
            plan.selected = backups[0]
            plan.warnings.append("selected latest integral backup because active db was unusable")
            continue

        partial = [r for r in candidates if r.exists and r.counts.get("tasks", 0) > 0]
        if partial:
            best = max(partial, key=_total_rows)
            plan.warnings.append(
                "row-by-row recovery may be possible, but no integral migration source exists"
            )
            plan.selected = best if best.ok else None
        if plan.selected is None:
            plan.warnings.append("blocking: no usable source; board will not be created empty")


def _manifest(plans: list[BoardPlan], *, migrated: bool, destination: str | None) -> dict[str, Any]:
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "migrated": migrated,
        "destination": destination,
        "boards": [
            {
                "board_id": p.board_id,
                "board_json": str(p.board_json) if p.board_json else None,
                "metadata": p.metadata,
                "active_db": str(p.active_db),
                "selected_source": str(p.selected.path) if p.selected else None,
                "selected_role": p.selected.role if p.selected else None,
                "source_counts": p.selected.counts if p.selected else {},
                "warnings": p.warnings,
                "sources": [
                    {
                        "path": str(r.path),
                        "role": r.role,
                        "exists": r.exists,
                        "candidate": r.candidate,
                        "size": r.size,
                        "mtime": r.mtime,
                        "integrity_check": r.integrity_check,
                        "tables": r.tables,
                        "counts": r.counts,
                        "error": r.error,
                    }
                    for r in p.reports
                ],
            }
            for p in plans
        ],
    }


def _pg_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _ensure_pg_schema(conn: Any) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS boards (
        id TEXT PRIMARY KEY,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        source_path TEXT,
        migrated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS tasks (
        board_id TEXT NOT NULL DEFAULT current_setting('hermes.kanban_board_id', true) REFERENCES boards(id),
        id TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT,
        assignee TEXT,
        status TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        created_by TEXT,
        created_at BIGINT NOT NULL,
        started_at BIGINT,
        completed_at BIGINT,
        workspace_kind TEXT NOT NULL DEFAULT 'scratch',
        workspace_path TEXT,
        branch_name TEXT,
        claim_lock TEXT,
        claim_expires BIGINT,
        tenant TEXT,
        result TEXT,
        idempotency_key TEXT,
        consecutive_failures INTEGER NOT NULL DEFAULT 0,
        worker_pid INTEGER,
        last_failure_error TEXT,
        max_runtime_seconds INTEGER,
        last_heartbeat_at BIGINT,
        current_run_id BIGINT,
        workflow_template_id TEXT,
        current_step_key TEXT,
        skills TEXT,
        model_override TEXT,
        max_retries INTEGER,
        session_id TEXT,
        PRIMARY KEY (board_id, id)
    );
    CREATE TABLE IF NOT EXISTS task_links (
        board_id TEXT NOT NULL DEFAULT current_setting('hermes.kanban_board_id', true) REFERENCES boards(id),
        parent_id TEXT NOT NULL,
        child_id TEXT NOT NULL,
        PRIMARY KEY (board_id, parent_id, child_id)
    );
    CREATE TABLE IF NOT EXISTS task_comments (
        board_id TEXT NOT NULL DEFAULT current_setting('hermes.kanban_board_id', true) REFERENCES boards(id),
        id BIGSERIAL,
        task_id TEXT NOT NULL,
        author TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at BIGINT NOT NULL,
        PRIMARY KEY (board_id, id)
    );
    CREATE TABLE IF NOT EXISTS task_events (
        board_id TEXT NOT NULL DEFAULT current_setting('hermes.kanban_board_id', true) REFERENCES boards(id),
        id BIGSERIAL,
        task_id TEXT NOT NULL,
        run_id BIGINT,
        kind TEXT NOT NULL,
        payload TEXT,
        created_at BIGINT NOT NULL,
        PRIMARY KEY (board_id, id)
    );
    CREATE TABLE IF NOT EXISTS task_runs (
        board_id TEXT NOT NULL DEFAULT current_setting('hermes.kanban_board_id', true) REFERENCES boards(id),
        id BIGSERIAL,
        task_id TEXT NOT NULL,
        profile TEXT,
        step_key TEXT,
        status TEXT NOT NULL,
        claim_lock TEXT,
        claim_expires BIGINT,
        worker_pid INTEGER,
        max_runtime_seconds INTEGER,
        last_heartbeat_at BIGINT,
        started_at BIGINT NOT NULL,
        ended_at BIGINT,
        outcome TEXT,
        summary TEXT,
        metadata TEXT,
        error TEXT,
        PRIMARY KEY (board_id, id)
    );
    CREATE TABLE IF NOT EXISTS kanban_notify_subs (
        board_id TEXT NOT NULL DEFAULT current_setting('hermes.kanban_board_id', true) REFERENCES boards(id),
        task_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        thread_id TEXT NOT NULL DEFAULT '',
        user_id TEXT,
        notifier_profile TEXT,
        created_at BIGINT NOT NULL,
        last_event_id BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY (board_id, task_id, platform, chat_id, thread_id)
    );
    """
    with conn.cursor() as cur:
        cur.execute(ddl)


def _sqlite_rows(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[sqlite3.Row]]:
    names = {
        str(row["name"])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if table not in names:
        return [], []
    cols = [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")]
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return cols, rows


def _reset_pg_sequences(cur: Any, board_id: str) -> None:
    for table in ("task_comments", "task_events", "task_runs"):
        cur.execute(
            """
            SELECT setval(
                pg_get_serial_sequence(%s, 'id'),
                GREATEST(
                    COALESCE((SELECT MAX(id) FROM %s WHERE board_id = %s), 0),
                    1
                ),
                COALESCE((SELECT MAX(id) FROM %s WHERE board_id = %s), 0) > 0
            )
            """
            % ("%s", _pg_ident(table), "%s", _pg_ident(table), "%s"),
            (table, board_id, board_id),
        )


def migrate_to_postgres(plans: list[BoardPlan], dsn: str) -> dict[str, dict[str, int]]:
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except Exception as exc:  # pragma: no cover - dependency may be absent locally
        raise SystemExit(f"psycopg is required for migration: {exc}") from exc

    results: dict[str, dict[str, int]] = {}
    with psycopg.connect(dsn) as pg:
        _ensure_pg_schema(pg)
        with pg.cursor() as cur:
            for plan in plans:
                if plan.selected is None:
                    raise SystemExit(f"refusing to create empty board {plan.board_id!r}: no source")
                cur.execute("DELETE FROM kanban_notify_subs WHERE board_id = %s", (plan.board_id,))
                cur.execute("DELETE FROM task_events WHERE board_id = %s", (plan.board_id,))
                cur.execute("DELETE FROM task_runs WHERE board_id = %s", (plan.board_id,))
                cur.execute("DELETE FROM task_comments WHERE board_id = %s", (plan.board_id,))
                cur.execute("DELETE FROM task_links WHERE board_id = %s", (plan.board_id,))
                cur.execute("DELETE FROM tasks WHERE board_id = %s", (plan.board_id,))
                cur.execute("DELETE FROM boards WHERE id = %s", (plan.board_id,))
                cur.execute(
                    "INSERT INTO boards (id, metadata, source_path) VALUES (%s, %s, %s)",
                    (plan.board_id, Jsonb(plan.metadata), str(plan.selected.path)),
                )

                board_counts: dict[str, int] = {}
                with _connect_readonly(plan.selected.path) as sq:
                    for table in DATA_TABLES:
                        cols, rows = _sqlite_rows(sq, table)
                        if not cols:
                            board_counts[table] = 0
                            continue
                        insert_cols = ["board_id", *cols]
                        placeholders = ", ".join(["%s"] * len(insert_cols))
                        sql = (
                            f"INSERT INTO {_pg_ident(table)} "
                            f"({', '.join(_pg_ident(c) for c in insert_cols)}) "
                            f"VALUES ({placeholders})"
                        )
                        for row in rows:
                            cur.execute(sql, [plan.board_id, *[row[c] for c in cols]])
                        cur.execute(
                            f"SELECT COUNT(*) FROM {_pg_ident(table)} WHERE board_id = %s",
                            (plan.board_id,),
                        )
                        dest_count = int(cur.fetchone()[0])
                        source_count = int(plan.selected.counts.get(table, 0))
                        if dest_count < source_count:
                            raise SystemExit(
                                f"loss guard failed for {plan.board_id}.{table}: "
                                f"destination {dest_count} < source {source_count}"
                            )
                        board_counts[table] = dest_count
                _reset_pg_sequences(cur, plan.board_id)
                results[plan.board_id] = board_counts
        pg.commit()
    return results


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_KANBAN_HOME", "~/.hermes"))
    parser.add_argument("--postgres-dsn", default=os.environ.get("HERMES_KANBAN_POSTGRES_DSN"))
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args(argv)

    hermes_home = Path(args.hermes_home).expanduser()
    plans = discover_boards(hermes_home)
    select_sources(plans)

    missing = [p.board_id for p in plans if p.selected is None]
    if missing:
        manifest = _manifest(plans, migrated=False, destination=args.postgres_dsn)
        if args.manifest:
            write_manifest(Path(args.manifest).expanduser(), manifest)
        print(json.dumps(manifest, indent=2, sort_keys=True), file=sys.stderr)
        return 2

    migrated = False
    destination_counts: dict[str, dict[str, int]] = {}
    if args.postgres_dsn and not args.inventory_only:
        destination_counts = migrate_to_postgres(plans, args.postgres_dsn)
        migrated = True

    manifest = _manifest(plans, migrated=migrated, destination=args.postgres_dsn)
    for board in manifest["boards"]:
        board["destination_counts"] = destination_counts.get(board["board_id"], {})
    if args.manifest:
        write_manifest(Path(args.manifest).expanduser(), manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

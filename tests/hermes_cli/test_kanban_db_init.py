from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from hermes_cli import kanban_db as kb


def test_connect_initialization_is_thread_safe(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = kb.kanban_db_path(board="default")
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))

    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            conn = kb.connect(board="default")
            conn.close()
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    with kb.connect(board="default") as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    assert "max_retries" in cols


def test_connect_migrates_legacy_db_before_creating_additive_column_indexes(
    tmp_path, monkeypatch
):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = kb.kanban_db_path(board="default")
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Simulate a board DB created before these additive columns existed.
    # SCHEMA_SQL uses CREATE TABLE IF NOT EXISTS, so it will not add missing
    # columns to this table before running CREATE INDEX statements. Indexes on
    # additive columns must therefore be created only after migrations run.
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE tasks (
                id                   TEXT PRIMARY KEY,
                title                TEXT NOT NULL,
                body                 TEXT,
                assignee             TEXT,
                status               TEXT NOT NULL,
                priority             INTEGER DEFAULT 0,
                created_by           TEXT,
                created_at           INTEGER NOT NULL,
                started_at           INTEGER,
                completed_at         INTEGER,
                workspace_kind       TEXT NOT NULL DEFAULT 'scratch',
                workspace_path       TEXT,
                branch_name          TEXT,
                claim_lock           TEXT,
                claim_expires        INTEGER,
                result               TEXT,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                worker_pid           INTEGER,
                last_failure_error   TEXT,
                max_runtime_seconds  INTEGER,
                last_heartbeat_at    INTEGER,
                current_run_id       INTEGER,
                workflow_template_id TEXT,
                current_step_key     TEXT,
                skills               TEXT,
                model_override       TEXT,
                max_retries          INTEGER
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

    with kb.connect(board="default") as conn:
        task_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        event_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(task_events)")
        }
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }

    assert {"tenant", "idempotency_key", "session_id"}.issubset(task_cols)
    assert "run_id" in event_cols
    assert {
        "idx_tasks_tenant",
        "idx_tasks_idempotency",
        "idx_tasks_session_id",
        "idx_events_run",
    }.issubset(indexes)

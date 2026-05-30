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


def _create_legacy_db(path: Path) -> None:
    """Create a kanban DB with the old TEXT PRIMARY KEY schema."""
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT,
            status TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            assignee TEXT,
            parent_id TEXT,
            created_at INTEGER NOT NULL,
            claim_lock TEXT,
            claim_expires INTEGER,
            started_at INTEGER
        );
        CREATE TABLE task_links (
            parent_id TEXT NOT NULL,
            child_id TEXT NOT NULL,
            PRIMARY KEY (parent_id, child_id)
        );
        CREATE TABLE task_comments (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            author TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE task_events (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE task_runs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            profile TEXT,
            status TEXT NOT NULL,
            claim_lock TEXT,
            claim_expires INTEGER,
            worker_pid INTEGER,
            max_runtime_seconds INTEGER,
            last_heartbeat_at INTEGER,
            started_at INTEGER NOT NULL,
            ended_at INTEGER,
            outcome TEXT,
            summary TEXT,
            metadata TEXT,
            error TEXT
        );
        CREATE TABLE kanban_notify_subs (
            task_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            thread_id TEXT NOT NULL DEFAULT '',
            user_id TEXT,
            created_at INTEGER NOT NULL,
            last_event_id TEXT,
            PRIMARY KEY (task_id, platform, chat_id, thread_id)
        );
    """)
    # Insert sample data
    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
        ("task-1", "Test task", "done", 1000),
    )
    conn.execute(
        "INSERT INTO task_comments (id, task_id, author, body, created_at) VALUES (?, ?, ?, ?, ?)",
        ("comment-1", "task-1", "agent", "hello", 1500),
    )
    conn.execute(
        "INSERT INTO task_events (id, task_id, kind, created_at) VALUES (?, ?, ?, ?)",
        ("event-1", "task-1", "completed", 2000),
    )
    conn.execute(
        "INSERT INTO task_runs (id, task_id, status, started_at) VALUES (?, ?, ?, ?)",
        ("run-1", "task-1", "done", 1000),
    )
    conn.execute(
        "INSERT INTO kanban_notify_subs (task_id, platform, chat_id, created_at, last_event_id) "
        "VALUES (?, ?, ?, ?, ?)",
        ("task-1", "telegram", "123", 1000, "event-1"),
    )
    conn.commit()
    conn.close()


def test_migrate_autoincrement_schema_rebuilds_text_pk_tables(tmp_path, monkeypatch):
    """Tables with TEXT PRIMARY KEY should be rebuilt as INTEGER AUTOINCREMENT."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = home / "kanban" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _create_legacy_db(db_path)

    # Clear init cache so connect() runs migration
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))

    with kb.connect(db_path) as conn:
        # Verify task_events.id is now INTEGER
        ev_cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(task_events)")}
        assert ev_cols["id"]["type"].upper() == "INTEGER"
        assert ev_cols["id"]["pk"] == 1

        # Verify task_comments.id is now INTEGER
        cm_cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(task_comments)")}
        assert cm_cols["id"]["type"].upper() == "INTEGER"
        assert cm_cols["id"]["pk"] == 1

        # Verify task_runs.id is now INTEGER
        run_cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(task_runs)")}
        assert run_cols["id"]["type"].upper() == "INTEGER"
        assert run_cols["id"]["pk"] == 1

        # Verify kanban_notify_subs.last_event_id is now INTEGER
        notify_cols = {
            row["name"]: row for row in conn.execute("PRAGMA table_info(kanban_notify_subs)")
        }
        assert notify_cols["last_event_id"]["type"].upper() == "INTEGER"

        # Verify data was preserved
        tasks = conn.execute("SELECT * FROM tasks").fetchall()
        assert len(tasks) == 1

        events = conn.execute("SELECT * FROM task_events").fetchall()
        assert len(events) == 1
        assert events[0]["kind"] == "completed"

        comments = conn.execute("SELECT * FROM task_comments").fetchall()
        assert len(comments) == 1

        runs = conn.execute("SELECT * FROM task_runs").fetchall()
        assert len(runs) == 1

        # Verify last_event_id was cast to INTEGER (0 for non-numeric values)
        subs = conn.execute("SELECT * FROM kanban_notify_subs").fetchall()
        assert len(subs) == 1
        # "event-1" is not numeric, so CAST returns 0
        assert subs[0]["last_event_id"] == 0


def test_migrate_autoincrement_schema_idempotent(tmp_path, monkeypatch):
    """Running migration twice should not break anything."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = home / "kanban" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _create_legacy_db(db_path)

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))

    # First migration
    with kb.connect(db_path) as conn:
        pass

    # Second migration (should be no-op)
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as conn:
        ev_cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(task_events)")}
        assert ev_cols["id"]["type"].upper() == "INTEGER"
        events = conn.execute("SELECT * FROM task_events").fetchall()
        assert len(events) == 1


def test_migrate_autoincrement_schema_fresh_db_unchanged(tmp_path, monkeypatch):
    """A fresh DB with correct schema should not be touched by migration."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = home / "kanban" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))

    # Create fresh DB via connect (runs SCHEMA_SQL + migrations)
    with kb.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
            ("task-1", "Test", "running", 1000),
        )
        conn.execute(
            "INSERT INTO task_events (task_id, kind, created_at) VALUES (?, ?, ?)",
            ("task-1", "completed", 3000),
        )

    # Verify AUTOINCREMENT works (first insert gets id=1)
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as conn:
        events = conn.execute("SELECT * FROM task_events ORDER BY id").fetchall()
        assert len(events) == 1
        assert events[0]["id"] == 1  # AUTOINCREMENT starts at 1


def test_unseen_events_for_sub_with_migrated_db(tmp_path, monkeypatch):
    """After migration, unseen_events_for_sub should not crash on int(None)."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = home / "kanban" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _create_legacy_db(db_path)

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))

    with kb.connect(db_path) as conn:
        # This should not raise TypeError: int() argument must be a string...
        max_id, events = kb.unseen_events_for_sub(
            conn,
            task_id="task-1",
            platform="telegram",
            chat_id="123",
        )
        # After migration, last_event_id was cast to 0, so all events are unseen
        assert isinstance(max_id, int)

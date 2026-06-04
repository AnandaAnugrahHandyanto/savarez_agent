from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import hermes_state
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


def test_connect_configures_journal_mode_once_per_process_path(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    db_path = kb.kanban_db_path(board="default")
    resolved = str(db_path.resolve())
    kb._INITIALIZED_PATHS.discard(resolved)
    kb._JOURNAL_CONFIGURED_PATHS.discard(resolved)

    calls: list[str] = []

    def fake_apply_wal_with_fallback(conn, *, db_label="state.db"):
        calls.append(db_label)
        return "wal"

    monkeypatch.setattr(hermes_state, "apply_wal_with_fallback", fake_apply_wal_with_fallback)

    for _ in range(3):
        conn = kb.connect(board="default")
        conn.close()

    assert calls == ["kanban.db (kanban.db)"]


def test_transient_pragma_disk_io_error_is_retried(monkeypatch):
    monkeypatch.setattr(kb, "_TRANSIENT_PRAGMA_RETRY_DELAYS", (0, 0))
    calls: list[str] = []

    class FlakyConn:
        def execute(self, sql: str):
            calls.append(sql)
            if len(calls) < 3:
                raise sqlite3.OperationalError("disk I/O error")
            return object()

    kb._execute_transient_pragma(FlakyConn(), "PRAGMA synchronous=NORMAL", db_label="test.db")

    assert calls == [
        "PRAGMA synchronous=NORMAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA synchronous=NORMAL",
    ]


def test_transient_pragma_non_io_error_is_not_retried(monkeypatch):
    monkeypatch.setattr(kb, "_TRANSIENT_PRAGMA_RETRY_DELAYS", (0, 0))
    calls: list[str] = []

    class BadConn:
        def execute(self, sql: str):
            calls.append(sql)
            raise sqlite3.OperationalError("database is locked")

    try:
        kb._execute_transient_pragma(BadConn(), "PRAGMA synchronous=NORMAL", db_label="test.db")
    except sqlite3.OperationalError as exc:
        assert "database is locked" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected OperationalError")

    assert calls == ["PRAGMA synchronous=NORMAL"]

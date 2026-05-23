from __future__ import annotations

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


def test_auto_init_refuses_missing_named_board_db(tmp_path, monkeypatch):
    import pytest

    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    kb.write_board_metadata("project")
    db_path = kb.kanban_db_path(board="project")
    assert not db_path.exists()

    with pytest.raises(Exception, match="refusing to auto-create missing kanban DB"):
        kb.init_db(board="project", allow_create=False)
    assert not db_path.exists()

    kb.init_db(board="project")
    assert db_path.exists()


def test_auto_init_refuses_empty_named_board_db(tmp_path, monkeypatch):
    import pytest

    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    kb.write_board_metadata("project")
    db_path = kb.kanban_db_path(board="project")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"")

    with pytest.raises(Exception, match="refusing to auto-create empty/truncated kanban DB"):
        kb.init_db(board="project", allow_create=False)
    assert db_path.read_bytes() == b""

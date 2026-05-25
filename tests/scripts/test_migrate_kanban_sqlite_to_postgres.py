import importlib.util
import sqlite3
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "migrate_kanban_sqlite_to_postgres.py"
SPEC = importlib.util.spec_from_file_location("migrate_kanban_sqlite_to_postgres", SCRIPT_PATH)
migration = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = migration
SPEC.loader.exec_module(migration)


def _write_board_db(path: Path, *, tasks: int = 1, events: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                workspace_kind TEXT NOT NULL DEFAULT 'scratch'
            );
            CREATE TABLE task_links (parent_id TEXT NOT NULL, child_id TEXT NOT NULL);
            CREATE TABLE task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at INTEGER NOT NULL
            );
            CREATE TABLE kanban_notify_subs (
                task_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                thread_id TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                PRIMARY KEY (task_id, platform, chat_id, thread_id)
            );
            """
        )
        for idx in range(tasks):
            conn.execute(
                "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, 'todo', 1)",
                (f"t_{idx}", f"Task {idx}"),
            )
        for idx in range(events):
            conn.execute(
                "INSERT INTO task_events (task_id, kind, created_at) VALUES ('t_0', 'created', ?)",
                (idx + 1,),
            )


def test_selects_recovered_preview_when_active_db_is_corrupt(tmp_path):
    hermes_home = tmp_path / ".hermes"
    _write_board_db(hermes_home / "kanban.db", tasks=2)
    board_dir = hermes_home / "kanban" / "boards" / "vtt-director-proto"
    board_dir.mkdir(parents=True)
    (board_dir / "board.json").write_text('{"name":"VTT Agentic"}', encoding="utf-8")
    (board_dir / "kanban.db").write_bytes(b"not sqlite")
    _write_board_db(board_dir / "kanban.db.bak-1", tasks=3, events=5)
    _write_board_db(board_dir / "kanban.db.recovered-preview", tasks=4, events=7)

    plans = migration.discover_boards(hermes_home)
    migration.select_sources(plans)

    by_board = {plan.board_id: plan for plan in plans}
    assert by_board["default"].selected.role == "active"
    vtt = by_board["vtt-director-proto"]
    assert vtt.selected.role == "recovered-preview"
    assert vtt.selected.counts["tasks"] == 4
    assert "active db unusable" in vtt.warnings[0]


def test_blocks_board_when_no_integral_source_exists(tmp_path):
    hermes_home = tmp_path / ".hermes"
    _write_board_db(hermes_home / "kanban.db", tasks=1)
    board_dir = hermes_home / "kanban" / "boards" / "broken"
    board_dir.mkdir(parents=True)
    (board_dir / "board.json").write_text("{}", encoding="utf-8")
    (board_dir / "kanban.db").write_bytes(b"not sqlite")

    plans = migration.discover_boards(hermes_home)
    migration.select_sources(plans)

    broken = {plan.board_id: plan for plan in plans}["broken"]
    assert broken.selected is None
    assert any("no usable source" in warning for warning in broken.warnings)

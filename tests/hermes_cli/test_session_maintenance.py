import sqlite3
import time
from pathlib import Path

from hermes_cli.session_maintenance import archive_prune, doctor_report, plan_archive_prune


def _make_state_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            parent_session_id TEXT,
            source TEXT,
            started_at REAL,
            ended_at REAL,
            message_count INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            system_prompt TEXT,
            model_config TEXT,
            handoff_state TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
            reasoning TEXT,
            reasoning_details TEXT,
            codex_reasoning_items TEXT,
            reasoning_content TEXT,
            codex_message_items TEXT
        );
        """
    )
    now = time.time()
    rows = [
        ("old-cron", None, "cron", now - 10 * 86400, now - 10 * 86400 + 5, 2, 100, 10, "sys", "{}", ""),
        ("new-cron", None, "cron", now - 2 * 86400, now - 2 * 86400 + 5, 1, 50, 5, "sys", "{}", ""),
        ("active-old-cron", None, "cron", now - 10 * 86400, None, 1, 50, 5, "sys", "{}", ""),
        ("discord-1", "old-cron", "discord", now - 20 * 86400, now - 20 * 86400 + 5, 1, 20, 2, "sys", "{}", ""),
    ]
    conn.executemany(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    for session_id, count in [("old-cron", 2), ("new-cron", 1), ("active-old-cron", 1), ("discord-1", 1)]:
        for i in range(count):
            conn.execute(
                """
                INSERT INTO messages(session_id, role, content, tool_calls, reasoning,
                  reasoning_details, codex_reasoning_items, reasoning_content, codex_message_items)
                VALUES (?, ?, ?, '', '', '', '', '', '')
                """,
                (session_id, "assistant" if i else "user", f"message {i}"),
            )
    conn.commit()
    conn.close()


def test_doctor_report_flags_cron_heavy_store(tmp_path):
    db_path = tmp_path / "state.db"
    _make_state_db(db_path)

    report = doctor_report(db_path)

    assert report["counts"]["sessions"] == 4
    assert report["counts"]["messages"] == 5
    assert report["by_source"][0]["source"] == "cron"
    assert any(flag["code"] == "CRON_DOMINATES_SESSION_STORE" for flag in report["risk_flags"])


def test_archive_prune_archives_before_deleting_only_ended_old_source_sessions(tmp_path):
    db_path = tmp_path / "state.db"
    archive_path = tmp_path / "archive.sqlite"
    backup_path = tmp_path / "backup.db"
    _make_state_db(db_path)

    plan = plan_archive_prune(db_path, source="cron", older_than_days=7)
    assert plan["candidate_sessions"] == 1
    assert plan["candidate_messages"] == 2

    result = archive_prune(
        db_path,
        archive_path,
        source="cron",
        older_than_days=7,
        backup_path=backup_path,
        vacuum=True,
    )

    assert result["archived_sessions"] == 1
    assert result["archived_messages"] == 2
    assert result["deleted_sessions"] == 1
    assert result["deleted_messages"] == 2
    assert archive_path.exists()
    assert backup_path.exists()

    with sqlite3.connect(db_path) as conn:
        remaining = {row[0] for row in conn.execute("SELECT id FROM sessions")}
        parent = conn.execute("SELECT parent_session_id FROM sessions WHERE id='discord-1'").fetchone()[0]
    assert remaining == {"new-cron", "active-old-cron", "discord-1"}
    assert parent is None

    with sqlite3.connect(archive_path) as conn:
        archived_sessions = conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
        archived_messages = conn.execute("SELECT count(*) FROM messages").fetchone()[0]
    assert archived_sessions == 1
    assert archived_messages == 2

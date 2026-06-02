from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from scripts.memory.social_ebbinghaus_sync import (
    SocialMemorySync,
    build_arg_parser,
    redact_sensitive_text,
)


def _init_state_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            user_id TEXT,
            title TEXT,
            started_at REAL NOT NULL
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    now = time.time()
    con.execute(
        "INSERT INTO sessions (id, source, user_id, title, started_at) VALUES (?, ?, ?, ?, ?)",
        ("s1", "telegram", "u1", "朝の相談", now),
    )
    con.execute(
        "INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?, ?, ?, ?, 1)",
        ("s1", "user", "Hermesの記憶バックアップをBitwardenで保管したい", now + 1),
    )
    con.execute(
        "INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?, ?, ?, ?, 1)",
        ("s1", "assistant", "AES鍵はgit外に置くのが安全です", now + 2),
    )
    con.commit()
    con.close()


def _init_memory_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE memories (
            memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL UNIQUE,
            encoded TEXT NOT NULL,
            cues TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            salience REAL DEFAULT 0.6,
            valence REAL DEFAULT 0.0,
            strength REAL DEFAULT 1.0,
            rehearsal_count INTEGER DEFAULT 0,
            retrieval_count INTEGER DEFAULT 0,
            source TEXT DEFAULT '',
            session_id TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            last_rehearsed_at REAL,
            last_retrieved_at REAL
        );
        """
    )
    con.commit()
    con.close()


def test_social_session_is_imported_to_ebbinghaus(tmp_path: Path) -> None:
    state_db = tmp_path / "state.db"
    memory_db = tmp_path / "ebbinghaus_memory.db"
    _init_state_db(state_db)
    _init_memory_db(memory_db)

    sync = SocialMemorySync(state_db=state_db, memory_db=memory_db, sources=("telegram",))
    result = sync.run(max_sessions=10, max_x_events=0, sleep=False)

    assert result["sessions_seen"] == 1
    assert result["memories_written"] == 1
    with sqlite3.connect(memory_db) as con:
        row = con.execute("SELECT content, tags, source, session_id FROM memories").fetchone()
    assert row[0].startswith("Social memory from telegram session")
    assert "memory backup" in row[0] or "記憶バックアップ" in row[0]
    assert "telegram" in row[1]
    assert row[2] == "social-memory-sync"
    assert row[3] == "s1"


def test_x_activity_jsonl_is_imported(tmp_path: Path) -> None:
    state_db = tmp_path / "missing-state.db"
    memory_db = tmp_path / "ebbinghaus_memory.db"
    x_log = tmp_path / "activity.jsonl"
    _init_memory_db(memory_db)
    x_log.write_text(
        json.dumps({"action": "post", "ok": True, "dry_run": True, "tweet_text": "はくあのX下書きです"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    sync = SocialMemorySync(state_db=state_db, memory_db=memory_db, x_activity_log=x_log)
    result = sync.run(max_sessions=0, max_x_events=10, sleep=False)

    assert result["x_events_seen"] == 1
    assert result["memories_written"] == 1
    with sqlite3.connect(memory_db) as con:
        row = con.execute("SELECT content, tags FROM memories").fetchone()
    assert "X memory" in row[0]
    assert "はくあのX下書き" in row[0]
    assert "x" in row[1]


def test_redacts_secret_like_values() -> None:
    token_value = "abc1234567890"
    secret_value = "supersecretpassword"
    oauth_value = "oauthcode"
    text = "".join(
        [
            "token",
            "=",
            token_value,
            " SECRET_KEY",
            "=",
            secret_value,
            " https://example.test/callback?",
            "code",
            "=",
            oauth_value,
        ]
    )
    redacted = redact_sensitive_text(text)
    assert "abc1234567890" not in redacted
    assert "supersecretpassword" not in redacted
    assert "oauthcode" not in redacted


def test_parser_accepts_social_sources() -> None:
    args = build_arg_parser().parse_args(["--sources", "line,discord,telegram", "--max-sessions", "3"])
    assert args.sources == "line,discord,telegram"
    assert args.max_sessions == 3

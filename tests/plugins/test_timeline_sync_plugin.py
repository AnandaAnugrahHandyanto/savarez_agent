from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _make_state_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            started_at REAL NOT NULL,
            message_count INTEGER DEFAULT 0
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO sessions (id, source, title, started_at, message_count) VALUES (?, ?, ?, ?, ?)",
        ("slack-1", "slack", "Slack thread", 1.0, 1),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        ("slack-1", "user", "메모리 질문", 1_700_000_000.0),
    )
    conn.commit()
    conn.close()


def test_plugin_pre_llm_call_returns_context_when_enabled(tmp_path, monkeypatch):
    from plugins.timeline_sync import on_pre_llm_call

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    monkeypatch.setenv("HERMES_TIMELINE_SYNC_DB", str(db_path))
    monkeypatch.setenv("HERMES_TIMELINE_SYNC_NOW", "1700000060")
    monkeypatch.delenv("HERMES_TIMELINE_SYNC_ENABLED", raising=False)

    result = on_pre_llm_call(
        session_id="slack-1",
        user_message="이어서 말해줘",
        conversation_history=[],
        platform="slack",
        model="test-model",
    )

    assert isinstance(result, dict)
    assert "Timeline sync" in result["context"]
    assert "Current platform: slack" in result["context"]


def test_plugin_pre_llm_call_can_be_disabled(tmp_path, monkeypatch):
    from plugins.timeline_sync import on_pre_llm_call

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    monkeypatch.setenv("HERMES_TIMELINE_SYNC_DB", str(db_path))
    monkeypatch.setenv("HERMES_TIMELINE_SYNC_ENABLED", "0")

    result = on_pre_llm_call(
        session_id="slack-1",
        user_message="이어서 말해줘",
        conversation_history=[],
        platform="slack",
        model="test-model",
    )

    assert result is None

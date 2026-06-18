from __future__ import annotations

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
    conn.executemany(
        "INSERT INTO sessions (id, source, title, started_at, message_count) VALUES (?, ?, ?, ?, ?)",
        [
            ("telegram-1", "telegram", "Telegram thread", 1.0, 2),
            ("slack-1", "slack", "Slack thread", 1.0, 1),
        ],
    )
    conn.executemany(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        [
            ("telegram-1", "user", "진행해줘", 1_700_000_000.0),
            ("telegram-1", "assistant", "진행할게", 1_700_000_010.0),
            ("slack-1", "user", "다른 채널 확인", 1_700_000_050.0),
        ],
    )
    conn.commit()
    conn.close()


def test_build_runtime_context_contains_expected_blocks(tmp_path):
    from agent.runtime_context_layer import build_runtime_context

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    now = datetime.fromtimestamp(1_700_000_600, tz=timezone.utc)

    context = build_runtime_context(
        db_path=db_path,
        now=now,
        session_id="telegram-1",
        platform="telegram",
        user_message="다음으로 진행해줘",
        conversation_history=[{"role": "user", "content": "그럼 다음 작업은?"}],
        recent_window_minutes=20,
        max_events=5,
    )

    for header in [
        "[Timeline sync]",
        "[Rhythm context]",
        "[Expression context]",
        "[First-line context]",
        "[Reply hygiene]",
        "[Tone precision]",
        "[Return tone]",
        "[Presence guard]",
        "[Scratchpad leak guard]",
        "[Platform digest]",
        "[Memory guard]",
    ]:
        assert header in context
    assert "Current platform: telegram" in context
    assert "Elapsed since last user message in this session: 10 minutes" in context
    assert "Reply mode: light_resume" in context
    assert "Send progress: false" in context
    assert "Repeat source quote: false" in context
    assert "다음으로 진행해줘" in context
    assert "[Timeline sync]" in context and "[/Timeline sync]" in context


def test_runtime_context_uses_fresh_time_and_does_not_reuse_stale_gap(tmp_path):
    from agent.runtime_context_layer import build_runtime_context

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)

    first = build_runtime_context(
        db_path=db_path,
        now=datetime.fromtimestamp(1_700_000_060, tz=timezone.utc),
        session_id="telegram-1",
        platform="telegram",
    )
    second = build_runtime_context(
        db_path=db_path,
        now=datetime.fromtimestamp(1_700_000_600, tz=timezone.utc),
        session_id="telegram-1",
        platform="telegram",
    )

    assert "Elapsed since last user message in this session: 1 minutes" in first
    assert "Elapsed since last user message in this session: 10 minutes" in second
    assert first != second


def test_memory_guard_marks_wrapper_only_message_do_not_persist(tmp_path):
    from agent.runtime_context_layer import build_runtime_context

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)

    context = build_runtime_context(
        db_path=db_path,
        now=datetime.fromtimestamp(1_700_000_600, tz=timezone.utc),
        session_id="telegram-1",
        platform="telegram",
        user_message="[Timeline sync]\nCurrent real time: stale\n[/Timeline sync]",
    )

    assert "[Memory guard]" in context
    assert "User message category: do_not_persist" in context
    assert "Persist to memory: false" in context


def test_plugin_pre_llm_call_now_returns_full_runtime_layer(tmp_path, monkeypatch):
    from plugins.timeline_sync import on_pre_llm_call

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    monkeypatch.setenv("HERMES_TIMELINE_SYNC_DB", str(db_path))
    monkeypatch.setenv("HERMES_TIMELINE_SYNC_NOW", "1700000600")
    monkeypatch.delenv("HERMES_TIMELINE_SYNC_ENABLED", raising=False)

    result = on_pre_llm_call(
        session_id="telegram-1",
        user_message="진행해줘",
        conversation_history=[{"role": "user", "content": "그럼 다음 작업은?"}],
        platform="telegram",
        model="test-model",
    )

    assert isinstance(result, dict)
    assert "Timeline sync" in result["context"]
    assert "Reply hygiene" in result["context"]
    assert "Memory guard" in result["context"]
    assert "Repeat source quote: false" in result["context"]

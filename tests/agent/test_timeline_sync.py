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
    rows = [
        ("slack-1", "slack", "Slack memory thread", 1000.0, 2),
        ("telegram-1", "telegram", "Telegram main", 1010.0, 2),
        ("cli-1", "cli", "CLI check", 1020.0, 1),
    ]
    conn.executemany(
        "INSERT INTO sessions (id, source, title, started_at, message_count) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    messages = [
        ("slack-1", "user", "너의 메모리 시스템은 어떻게 작동해?", 1_700_000_000.0),
        ("slack-1", "assistant", "메모리 구조를 설명했어", 1_700_000_010.0),
        ("telegram-1", "user", "클론잡 좀 꺼줘", 1_700_000_100.0),
        ("telegram-1", "assistant", "작업 삭제 완료야", 1_700_000_120.0),
        ("cli-1", "user", "한 단어로 답", 1_700_000_200.0),
    ]
    conn.executemany(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        messages,
    )
    conn.commit()
    conn.close()


def test_coerce_epoch_seconds_accepts_datetime_and_milliseconds():
    from agent.timeline_sync import coerce_epoch_seconds

    dt = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)

    assert coerce_epoch_seconds(dt) == 1_700_000_000.0
    assert coerce_epoch_seconds(1_700_000_000_000) == 1_700_000_000.0
    assert coerce_epoch_seconds("1700000000") == 1_700_000_000.0
    assert coerce_epoch_seconds("bad") is None


def test_describe_elapsed_uses_real_gap_buckets():
    from agent.timeline_sync import describe_elapsed

    assert describe_elapsed(75).bucket == "immediate"
    assert describe_elapsed(600).bucket == "recent"
    assert describe_elapsed(7200).bucket == "earlier_today"
    assert describe_elapsed(30 * 3600).bucket == "older"


def test_get_recent_events_orders_sources_by_real_time(tmp_path):
    from agent.timeline_sync import get_recent_events

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)

    events = get_recent_events(
        db_path=db_path,
        since_ts=1_700_000_050.0,
        limit=3,
        exclude_session_id="telegram-1",
    )

    assert [event["source"] for event in events] == ["cli"]
    assert events[0]["preview"] == "한 단어로 답"


def test_build_timeline_context_includes_current_time_gap_and_cross_platform_events(tmp_path):
    from agent.timeline_sync import build_timeline_context

    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    now = datetime.fromtimestamp(1_700_000_500, tz=timezone.utc)

    context = build_timeline_context(
        db_path=db_path,
        now=now,
        session_id="telegram-1",
        platform="telegram",
        recent_window_minutes=10,
        max_events=5,
    )

    assert "Timeline sync" in context
    assert "Current real time:" in context
    assert "Current platform: telegram" in context
    assert "Elapsed since last user message in this session: 6 minutes 40 seconds" in context
    assert "Recent cross-platform events" in context
    assert "CLI" in context
    assert "한 단어로 답" in context
    assert "Avoid saying" in context

import sqlite3
from pathlib import Path

import yaml

from cron import ockham_outbox


def _write_ockham_config(tmp_path: Path, *, chat_id="", enabled=True, start="23:00", end="07:00"):
    cfg = {
        "notify": {
            "telegram": {"enabled": enabled, "chat_id": chat_id},
            "quiet_hours": {"start": start, "end": end, "timezone": "America/New_York"},
        }
    }
    path = tmp_path / "ockham.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _write_outbox(tmp_path: Path, rows):
    path = tmp_path / "outbox.db"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE outbox (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                deliver_after INTEGER NOT NULL DEFAULT 0,
                sent_at INTEGER NOT NULL DEFAULT 0,
                dedup_key TEXT NOT NULL DEFAULT '',
                coalesce_key TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.executemany(
            "INSERT INTO outbox (id, type, title, body, priority, status, created_at, deliver_after, sent_at, dedup_key, coalesce_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return path


def test_resolve_delivery_target_prefers_explicit_chat(monkeypatch, tmp_path):
    cfg = _write_ockham_config(tmp_path, chat_id="12345")
    monkeypatch.setenv("OCKHAM_CONFIG_PATH", str(cfg))
    assert ockham_outbox.resolve_delivery_target() == "telegram:12345"


def test_should_send_respects_quiet_hours_for_non_alert(monkeypatch, tmp_path):
    cfg = _write_ockham_config(tmp_path, chat_id="12345")
    monkeypatch.setenv("OCKHAM_CONFIG_PATH", str(cfg))
    from datetime import datetime
    quiet_time = datetime(2026, 4, 10, 23, 30)
    assert ockham_outbox.should_send("alert", quiet_time) is True
    assert ockham_outbox.should_send("approval", quiet_time) is False
    assert ockham_outbox.should_send("digest", quiet_time) is False


def test_drain_marks_sent_and_skips_quiet(monkeypatch, tmp_path):
    cfg = _write_ockham_config(tmp_path, chat_id="12345")
    db = _write_outbox(
        tmp_path,
        [
            ("a1", "alert", "Alert", "body", 2, "pending", 100, 0, 0, "", ""),
            ("p1", "approval", "Approval", "body", 1, "pending", 100, 0, 0, "approval:b1:2", ""),
        ],
    )
    monkeypatch.setenv("OCKHAM_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("OCKHAM_OUTBOX_PATH", str(db))
    sent = []

    def deliver_fn(notification, target, content):
        sent.append((notification.id, target, content))
        return None

    from datetime import datetime
    delivered, errors = ockham_outbox.drain(deliver_fn, now=datetime(2026, 4, 10, 23, 30))
    assert delivered == 1
    assert errors == []
    assert sent[0][0] == "a1"

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT id, status FROM outbox ORDER BY id").fetchall()
    finally:
        conn.close()
    assert rows == [("a1", "sent"), ("p1", "pending")]

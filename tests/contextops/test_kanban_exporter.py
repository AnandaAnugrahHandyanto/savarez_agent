"""Targeted tests for the read-only Hermes Kanban -> ContextOps exporter.

The exporter is quarantined under ``plugins.context_engine.contextops`` and
must:

* never emit raw task ids, channel/discord ids, absolute paths, raw payloads,
  or provider-shaped tokens;
* only emit deterministic opaque ``ref:<hex>`` provenance pointers;
* be read-only against the Hermes Kanban SQLite file;
* round-trip to JSONL that passes its own leak gate and matches a golden
  fixture.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

from plugins.context_engine.contextops.kanban_exporter import (
    KANBAN_SOURCE,
    assert_line_safe,
    export_kanban_to_jsonl,
    iter_kanban_events,
    opaque_ref,
    scan_jsonl_for_leaks,
    task_event_row_to_event,
    task_row_to_event,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_PATH = FIXTURE_DIR / "kanban_exporter_golden.jsonl"


# --- DB helpers --------------------------------------------------------------

def _make_kanban_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT,
                body TEXT,
                status TEXT,
                workspace_path TEXT,
                session_id TEXT,
                created_at INTEGER
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                run_id INTEGER,
                kind TEXT NOT NULL,
                payload TEXT,
                created_at INTEGER NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# Helper to write rows with explicit timestamps for deterministic output.
GOLDEN_TS_ALPHA = 1767323045        # 2026-01-02T03:04:05Z
GOLDEN_TS_BETA = 1767323046         # 2026-01-02T03:04:06Z
GOLDEN_TS_EVENT_1 = 1767323100      # 2026-01-02T03:05:00Z
GOLDEN_TS_EVENT_2 = 1767323160      # 2026-01-02T03:06:00Z


@pytest.fixture()
def golden_db(tmp_path: Path) -> Path:
    path = tmp_path / "kanban.db"
    _make_kanban_db(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO tasks (id,title,body,status,workspace_path,session_id,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                "task-alpha-001",
                "operator wants /etc/passwd inspection AKIAABCDEFGHIJKLMNOP",
                "raw transcript body that must not leak guild_id=1234567890123456789",
                "in_progress",
                "/home/op/workspaces/task-alpha-001",
                "sess-secret-xyz",
                GOLDEN_TS_ALPHA,
            ),
        )
        conn.execute(
            "INSERT INTO tasks (id,title,body,status,workspace_path,session_id,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                "task-beta-002",
                "another task",
                "more body",
                "operator pasted /home/op/.env",
                None,
                None,
                GOLDEN_TS_BETA,
            ),
        )
        conn.execute(
            "INSERT INTO task_events (id,task_id,run_id,kind,payload,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                1,
                "task-alpha-001",
                42,
                "started",
                json.dumps({"channel_id": "1234567890123456789", "body": "raw"}),
                GOLDEN_TS_EVENT_1,
            ),
        )
        conn.execute(
            "INSERT INTO task_events (id,task_id,run_id,kind,payload,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                2,
                "task-alpha-001",
                42,
                "operator said sensitive things",
                json.dumps({"token": "AKIAABCDEFGHIJKLMNOP"}),
                GOLDEN_TS_EVENT_2,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return path


# --- opaque_ref --------------------------------------------------------------

def test_opaque_ref_is_deterministic_and_prefixed() -> None:
    a = opaque_ref("task-001", namespace="task")
    b = opaque_ref("task-001", namespace="task")
    assert a == b
    assert a.startswith("ref:")
    assert all(ch in "0123456789abcdef" for ch in a[len("ref:"):])


def test_opaque_ref_distinguishes_namespaces() -> None:
    assert opaque_ref("task-001", namespace="task") != opaque_ref("task-001", namespace="task_event")


def test_opaque_ref_rejects_empty() -> None:
    with pytest.raises(ValueError):
        opaque_ref("", namespace="task")
    with pytest.raises(ValueError):
        opaque_ref("   ", namespace="task")


# --- task_row_to_event -------------------------------------------------------

def test_task_row_to_event_uses_opaque_id_and_drops_raw_fields() -> None:
    row = {
        "id": "task-alpha-001",
        "title": "operator wants /etc/passwd inspection",
        "body": "long raw body with channel_id=1234567890123456789",
        "status": "in_progress",
        "workspace_path": "/home/op/workspaces/task-alpha-001",
        "session_id": "sess-secret-xyz",
        "created_at": GOLDEN_TS_ALPHA,
    }
    event = task_row_to_event(row)
    blob = event.model_dump_json()
    assert "task-alpha-001" not in blob
    assert "sess-secret-xyz" not in blob
    assert "/home/op/" not in blob
    assert "/etc/passwd" not in blob
    assert "channel_id" not in blob
    assert event.id.startswith("ref:")
    assert event.source == KANBAN_SOURCE
    assert event.refs == [opaque_ref("task-alpha-001", namespace="task")]
    assert event.metadata == {"kind": "kanban_task", "status": "in_progress"}


def test_task_row_to_event_redacts_unsafe_status_value() -> None:
    row = {"id": "task-x", "status": "operator pasted /home/op/.env", "created_at": GOLDEN_TS_BETA}
    event = task_row_to_event(row)
    assert event.metadata["status"] == "redacted"
    assert "/home/op/.env" not in event.model_dump_json()


def test_task_row_to_event_redacts_raw_id_shaped_status_value() -> None:
    row = {"id": "task-x", "status": "task-alpha-001", "created_at": GOLDEN_TS_BETA}
    event = task_row_to_event(row)
    assert event.metadata["status"] == "redacted"
    assert "task-alpha-001" not in event.model_dump_json()


def test_task_row_to_event_requires_id() -> None:
    with pytest.raises(ValueError):
        task_row_to_event({"status": "open", "created_at": 0})


# --- task_event_row_to_event -------------------------------------------------

def test_task_event_row_to_event_omits_run_id_and_payload() -> None:
    row = {
        "id": 99,
        "task_id": "task-alpha-001",
        "run_id": 42,
        "kind": "started",
        "payload": json.dumps({"channel_id": "1234567890123456789", "token": "AKIAABCDEFGHIJKLMNOP"}),
        "created_at": GOLDEN_TS_EVENT_1,
    }
    event = task_event_row_to_event(row)
    blob = event.model_dump_json()
    assert "task-alpha-001" not in blob
    assert "1234567890123456789" not in blob
    assert "AKIAABCDEFGHIJKLMNOP" not in blob
    assert "run_id" not in blob
    assert "payload" not in blob
    assert "42" not in blob.replace('"42', "")  # the raw run_id 42 must not appear as a number
    assert event.metadata == {"kind": "kanban_task_event", "task_event_kind": "started"}
    # Two opaque refs: the event-specific one + the parent task ref.
    assert len(event.refs) == 2
    assert all(r.startswith("ref:") for r in event.refs)
    assert opaque_ref("task-alpha-001", namespace="task") in event.refs


def test_task_event_row_to_event_redacts_unsafe_kind() -> None:
    row = {
        "id": 99,
        "task_id": "task-alpha-001",
        "run_id": None,
        "kind": "operator said sensitive things",
        "payload": None,
        "created_at": GOLDEN_TS_EVENT_2,
    }
    event = task_event_row_to_event(row)
    assert event.metadata["task_event_kind"] == "redacted"
    assert "operator" not in event.model_dump_json()


# --- export_kanban_to_jsonl --------------------------------------------------

def test_export_writes_sanitized_jsonl(golden_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    count = export_kanban_to_jsonl(golden_db, out)
    assert count == 4
    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 4
    for line in lines:
        obj = json.loads(line)
        assert obj["id"].startswith("ref:")
        assert obj["source"] == KANBAN_SOURCE
        for ref in obj["refs"]:
            assert ref.startswith("ref:")
        # Confirm none of the raw inputs leaked into this line.
        for forbidden in (
            "task-alpha-001",
            "task-beta-002",
            "sess-secret-xyz",
            "AKIAABCDEFGHIJKLMNOP",
            "1234567890123456789",
            "/home/op/",
            "/etc/passwd",
            "channel_id",
            "guild_id",
            "payload",
            "run_id",
        ):
            assert forbidden not in line, (forbidden, line)


def test_export_does_not_mutate_source_db(golden_db: Path, tmp_path: Path) -> None:
    mtime_before = golden_db.stat().st_mtime_ns
    size_before = golden_db.stat().st_size
    with sqlite3.connect(golden_db) as conn:
        digest_before = list(conn.execute("SELECT id, status, created_at FROM tasks ORDER BY id ASC"))
        events_before = list(conn.execute("SELECT id, task_id, kind, created_at FROM task_events ORDER BY id ASC"))
    # Avoid clock-resolution flakiness on the mtime equality check.
    time.sleep(0.01)
    export_kanban_to_jsonl(golden_db, tmp_path / "ro_check.jsonl")
    assert golden_db.stat().st_size == size_before
    assert golden_db.stat().st_mtime_ns == mtime_before
    with sqlite3.connect(golden_db) as conn:
        assert list(conn.execute("SELECT id, status, created_at FROM tasks ORDER BY id ASC")) == digest_before
        assert list(conn.execute("SELECT id, task_id, kind, created_at FROM task_events ORDER BY id ASC")) == events_before


def test_iter_kanban_events_uses_readonly_uri(golden_db: Path) -> None:
    events = list(iter_kanban_events(golden_db))
    assert len(events) == 4


def test_export_matches_golden_fixture(golden_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "golden_check.jsonl"
    export_kanban_to_jsonl(golden_db, out)
    actual = out.read_text(encoding="utf-8").splitlines()
    expected = GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
    assert actual == expected


# --- leak gate ---------------------------------------------------------------

def test_scan_jsonl_for_leaks_passes_on_exporter_output(golden_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "clean.jsonl"
    export_kanban_to_jsonl(golden_db, out)
    leaks = scan_jsonl_for_leaks(out)
    assert leaks == []


def test_scan_jsonl_for_leaks_passes_on_committed_golden_fixture() -> None:
    assert scan_jsonl_for_leaks(GOLDEN_PATH) == []


def test_scan_jsonl_for_leaks_detects_raw_id_leak(tmp_path: Path) -> None:
    bad = tmp_path / "leaky.jsonl"
    bad.write_text(json.dumps({
        "id": "ref:deadbeef00000000deadbeef",
        "source": "hermes_kanban",
        "text": "task with task_id=task-alpha-001",
        "refs": ["ref:deadbeef00000000deadbeef"],
        "created_at": "2026-01-02T03:04:05Z",
        "metadata": {},
    }) + "\n", encoding="utf-8")
    leaks = scan_jsonl_for_leaks(bad)
    assert len(leaks) == 1
    assert "task_id" in leaks[0]


def test_scan_jsonl_for_leaks_detects_raw_id_value_without_field_name(tmp_path: Path) -> None:
    bad = tmp_path / "leaky.jsonl"
    bad.write_text(json.dumps({
        "id": "ref:deadbeef00000000deadbeef",
        "source": "hermes_kanban",
        "text": "task-alpha-001",
        "refs": ["ref:deadbeef00000000deadbeef"],
        "created_at": "2026-01-02T03:04:05Z",
        "metadata": {},
    }) + "\n", encoding="utf-8")
    leaks = scan_jsonl_for_leaks(bad)
    assert leaks and "raw-id-shaped-value" in leaks[0]


def test_scan_jsonl_for_leaks_detects_path_leak(tmp_path: Path) -> None:
    bad = tmp_path / "leaky.jsonl"
    bad.write_text(json.dumps({
        "id": "ref:deadbeef00000000deadbeef",
        "source": "hermes_kanban",
        "text": "workspace at /home/op/ws",
        "refs": ["ref:deadbeef00000000deadbeef"],
        "created_at": "2026-01-02T03:04:05Z",
        "metadata": {},
    }) + "\n", encoding="utf-8")
    leaks = scan_jsonl_for_leaks(bad)
    assert leaks and "path" in leaks[0]


def test_scan_jsonl_for_leaks_detects_discord_snowflake(tmp_path: Path) -> None:
    bad = tmp_path / "leaky.jsonl"
    bad.write_text(json.dumps({
        "id": "ref:deadbeef00000000deadbeef",
        "source": "hermes_kanban",
        "text": "from channel 1234567890123456789",
        "refs": ["ref:deadbeef00000000deadbeef"],
        "created_at": "2026-01-02T03:04:05Z",
        "metadata": {},
    }) + "\n", encoding="utf-8")
    assert scan_jsonl_for_leaks(bad)


def test_scan_jsonl_for_leaks_detects_non_opaque_ref(tmp_path: Path) -> None:
    bad = tmp_path / "leaky.jsonl"
    bad.write_text(json.dumps({
        "id": "ref:deadbeef00000000deadbeef",
        "source": "hermes_kanban",
        "text": "ok",
        "refs": ["message:msg-7"],
        "created_at": "2026-01-02T03:04:05Z",
        "metadata": {},
    }) + "\n", encoding="utf-8")
    leaks = scan_jsonl_for_leaks(bad)
    assert leaks and ("non-opaque ref" in leaks[0] or "raw-id-shaped-value" in leaks[0])


def test_assert_line_safe_raises_on_leak() -> None:
    with pytest.raises(ValueError):
        assert_line_safe('{"id":"ref:deadbeef00000000deadbeef","source":"k","text":"see /home/op","refs":["ref:deadbeef00000000deadbeef"],"created_at":"2026-01-02T03:04:05Z","metadata":{}}')


# --- quarantine --------------------------------------------------------------

def test_top_level_contextops_does_not_export_kanban_exporter() -> None:
    import contextops

    for name in (
        "kanban_exporter",
        "export_kanban_to_jsonl",
        "iter_kanban_events",
        "task_row_to_event",
        "task_event_row_to_event",
    ):
        assert not hasattr(contextops, name), name

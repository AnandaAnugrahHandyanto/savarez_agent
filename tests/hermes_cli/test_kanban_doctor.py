"""Tests for hermes_cli.kanban_doctor — Layer 3 board health report.

Behavior-contract tests that exercise ``board_doctor`` against a real
(temporary) kanban.db to validate classification, bottleneck detection,
deadlock detection, and Layer 1/2 wiring.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_doctor as kdoc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _create_task(conn, **overrides):
    """Thin wrapper around kb.create_task with sensible defaults."""
    defaults = {
        "title": "test task",
        "assignee": "worker",
        "body": "Test task body with enough content to pass intake guard rules.",
    }
    # Map 'status' to 'initial_status' (the kwarg create_task expects).
    if "status" in overrides:
        overrides["initial_status"] = overrides.pop("status")
    defaults.update(overrides)
    return kb.create_task(conn, **defaults)


# ---------------------------------------------------------------------------
# Healthy board
# ---------------------------------------------------------------------------


def test_healthy_empty_board(kanban_home):
    """An empty board should report as healthy."""
    conn = kb.connect()
    try:
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["healthy"] is True
    assert report["counts"]["total_non_archived"] == 0
    assert report["counts"]["blocked_genuinely_stuck"] == 0
    assert report["counts"]["blocked_waiting_by_design"] == 0
    assert report["counts"]["blocked_review_required"] == 0
    assert report["deadlocks"] == []
    assert report["layer1_warnings"] == []
    assert report["oldest_stalled"]["task_id"] is None


def test_healthy_board_with_running_tasks(kanban_home):
    """A board with only ready/done tasks is healthy."""
    conn = kb.connect()
    try:
        t1 = _create_task(conn, title="ready task", assignee="w")
        t2 = _create_task(conn, title="done task", assignee="w")
        kb.complete_task(conn, t2, summary="finished")
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["healthy"] is True
    assert report["counts"]["by_status"]["ready"] == 1
    assert report["counts"]["by_status"]["done"] == 1


# ---------------------------------------------------------------------------
# Blocked classification
# ---------------------------------------------------------------------------


def test_review_required_detected(kanban_home):
    """A blocked task with reason 'review-required: ...' is classified correctly."""
    conn = kb.connect()
    try:
        tid = _create_task(conn, title="need review", assignee="athena")
        kb.block_task(conn, tid, reason="review-required: code needs eyes")
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["counts"]["blocked_review_required"] == 1
    assert report["counts"]["blocked_genuinely_stuck"] == 0
    assert report["counts"]["blocked_waiting_by_design"] == 0
    assert report["bottleneck"]["profile"] == "athena"
    assert report["bottleneck"]["review_required_count"] == 1


def test_waiting_by_design_detected(kanban_home):
    """A blocked task with reason starting 'waiting' is waiting-by-design."""
    conn = kb.connect()
    try:
        tid = _create_task(conn, title="waiting", assignee="w")
        kb.block_task(conn, tid, reason="waiting for upstream deployment")
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["counts"]["blocked_waiting_by_design"] == 1
    assert report["counts"]["blocked_genuinely_stuck"] == 0
    assert report["counts"]["blocked_review_required"] == 0


def test_scheduled_is_waiting_by_design(kanban_home):
    """A task in 'scheduled' status is waiting-by-design."""
    conn = kb.connect()
    try:
        tid = _create_task(conn, title="sched task", assignee="w")
        kb.schedule_task(conn, tid, reason="scheduled for later")
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["counts"]["blocked_waiting_by_design"] >= 1


def test_genuinely_stuck_detected(kanban_home):
    """A blocked task with a generic reason (not review, not waiting) is stuck."""
    conn = kb.connect()
    try:
        tid = _create_task(conn, title="stuck", assignee="w")
        kb.block_task(conn, tid, reason="needs investigation")
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["counts"]["blocked_genuinely_stuck"] == 1
    assert report["counts"]["blocked_waiting_by_design"] == 0
    assert report["counts"]["blocked_review_required"] == 0
    assert report["healthy"] is False


def test_blocked_no_reason_is_waiting_by_design(kanban_home):
    """A blocked task with no explicit reason (parent-dep blocked) is
    waiting-by-design — not stuck."""
    conn = kb.connect()
    try:
        tid = _create_task(conn, title="blocked no reason", assignee="w")
        kb.block_task(conn, tid, reason="")  # running -> blocked with empty reason
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    # Empty reason → defaults to waiting by design (parent-dep wait).
    assert report["counts"]["blocked_waiting_by_design"] >= 1


# ---------------------------------------------------------------------------
# Bottleneck detection
# ---------------------------------------------------------------------------


def test_bottleneck_profile_with_most_reviews(kanban_home):
    """The profile with the most review-required items is the bottleneck."""
    conn = kb.connect()
    try:
        t1 = _create_task(conn, title="rev1", assignee="athena")
        t2 = _create_task(conn, title="rev2", assignee="athena")
        t3 = _create_task(conn, title="rev3", assignee="zeus")
        kb.block_task(conn, t1, reason="review-required: code")
        kb.block_task(conn, t2, reason="review-required: arch")
        kb.block_task(conn, t3, reason="review-required: infra")
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["bottleneck"]["profile"] == "athena"
    assert report["bottleneck"]["review_required_count"] == 2
    assert report["bottleneck"]["review_required_by_profile"]["athena"] == 2
    assert report["bottleneck"]["review_required_by_profile"]["zeus"] == 1


# ---------------------------------------------------------------------------
# Oldest stalled task
# ---------------------------------------------------------------------------


def test_oldest_stalled_task(kanban_home):
    """The oldest blocked/ready task is reported."""
    conn = kb.connect()
    try:
        now = int(time.time())
        # Create a task that's been ready for 2 hours.
        old_tid = _create_task(conn, title="old task", assignee="w")
        # Manually set created_at to 2h ago.
        conn.execute(
            "UPDATE tasks SET created_at = ?, status = 'ready' WHERE id = ?",
            (now - 7200, old_tid),
        )
        conn.commit()
        # Create a newer blocked task.
        new_tid = _create_task(conn, title="new task", assignee="w")
        kb.block_task(conn, new_tid, reason="stuck")
        report = kdoc.board_doctor(conn, now=now)
    finally:
        conn.close()
    assert report["oldest_stalled"]["task_id"] == old_tid
    assert report["oldest_stalled"]["age_seconds"] >= 7200
    assert report["oldest_stalled"]["status"] == "ready"


# ---------------------------------------------------------------------------
# Deadlock detection
# ---------------------------------------------------------------------------


def test_no_deadlocks_on_clean_graph(kanban_home):
    """A graph with no cycles reports no deadlocks."""
    conn = kb.connect()
    try:
        p = _create_task(conn, title="parent", assignee="w")
        c = _create_task(conn, title="child", assignee="w")
        kb.link_tasks(conn, p, c)
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["deadlocks"] == []


def test_deadlock_detected_on_cycle(kanban_home):
    """A cycle in task_links is detected.

    link_tasks() itself prevents cycles, but the doctor should detect them
    if they exist (e.g., from raw SQL, race conditions, or migration).
    We insert directly into task_links to bypass the guard.
    """
    conn = kb.connect()
    try:
        a = _create_task(conn, title="A", assignee="w")
        b = _create_task(conn, title="B", assignee="w")
        c = _create_task(conn, title="C", assignee="w")
        # a -> b -> c (legal chain)
        kb.link_tasks(conn, a, b)
        kb.link_tasks(conn, b, c)
        # c -> a (would create cycle — insert raw to bypass _would_cycle guard)
        conn.execute(
            "INSERT INTO task_links (parent_id, child_id) VALUES (?, ?)",
            (c, a),
        )
        conn.commit()
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert len(report["deadlocks"]) >= 1
    assert any(a in d["cycle"] for d in report["deadlocks"])


# ---------------------------------------------------------------------------
# Layer 1 warnings
# ---------------------------------------------------------------------------


def test_layer1_warnings_from_diagnostics(kanban_home):
    """Tasks with active diagnostics show up as Layer 1 warnings."""
    conn = kb.connect()
    try:
        # Create a task (will be in 'ready' status since no parents).
        tid = _create_task(conn, title="failing", assignee="w")
        # Set consecutive_failures high enough to trigger repeated_failures.
        conn.execute(
            "UPDATE tasks SET consecutive_failures = 5, "
            "last_failure_error = 'Profile not found' WHERE id = ?",
            (tid,),
        )
        conn.commit()
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    # Should have at least one warning.
    assert len(report["layer1_warnings"]) >= 1
    w = report["layer1_warnings"][0]
    assert "repeated_failures" in [d["kind"] for d in w["diagnostics"]]


# ---------------------------------------------------------------------------
# Heal log (Layer 2)
# ---------------------------------------------------------------------------


def test_heal_log_empty_when_l2_not_deployed(kanban_home):
    """When self_heal_events table doesn't exist, heal log is empty."""
    conn = kb.connect()
    try:
        report = kdoc.board_doctor(conn)
    finally:
        conn.close()
    assert report["heal_log_24h"] == []


def test_heal_log_reads_from_self_heal_events(kanban_home):
    """When self_heal_events exists and has rows, they show up."""
    conn = kb.connect()
    try:
        now = int(time.time())
        # Create the self_heal_events table (Layer 2 contract).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS self_heal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO self_heal_events (task_id, action, detail, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("t_abc12345", "auto_route_reviewer", "rerouted athena -> zeus", now - 100),
        )
        conn.commit()
        report = kdoc.board_doctor(conn, now=now)
    finally:
        conn.close()
    assert len(report["heal_log_24h"]) == 1
    entry = report["heal_log_24h"][0]
    assert entry["action"] == "auto_route_reviewer"
    assert entry["task_id"] == "t_abc12345"


def test_heal_log_excludes_entries_older_than_24h(kanban_home):
    """Entries older than 24h are excluded from the heal log."""
    conn = kb.connect()
    try:
        now = int(time.time())
        conn.execute("""
            CREATE TABLE IF NOT EXISTS self_heal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        # Recent entry.
        conn.execute(
            "INSERT INTO self_heal_events (task_id, action, detail, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("t_recent123", "auto_route_reviewer", "recent", now - 100),
        )
        # Old entry (2 days ago).
        conn.execute(
            "INSERT INTO self_heal_events (task_id, action, detail, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("t_old123456", "auto_archive_junk", "old", now - 200000),
        )
        conn.commit()
        report = kdoc.board_doctor(conn, now=now)
    finally:
        conn.close()
    assert len(report["heal_log_24h"]) == 1
    assert report["heal_log_24h"][0]["task_id"] == "t_recent123"


# ---------------------------------------------------------------------------
# JSON output via CLI
# ---------------------------------------------------------------------------


def test_doctor_json_output(kanban_home):
    """The --json flag produces valid JSON from the CLI."""
    import subprocess
    result = subprocess.run(
        ["hermes", "kanban", "doctor", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "healthy" in data
    assert "counts" in data
    assert "bottleneck" in data
    assert "deadlocks" in data
    assert "layer1_warnings" in data
    assert "heal_log_24h" in data


def test_doctor_human_output_healthy(kanban_home):
    """The human-readable output includes 'Board healthy' when healthy."""
    import subprocess
    result = subprocess.run(
        ["hermes", "kanban", "doctor"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "Board" in result.stdout


def test_doctor_always_exits_0(kanban_home):
    """Doctor always exits 0 even on an unhealthy board (watchdog contract)."""
    conn = kb.connect()
    try:
        tid = _create_task(conn, title="stuck", assignee="w")
        kb.block_task(conn, tid, reason="broken")
    finally:
        conn.close()

    import subprocess
    result = subprocess.run(
        ["hermes", "kanban", "doctor", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(result.stdout)
    assert data["healthy"] is False
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# --board flag
# ---------------------------------------------------------------------------


def test_doctor_board_flag(monkeypatch, tmp_path):
    """Doctor respects the --board flag for multi-project boards."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    import subprocess
    # Create a new board.
    result = subprocess.run(
        ["hermes", "kanban", "boards", "create", "testboard"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0

    # Doctor on that board should work.
    result = subprocess.run(
        ["hermes", "kanban", "doctor", "--board", "testboard", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["counts"]["total_non_archived"] == 0
    assert data["healthy"] is True

"""Tests for Kanban DB rerun_task (commit 97c6f4e42 coverage)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


# ---------------------------------------------------------------------------
# Basic: terminal statuses → ready
# ---------------------------------------------------------------------------

def test_rerun_completed_task_resets_to_ready(kanban_home):
    """rerun_task on a completed task resets status to ready."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="done-task", assignee="worker")
        kb.claim_task(conn, t)
    with kb.connect() as conn:
        assert kb.complete_task(conn, t, result="all good")
        assert kb.get_task(conn, t).status == "done"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)
        task = kb.get_task(conn, t)

    assert task.status == "ready"
    assert task.completed_at is None
    assert task.started_at is None
    assert task.claim_lock is None
    assert task.claim_expires is None
    assert task.worker_pid is None
    assert task.consecutive_failures == 0
    assert task.last_failure_error is None
    assert task.current_run_id is None


def test_rerun_blocked_task_resets_to_ready(kanban_home):
    """rerun_task on a blocked task resets status to ready."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="blocked-task", assignee="worker")
        kb.claim_task(conn, t)
        assert kb.block_task(conn, t, reason="need input")
        assert kb.get_task(conn, t).status == "blocked"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)
        task = kb.get_task(conn, t)

    assert task.status == "ready"


def test_rerun_archived_task_resets_to_ready(kanban_home):
    """rerun_task on an archived task resets status to ready."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="archived-task", assignee="worker")
        kb.claim_task(conn, t)
        assert kb.complete_task(conn, t, result="ok")
        assert kb.archive_task(conn, t)
        assert kb.get_task(conn, t).status == "archived"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)
        task = kb.get_task(conn, t)

    assert task.status == "ready"


# ---------------------------------------------------------------------------
# Edge cases: non-rerunnable inputs
# ---------------------------------------------------------------------------

def test_rerun_non_terminal_status_returns_false(kanban_home):
    """rerun_task returns False for running / ready / todo tasks."""
    with kb.connect() as conn:
        # Create and test a fresh ready task first
        t_ready = kb.create_task(conn, title="fresh-ready", assignee="w")
        assert not kb.rerun_task(conn, t_ready), "Ready task should not be rerunnable"

        # Create a running task
        t_running = kb.create_task(conn, title="running-task", assignee="w")
        kb.claim_task(conn, t_running)
        assert kb.get_task(conn, t_running).status == "running"
        assert not kb.rerun_task(conn, t_running), "Running task should not be rerunnable"

        # Create a todo task (has undone parent)
        p = kb.create_task(conn, title="p-todo", assignee="w")
        t_todo = kb.create_task(conn, title="todo-task", parents=[p], assignee="w")
        assert kb.get_task(conn, t_todo).status == "todo"
        assert not kb.rerun_task(conn, t_todo), "Todo task should not be rerunnable"


def test_rerun_nonexistent_task_returns_false(kanban_home):
    """rerun_task returns False for a bogus task_id."""
    with kb.connect() as conn:
        assert not kb.rerun_task(conn, "t_nonexistent_999")


# ---------------------------------------------------------------------------
# Parent gate logic
# ---------------------------------------------------------------------------

def test_rerun_with_done_parents_goes_to_ready(kanban_home):
    """When all parents are done, rerun promotes to ready."""
    with kb.connect() as conn:
        p = kb.create_task(conn, title="parent", assignee="w")
        kb.claim_task(conn, p)
        kb.complete_task(conn, p, result="ok")
        c = kb.create_task(conn, title="child", parents=[p], assignee="w")
        assert kb.get_task(conn, c).status == "ready"
        kb.claim_task(conn, c)
        kb.complete_task(conn, c, result="ok")
        assert kb.get_task(conn, c).status == "done"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, c)
        child = kb.get_task(conn, c)

    assert child.status == "ready"


def test_rerun_with_undone_parents_goes_to_todo(kanban_home):
    """When a parent is NOT done, rerun demotes to todo."""
    with kb.connect() as conn:
        p = kb.create_task(conn, title="parent-undone", assignee="w")
        c = kb.create_task(conn, title="child-undone", parents=[p], assignee="w")
        assert kb.get_task(conn, c).status == "todo"
        # Force child to done via direct update (simulate external completion)
        conn.execute(
            "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
            (c,),
        )
        conn.commit()
        assert kb.get_task(conn, c).status == "done"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, c)
        child = kb.get_task(conn, c)

    assert child.status == "todo"


def test_rerun_with_review_required_blocked_parent_counts_as_done(kanban_home):
    """Parent blocked with 'review-required' reason satisfies the gate."""
    with kb.connect() as conn:
        p = kb.create_task(conn, title="parent-review", assignee="w")
        kb.claim_task(conn, p)
        kb.block_task(conn, p, reason="review-required: needs eyes on PR")
        c = kb.create_task(conn, title="child-review", parents=[p], assignee="w")
        assert kb.get_task(conn, c).status == "todo"
        # Force child to done via direct update
        conn.execute(
            "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
            (c,),
        )
        conn.commit()
        # Verify parent is blocked with review-required
        parent = kb.get_task(conn, p)
        assert parent.status == "blocked"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, c)
        child = kb.get_task(conn, c)

    assert child.status == "ready", (
        "Child with review-required blocked parent should be 'ready'"
    )


def test_rerun_with_non_review_blocked_parent_goes_to_todo(kanban_home):
    """Parent blocked with a non-review reason does NOT satisfy the gate."""
    with kb.connect() as conn:
        p = kb.create_task(conn, title="parent-blocked-other", assignee="w")
        kb.claim_task(conn, p)
        kb.block_task(conn, p, reason="waiting for API key")
        c = kb.create_task(
            conn, title="child-blocked-other", parents=[p], assignee="w"
        )
        # Force child to done
        conn.execute(
            "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
            (c,),
        )
        conn.commit()

    with kb.connect() as conn:
        assert kb.rerun_task(conn, c)
        child = kb.get_task(conn, c)

    assert child.status == "todo", (
        "Child with non-review blocked parent should be 'todo'"
    )


# ---------------------------------------------------------------------------
# Notification subscription retention
# ---------------------------------------------------------------------------

def test_rerun_preserves_notification_subscription(kanban_home):
    """Notification subs persist across rerun — last_event_id is refreshed."""
    with kb.connect() as conn:
        t = kb.create_task(
            conn,
            title="sub-task",
            assignee="worker",
            subscribe={"platform": "telegram", "chat_id": "123"},
        )
        kb.claim_task(conn, t)
        kb.complete_task(conn, t, result="ok")

        # Capture the sub row before rerun
        subs_before = kb.list_notify_subs(conn, task_id=t)
        assert len(subs_before) == 1
        assert subs_before[0]["platform"] == "telegram"
        assert subs_before[0]["chat_id"] == "123"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)

        # Subscription must still exist
        subs_after = kb.list_notify_subs(conn, task_id=t)
        assert len(subs_after) == 1, "Subscription should survive rerun"
        assert subs_after[0]["platform"] == "telegram"
        assert subs_after[0]["chat_id"] == "123"
        assert subs_after[0]["task_id"] == t


# ---------------------------------------------------------------------------
# Claim + failure state clearing
# ---------------------------------------------------------------------------

def test_rerun_clears_claim_and_failure_state(kanban_home):
    """rerun_task zeros out consecutive_failures and last_failure_error."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="failure-task", assignee="worker")
        kb.claim_task(conn, t)
        kb.complete_task(conn, t, result="ok")

        # Inject artificial failure state
        conn.execute(
            "UPDATE tasks SET consecutive_failures = 3, "
            "last_failure_error = 'something broke' WHERE id = ?",
            (t,),
        )
        conn.commit()
        task_before = kb.get_task(conn, t)
        assert task_before.consecutive_failures == 3
        assert task_before.last_failure_error == "something broke"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)
        task = kb.get_task(conn, t)

    assert task.consecutive_failures == 0
    assert task.last_failure_error is None


# ---------------------------------------------------------------------------
# Assignee override
# ---------------------------------------------------------------------------

def test_rerun_with_new_assignee(kanban_home):
    """rerun_task accepts an optional new_assignee."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="reassign-task", assignee="alice")
        kb.claim_task(conn, t)
        kb.complete_task(conn, t, result="done")

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t, new_assignee="bob")
        task = kb.get_task(conn, t)

    assert task.status == "ready"
    assert task.assignee == "bob"


def test_rerun_keeps_original_assignee_when_new_not_given(kanban_home):
    """rerun_task preserves the original assignee when new_assignee is None."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="keep-assignee", assignee="alice")
        kb.claim_task(conn, t)
        kb.complete_task(conn, t, result="done")

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)
        task = kb.get_task(conn, t)

    assert task.status == "ready"
    assert task.assignee == "alice"


# ---------------------------------------------------------------------------
# Event recording
# ---------------------------------------------------------------------------

def test_rerun_records_event(kanban_home):
    """rerun_task emits a 'rerun' event with reason and status."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="event-task", assignee="worker")
        kb.claim_task(conn, t)
        kb.complete_task(conn, t, result="done")

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t, reason="retry after upstream fix")

        events = conn.execute(
            "SELECT kind, payload FROM task_events WHERE task_id = ? ORDER BY id",
            (t,),
        ).fetchall()

    kinds = [e["kind"] for e in events]
    assert "rerun" in kinds, f"Expected 'rerun' event in {kinds}"

    rerun_event = next(e for e in events if e["kind"] == "rerun")
    import json

    payload = json.loads(rerun_event["payload"])
    assert payload["reason"] == "retry after upstream fix"
    assert payload["status"] == "ready"
    assert payload["assignee"] == "worker"


# ---------------------------------------------------------------------------
# Multiple parents (fan-in)
# ---------------------------------------------------------------------------

def test_rerun_fan_in_all_done_goes_to_ready(kanban_home):
    """Fan-in: rerun goes to ready only when ALL parents are done."""
    with kb.connect() as conn:
        p1 = kb.create_task(conn, title="p1", assignee="w")
        p2 = kb.create_task(conn, title="p2", assignee="w")
        kb.claim_task(conn, p1)
        kb.complete_task(conn, p1, result="ok")
        kb.claim_task(conn, p2)
        kb.complete_task(conn, p2, result="ok")

        c = kb.create_task(conn, title="fanin-child", parents=[p1, p2], assignee="w")
        assert kb.get_task(conn, c).status == "ready"
        kb.claim_task(conn, c)
        kb.complete_task(conn, c, result="ok")
        assert kb.get_task(conn, c).status == "done"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, c)
        child = kb.get_task(conn, c)

    assert child.status == "ready"


def test_rerun_fan_in_one_undone_goes_to_todo(kanban_home):
    """Fan-in: rerun goes to todo when ANY parent is undone."""
    with kb.connect() as conn:
        p1 = kb.create_task(conn, title="p1-done", assignee="w")
        kb.claim_task(conn, p1)
        kb.complete_task(conn, p1, result="ok")

        p2 = kb.create_task(conn, title="p2-undone", assignee="w")

        c = kb.create_task(
            conn, title="fanin-partial", parents=[p1, p2], assignee="w"
        )
        conn.execute(
            "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
            (c,),
        )
        conn.commit()

    with kb.connect() as conn:
        assert kb.rerun_task(conn, c)
        child = kb.get_task(conn, c)

    assert child.status == "todo"


# ---------------------------------------------------------------------------
# Invariant: stale current_run_id cleaned up
# ---------------------------------------------------------------------------

def test_rerun_cleans_stale_current_run_id(kanban_home):
    """If a terminal task somehow has current_run_id set, rerun cleans it."""
    with kb.connect() as conn:
        t = kb.create_task(conn, title="leaky-task", assignee="worker")
        kb.claim_task(conn, t)
        # Inject a synthetic run so there's a current_run_id
        run_id = conn.execute(
            "INSERT INTO task_runs (task_id, profile, status, started_at) "
            "VALUES (?, 'worker', 'running', ?)",
            (t, int(__import__("time").time())),
        ).lastrowid
        conn.execute("UPDATE tasks SET current_run_id = ? WHERE id = ?", (run_id, t))
        conn.commit()
        # Now complete the task — but current_run_id persists (this is the "leak")
        conn.execute(
            "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
            (t,),
        )
        conn.commit()
        task_before = kb.get_task(conn, t)
        assert task_before.current_run_id is not None, "Precondition: leaked run id"

    with kb.connect() as conn:
        assert kb.rerun_task(conn, t)
        task = kb.get_task(conn, t)

    assert task.current_run_id is None, "Rerun must clear stale current_run_id"

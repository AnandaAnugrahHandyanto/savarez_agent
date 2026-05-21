from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(kb.SCHEMA_SQL)
    kb._migrate_add_optional_columns(conn)
    try:
        yield conn
    finally:
        conn.close()


def test_parent_scratch_survives_until_child_done(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "parent-scratch"
    workspace.mkdir()

    parent = kb.create_task(
        kanban_conn,
        title="parent",
        assignee="lead",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )
    child = kb.create_task(
        kanban_conn,
        title="child",
        assignee="worker",
        parents=[parent],
    )

    assert kb.complete_task(kanban_conn, parent, result="parent complete")
    assert kb.get_task(kanban_conn, child).status == "ready"
    assert workspace.is_dir()


def test_parent_scratch_cleaned_after_last_child_done(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "parent-scratch-last-child"
    workspace.mkdir()

    parent = kb.create_task(
        kanban_conn,
        title="parent",
        assignee="lead",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )
    child = kb.create_task(
        kanban_conn,
        title="child",
        assignee="worker",
        parents=[parent],
    )

    assert kb.complete_task(kanban_conn, parent, result="parent complete")
    assert workspace.is_dir()
    assert kb.complete_task(kanban_conn, child, result="child complete")
    assert not workspace.exists()


# ---------------------------------------------------------------------------
# Multi-child deferred cleanup (commit 03e231971)
# ---------------------------------------------------------------------------

def test_parent_survives_when_one_of_many_children_still_active(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """Parent scratch workspace survives when at least one child is active."""
    workspace = tmp_path / "parent-multi-child-active"
    workspace.mkdir()

    parent = kb.create_task(
        kanban_conn,
        title="orchestrator",
        assignee="lead",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )
    child_a = kb.create_task(
        kanban_conn,
        title="worker-a",
        assignee="alice",
        parents=[parent],
    )
    child_b = kb.create_task(
        kanban_conn,
        title="worker-b",
        assignee="bob",
        parents=[parent],
    )
    child_c = kb.create_task(
        kanban_conn,
        title="worker-c",
        assignee="carol",
        parents=[parent],
    )

    assert kb.complete_task(kanban_conn, parent, result="orchestration done")

    # Complete child A and C, but leave B in todo (still active)
    conn = kanban_conn
    conn.execute(
        "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
        (child_a,),
    )
    conn.commit()
    conn.execute(
        "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
        (child_c,),
    )
    conn.commit()

    # Simulate completing A (calls _cleanup_workspace on parent)
    # A is done → parent cleanup deferred because B is still active
    assert workspace.is_dir(), "Workspace must survive with active child B"

    # Now complete child B — last active child
    conn.execute(
        "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
        (child_b,),
    )
    conn.commit()
    # Simulate completing B → triggers parent cleanup
    kb._cleanup_workspace(kanban_conn, parent)

    assert not workspace.exists(), "Workspace cleaned after last child done"


def test_parent_cleaned_when_all_children_done(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """Parent scratch workspace is removed when ALL children are done."""
    workspace = tmp_path / "parent-all-children-done"
    workspace.mkdir()

    parent = kb.create_task(
        kanban_conn,
        title="orchestrator",
        assignee="lead",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )
    child_a = kb.create_task(
        kanban_conn,
        title="worker-a",
        assignee="alice",
        parents=[parent],
    )
    child_b = kb.create_task(
        kanban_conn,
        title="worker-b",
        assignee="bob",
        parents=[parent],
    )

    assert kb.complete_task(kanban_conn, parent, result="orchestration done")

    # Mark both children as done
    conn = kanban_conn
    conn.execute(
        "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
        (child_a,),
    )
    conn.commit()
    conn.execute(
        "UPDATE tasks SET status='done', started_at=0, completed_at=0 WHERE id=?",
        (child_b,),
    )
    conn.commit()

    # Simulate completing last child → parent cleanup
    kb._cleanup_workspace(kanban_conn, parent)

    assert not workspace.exists(), "Workspace cleaned when all children done"


def test_parent_survives_child_in_archived_state(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """Archived children do NOT count as active — parent can be cleaned."""
    workspace = tmp_path / "parent-archived-child"
    workspace.mkdir()

    parent = kb.create_task(
        kanban_conn,
        title="orchestrator",
        assignee="lead",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )
    child = kb.create_task(
        kanban_conn,
        title="worker",
        assignee="alice",
        parents=[parent],
    )

    assert kb.complete_task(kanban_conn, parent, result="orchestration done")

    # Archive the child (archived = terminal, not active)
    conn = kanban_conn
    conn.execute(
        "UPDATE tasks SET status='archived', started_at=0, completed_at=0 WHERE id=?",
        (child,),
    )
    conn.commit()

    kb._cleanup_workspace(kanban_conn, parent)
    assert not workspace.exists(), "Workspace cleaned when child is archived"


def test_parent_survives_child_in_gave_up_state(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """Children in 'gave_up' status do NOT count as active."""
    workspace = tmp_path / "parent-gave-up-child"
    workspace.mkdir()

    parent = kb.create_task(
        kanban_conn,
        title="orchestrator",
        assignee="lead",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )
    child = kb.create_task(
        kanban_conn,
        title="worker",
        assignee="alice",
        parents=[parent],
    )

    assert kb.complete_task(kanban_conn, parent, result="orchestration done")

    conn = kanban_conn
    conn.execute(
        "UPDATE tasks SET status='gave_up', started_at=0, completed_at=0 WHERE id=?",
        (child,),
    )
    conn.commit()

    kb._cleanup_workspace(kanban_conn, parent)
    assert not workspace.exists(), "Workspace cleaned when child gave up"


def test_dir_workspace_not_cleaned(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """``dir`` workspaces are never cleaned — only ``scratch``."""
    workspace = tmp_path / "persistent-workspace"
    workspace.mkdir()
    marker = workspace / "important.txt"
    marker.write_text("preserve me")

    parent = kb.create_task(
        kanban_conn,
        title="persistent-parent",
        assignee="lead",
        workspace_kind="dir",
        workspace_path=str(workspace),
    )

    assert kb.complete_task(kanban_conn, parent, result="done")
    kb._cleanup_workspace(kanban_conn, parent)

    assert workspace.is_dir(), "dir workspace must survive"
    assert marker.read_text() == "preserve me"


def test_scratch_cleanup_no_active_children(
    kanban_conn: sqlite3.Connection,
    tmp_path: Path,
) -> None:
    """Scratch workspace cleaned immediately when there are no children."""
    workspace = tmp_path / "solo-scratch"
    workspace.mkdir()

    task = kb.create_task(
        kanban_conn,
        title="solo-task",
        assignee="worker",
        workspace_kind="scratch",
        workspace_path=str(workspace),
    )

    assert kb.complete_task(kanban_conn, task, result="done")
    assert not workspace.exists(), "Solo scratch workspace cleaned on completion"

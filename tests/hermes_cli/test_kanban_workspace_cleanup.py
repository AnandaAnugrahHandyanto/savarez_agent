"""Tests for _cleanup_workspace safety guard (issue #30151).

Verifies that _cleanup_workspace refuses to delete paths outside workspaces_root
while still cleaning up legitimate scratch workspaces normally.
"""

from __future__ import annotations

import os
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
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_HOME", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_WORKSPACES_ROOT", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)
    kb.init_db()
    return home


def _create_scratch_task(conn, workspace_path, task_id=None):
    """Insert a scratch task with a given workspace_path into the DB."""
    if task_id is None:
        task_id = "t_deadbeef0001"
    import time
    conn.execute(
        "INSERT INTO tasks "
        "(id, title, status, workspace_kind, workspace_path, created_at, created_by) "
        "VALUES (?, ?, 'running', 'scratch', ?, ?, 'test')",
        (task_id, f"Test task {task_id}", str(workspace_path), int(time.time())),
    )
    conn.commit()
    return task_id


class TestCleanupWorkspaceSafetyGuard:
    """_cleanup_workspace must refuse paths outside workspaces_root."""

    def test_normal_workspace_inside_root_is_deleted(self, kanban_home, tmp_path):
        """A scratch workspace inside workspaces_root is deleted normally."""
        ws_root = kb.workspaces_root()
        ws_root.mkdir(parents=True, exist_ok=True)
        task_ws = ws_root / "t_deadbeef0001"
        task_ws.mkdir()
        (task_ws / "file.txt").write_text("data")

        with kb.connect() as conn:
            task_id = _create_scratch_task(conn, task_ws)
            kb._cleanup_workspace(conn, task_id)

        assert not task_ws.exists(), "workspace inside workspaces_root should be deleted"

    def test_workspace_outside_root_is_not_deleted(self, kanban_home, tmp_path):
        """A workspace path outside workspaces_root must NOT be deleted."""
        # Create a directory outside workspaces_root
        outside_dir = tmp_path / "my-precious-projects"
        outside_dir.mkdir()
        (outside_dir / "important.py").write_text("print('do not delete me')")

        with kb.connect() as conn:
            task_id = _create_scratch_task(conn, outside_dir)
            kb._cleanup_workspace(conn, task_id)

        assert outside_dir.exists(), "workspace outside workspaces_root must NOT be deleted"
        assert (outside_dir / "important.py").exists(), "files inside must be preserved"

    def test_symlink_escaping_workspace_is_not_deleted(self, kanban_home, tmp_path):
        """A symlink inside workspaces_root pointing outside must not be followed for deletion."""
        ws_root = kb.workspaces_root()
        ws_root.mkdir(parents=True, exist_ok=True)

        # Real target outside workspaces_root
        outside_dir = tmp_path / "external-target"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("classified")

        # Symlink inside workspaces_root pointing to the outside dir
        link_path = ws_root / "t_symlink_escape"
        link_path.symlink_to(outside_dir)

        with kb.connect() as conn:
            task_id = _create_scratch_task(conn, link_path)
            kb._cleanup_workspace(conn, task_id)

        # The symlink itself resolves to outside workspaces_root, so it
        # should be refused. The real target must remain intact.
        # (resolve() follows symlinks, so the resolved path is outside root)
        assert outside_dir.exists(), "symlink target outside root must NOT be deleted"
        assert (outside_dir / "secret.txt").exists()

    def test_path_traversal_attempt_is_not_deleted(self, kanban_home, tmp_path):
        """Relative path traversal (../../etc) must not escape workspaces_root."""
        ws_root = kb.workspaces_root()
        ws_root.mkdir(parents=True, exist_ok=True)

        # Create a directory that would be hit by traversal
        target_dir = tmp_path / "traversal-target"
        target_dir.mkdir()
        (target_dir / "safe.txt").write_text("untouched")

        # Build a path with traversal from inside workspaces_root
        traversal_path = ws_root / ".." / ".." / ".." / tmp_path.name / "traversal-target"

        with kb.connect() as conn:
            task_id = _create_scratch_task(conn, traversal_path)
            kb._cleanup_workspace(conn, task_id)

        assert target_dir.exists(), "traversal target must NOT be deleted"
        assert (target_dir / "safe.txt").exists()

    def test_nonexistent_task_is_noop(self, kanban_home):
        """Calling _cleanup_workspace with a nonexistent task_id is a no-op."""
        with kb.connect() as conn:
            # Should not raise
            kb._cleanup_workspace(conn, "t_nonexistent0000")

    def test_non_scratch_workspace_is_not_deleted(self, kanban_home, tmp_path):
        """A 'worktree' or 'dir' workspace must never be deleted regardless of path."""
        ws_root = kb.workspaces_root()
        ws_root.mkdir(parents=True, exist_ok=True)
        task_ws = ws_root / "t_worktree_task"
        task_ws.mkdir()
        (task_ws / "code.py").write_text("print('keep')")

        import time
        with kb.connect() as conn:
            conn.execute(
                "INSERT INTO tasks "
                "(id, title, status, workspace_kind, workspace_path, created_at, created_by) "
                "VALUES (?, ?, 'running', 'worktree', ?, ?, 'test')",
                ("t_worktree01", "Worktree task", str(task_ws), int(time.time())),
            )
            conn.commit()
            kb._cleanup_workspace(conn, "t_worktree01")

        assert task_ws.exists(), "worktree workspace must not be deleted"
        assert (task_ws / "code.py").exists()

    def test_is_safe_workspace_path_helper(self):
        """Unit tests for _is_safe_workspace_path."""
        root = Path("/tmp/hermes-home/kanban/workspaces").resolve()

        # Inside root
        assert kb._is_safe_workspace_path(
            Path("/tmp/hermes-home/kanban/workspaces/task1").resolve(), root
        )

        # Outside root
        assert not kb._is_safe_workspace_path(
            Path("/tmp/hermes-home/projects").resolve(), root
        )

        # Root itself is safe (relative_to succeeds)
        assert kb._is_safe_workspace_path(root, root)

        # Same prefix but different directory (not a child)
        assert not kb._is_safe_workspace_path(
            Path("/tmp/hermes-home/kanban/workspaces-other").resolve(), root
        )

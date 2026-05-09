from pathlib import Path

from hermes_cli.kanban_cleanup import (
    CleanupDecision,
    ProcessInfo,
    WorktreeInfo,
    classify_workspace_dir_for_cleanup,
    classify_worktree_for_cleanup,
)
from hermes_cli.kanban_policy import BoardPolicy


def test_classify_clean_secondary_worktree_safe(tmp_path):
    project = tmp_path / "Project"
    policy = BoardPolicy(board="demo", project_root=project, worktree_root=project / ".worktrees")
    info = WorktreeInfo(path=project / ".worktrees" / "task-1", main=False, dirty=False)

    decision = classify_worktree_for_cleanup(info, policy, [])

    assert decision.action == "safe_remove"


def test_classify_dirty_worktree_blocked(tmp_path):
    project = tmp_path / "Project"
    policy = BoardPolicy(board="demo", project_root=project, worktree_root=project / ".worktrees")
    info = WorktreeInfo(path=project / ".worktrees" / "task-1", main=False, dirty=True)

    decision = classify_worktree_for_cleanup(info, policy, [])

    assert decision.action == "blocked_dirty"


def test_classify_active_worktree_blocked(tmp_path):
    project = tmp_path / "Project"
    wt = project / ".worktrees" / "task-1"
    policy = BoardPolicy(board="demo", project_root=project, worktree_root=project / ".worktrees")
    info = WorktreeInfo(path=wt, main=False, dirty=False)

    decision = classify_worktree_for_cleanup(info, policy, [ProcessInfo(pid=123, command=f"pnpm dev {wt}")])

    assert decision.action == "blocked_active"


def test_classify_main_checkout_protected(tmp_path):
    project = tmp_path / "Project"
    policy = BoardPolicy(board="demo", project_root=project, worktree_root=project / ".worktrees")
    info = WorktreeInfo(path=project, main=True, dirty=False)

    decision = classify_worktree_for_cleanup(info, policy, [])

    assert decision.action == "protected_main"


def test_classify_scratch_dir_safe_when_inactive(tmp_path):
    project = tmp_path / "Project"
    scratch = tmp_path / ".hermes" / "kanban" / "boards" / "demo" / "workspaces" / "t1"
    policy = BoardPolicy(board="demo", project_root=project, worktree_root=project / ".worktrees")

    decision = classify_workspace_dir_for_cleanup(scratch, policy, [])

    assert decision.action == "safe_remove_scratch"

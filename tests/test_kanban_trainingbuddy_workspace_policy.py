from __future__ import annotations

from types import SimpleNamespace

from hermes_cli.kanban_validation import validate_tasks


def _task(**overrides):
    data = {
        "id": "t_bad",
        "title": "Fix GitHub issue #95: protected layout redirect",
        "body": "TrainingBuddy repo change for issue #95. VC-001: redirect unauthenticated users.",
        "assignee": "fullstack-eng",
        "status": "ready",
        "workspace_kind": "worktree",
        "workspace_path": "/home/it/.hermes/kanban/boards/trainingbuddy/workspaces/t_bad/TrainingBuddy",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_trainingbuddy_worktree_outside_project_worktrees_is_error():
    findings = validate_tasks([_task()])
    codes = {f.code for f in findings}
    assert "worktree_outside_project_root" in codes


def test_trainingbuddy_shared_project_root_worktree_is_error():
    findings = validate_tasks([_task(workspace_path="/home/it/Projects/TrainingBuddy")])
    codes = {f.code for f in findings}
    assert "shared_project_root_workspace" in codes


def test_trainingbuddy_project_local_worktree_is_allowed():
    findings = validate_tasks([
        _task(workspace_path="/home/it/Projects/TrainingBuddy/.worktrees/issue-95-protected-layout")
    ])
    codes = {f.code for f in findings}
    assert "worktree_outside_project_root" not in codes
    assert "shared_project_root_workspace" not in codes
    assert "missing_explicit_project_worktree" not in codes

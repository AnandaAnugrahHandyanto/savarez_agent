"""Inventory, cleanup, and teardown helpers for Kanban boards.

The functions here intentionally separate classification from deletion so tests
can exercise safety decisions without touching real worktrees or processes.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hermes_cli import kanban_db as kb
from hermes_cli.kanban_policy import BoardPolicy, load_policy


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    command: str


@dataclass(frozen=True)
class CleanupDecision:
    path: str
    action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str = ""
    head: str = ""
    main: bool = False
    dirty: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "branch": self.branch,
            "head": self.head,
            "main": self.main,
            "dirty": self.dirty,
        }


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def list_registered_worktrees(project_root: Path | None) -> list[WorktreeInfo]:
    if project_root is None or not (project_root / ".git").exists():
        return []
    proc = _run(["git", "worktree", "list", "--porcelain"], cwd=project_root)
    if proc.returncode != 0:
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
        else:
            key, value = line, ""
        if key == "worktree" and current:
            entries.append(current)
            current = {}
        current[key] = value
    if current:
        entries.append(current)
    infos: list[WorktreeInfo] = []
    main_path = project_root.resolve(strict=False)
    for entry in entries:
        path = Path(entry.get("worktree", "")).expanduser().resolve(strict=False)
        dirty = False
        if path.exists():
            status = _run(["git", "status", "--short"], cwd=path)
            dirty = bool(status.stdout.strip()) if status.returncode == 0 else True
        infos.append(WorktreeInfo(
            path=path,
            branch=entry.get("branch", ""),
            head=entry.get("HEAD", ""),
            main=path == main_path,
            dirty=dirty,
        ))
    return infos


def find_relevant_processes(board: str, policy: BoardPolicy) -> list[ProcessInfo]:
    proc = _run(["ps", "-eo", "pid=,args="])
    if proc.returncode != 0:
        return []
    needles = [board.lower()]
    if policy.project_root:
        needles.append(str(policy.project_root).lower())
    if policy.worktree_root:
        needles.append(str(policy.worktree_root).lower())
    own_pid = os.getpid()
    infos: list[ProcessInfo] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_s, _, command = stripped.partition(" ")
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid == own_pid:
            continue
        lower = command.lower()
        if any(n and n in lower for n in needles) and "ps -eo" not in lower:
            infos.append(ProcessInfo(pid=pid, command=command))
    return infos


def classify_worktree_for_cleanup(info: WorktreeInfo, policy: BoardPolicy, processes: list[ProcessInfo]) -> CleanupDecision:
    path_s = str(info.path)
    if info.main or (policy.project_root and info.path == policy.project_root):
        return CleanupDecision(path_s, "protected_main", "main project checkout is never removed by cleanup")
    for proc in processes:
        if path_s in proc.command:
            return CleanupDecision(path_s, "blocked_active", f"active process pid={proc.pid}")
    if info.dirty:
        return CleanupDecision(path_s, "blocked_dirty", "worktree has uncommitted changes")
    return CleanupDecision(path_s, "safe_remove", "inactive clean secondary worktree")


def classify_workspace_dir_for_cleanup(path: Path, policy: BoardPolicy, processes: list[ProcessInfo]) -> CleanupDecision:
    path = path.resolve(strict=False)
    path_s = str(path)
    if policy.project_root and path == policy.project_root:
        return CleanupDecision(path_s, "protected_main", "main project checkout is never scratch junk")
    for proc in processes:
        if path_s in proc.command:
            return CleanupDecision(path_s, "blocked_active", f"active process pid={proc.pid}")
    return CleanupDecision(path_s, "safe_remove_scratch", "inactive board scratch/workspace directory")


def inventory_board(board: str, policy: BoardPolicy | None = None) -> dict[str, Any]:
    policy = policy or load_policy(board)
    board_path = kb.board_dir(board)
    workspace_root = kb.workspaces_root(board)
    worktrees = list_registered_worktrees(policy.project_root)
    processes = find_relevant_processes(board, policy)
    workspace_dirs = []
    if workspace_root.exists():
        workspace_dirs = [str(p) for p in sorted(workspace_root.iterdir())]
    return {
        "board": board,
        "policy": policy.to_dict(),
        "board_path": str(board_path),
        "board_exists": board_path.exists(),
        "registered_worktrees": [w.to_dict() for w in worktrees],
        "workspace_dirs": workspace_dirs,
        "processes": [asdict(p) for p in processes],
        "warnings": [],
    }


def stop_processes(processes: list[ProcessInfo], *, timeout: float = 1.0) -> list[int]:
    stopped: list[int] = []
    for proc in processes:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            stopped.append(proc.pid)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
    if stopped:
        time.sleep(timeout)
    for proc in processes:
        try:
            os.kill(proc.pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except Exception:
            pass
    return stopped


def cleanup_board(board: str, *, dry_run: bool = True) -> dict[str, Any]:
    policy = load_policy(board)
    processes = find_relevant_processes(board, policy)
    decisions = [classify_worktree_for_cleanup(w, policy, processes) for w in list_registered_worktrees(policy.project_root)]
    removed: list[str] = []
    if not dry_run:
        for decision in decisions:
            if decision.action == "safe_remove":
                _run(["git", "worktree", "remove", "--force", decision.path], cwd=policy.project_root)
                removed.append(decision.path)
        if policy.project_root:
            _run(["git", "worktree", "prune"], cwd=policy.project_root)
    return {"board": board, "dry_run": dry_run, "decisions": [d.to_dict() for d in decisions], "removed": removed}


def teardown_board(
    board: str,
    *,
    remove_all_worktrees: bool,
    delete_board: bool,
    yes: bool,
) -> dict[str, Any]:
    policy = load_policy(board)
    if not yes:
        return {
            "board": board,
            "verified": False,
            "refused": True,
            "reason": "destructive teardown requires --yes",
            "inventory": inventory_board(board, policy),
        }
    processes = find_relevant_processes(board, policy)
    stopped = stop_processes(processes)
    removed_worktrees: list[str] = []
    if remove_all_worktrees and policy.project_root:
        for wt in list_registered_worktrees(policy.project_root):
            if wt.main:
                continue
            _run(["git", "worktree", "remove", "--force", str(wt.path)], cwd=policy.project_root)
            removed_worktrees.append(str(wt.path))
        _run(["git", "worktree", "prune"], cwd=policy.project_root)
        if policy.worktree_root and policy.worktree_root.exists():
            shutil.rmtree(policy.worktree_root, ignore_errors=True)
    board_removed = False
    if delete_board:
        board_path = kb.board_dir(board)
        if board_path.exists():
            shutil.rmtree(board_path, ignore_errors=True)
        board_removed = not board_path.exists()
    remaining_worktrees = [w.to_dict() for w in list_registered_worktrees(policy.project_root) if not w.main]
    remaining_processes = [asdict(p) for p in find_relevant_processes(board, policy)]
    remaining_paths = []
    if delete_board and kb.board_dir(board).exists():
        remaining_paths.append(str(kb.board_dir(board)))
    if remove_all_worktrees and policy.worktree_root and policy.worktree_root.exists():
        remaining_paths.append(str(policy.worktree_root))
    return {
        "board": board,
        "processes_stopped": stopped,
        "worktrees_removed": removed_worktrees,
        "board_removed": board_removed,
        "remaining_worktrees": remaining_worktrees,
        "remaining_processes": remaining_processes,
        "remaining_paths": remaining_paths,
        "verified": not remaining_worktrees and not remaining_processes and not remaining_paths,
    }

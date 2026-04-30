"""Workspace-binding guards for side-effecting project tools.

The gateway can bind a chat/channel to an authoritative workspace repo.  Tool
side effects should not silently land in a different checkout just because the
model inferred project context from room names or stale memory.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Iterable, Optional


_MUTATING_GIT_SUBCOMMANDS = frozenset({
    "add",
    "am",
    "apply",
    "bisect",
    "branch",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "tag",
    "worktree",
})

_READ_ONLY_GIT_SUBCOMMANDS = frozenset({
    "blame",
    "branch",  # treated as mutating when flags imply create/delete; see parser
    "diff",
    "fetch",
    "grep",
    "log",
    "ls-files",
    "remote",
    "rev-parse",
    "show",
    "status",
})

_MUTATING_BRANCH_FLAGS = ("-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy")


def check_path_side_effect_allowed(path: str | Path) -> Optional[str]:
    """Return an error if a file write targets a repo outside the binding.

    Non-gateway callers and non-repo paths are allowed.  Gateway project writes
    are blocked when they target a git checkout that is not the bound repo, or
    when the session has no workspace binding at all.
    """

    if not _in_gateway_session():
        return None

    resolved = _safe_resolve(path)
    repo_root = _find_git_root(resolved if resolved.is_dir() else resolved.parent)
    if repo_root is None:
        return None

    bound_repo = _bound_repo_path()
    if bound_repo is None:
        return _blocked_message(repo_root, None)
    if not _same_path(repo_root, bound_repo):
        return _blocked_message(repo_root, bound_repo)
    return None


def check_terminal_side_effect_allowed(command: str, cwd: str | Path) -> Optional[str]:
    """Return an error if a mutating git command is outside the binding."""

    if not _in_gateway_session() or not _looks_like_mutating_git_command(command):
        return None

    cwd_path = _safe_resolve(cwd)
    repo_root = _find_git_root(cwd_path)
    if repo_root is None:
        return None

    bound_repo = _bound_repo_path()
    if bound_repo is None:
        return _blocked_message(repo_root, None)
    if not _same_path(repo_root, bound_repo):
        return _blocked_message(repo_root, bound_repo)
    return None


def _blocked_message(actual_repo: Path, bound_repo: Optional[Path]) -> str:
    if bound_repo is None:
        return (
            "Blocked repo side effect: this gateway session has no authoritative "
            f"workspace binding, but the target is inside git repo `{actual_repo}`. "
            "Add a channel binding to workspaces.yaml or use read-only tools."
        )
    return (
        "Blocked repo side effect outside authoritative workspace binding: "
        f"target repo `{actual_repo}` does not match bound repo `{bound_repo}`."
    )


def _in_gateway_session() -> bool:
    return bool(_session_env("HERMES_SESSION_PLATFORM", "") and _session_env("HERMES_SESSION_CHAT_ID", ""))


def _bound_repo_path() -> Optional[Path]:
    repo_path = _session_env("HERMES_WORKSPACE_REPO_PATH", "")
    if not repo_path:
        return None
    return _safe_resolve(repo_path)


def _session_env(name: str, default: str = "") -> str:
    try:
        from gateway.session_context import get_session_env

        return get_session_env(name, default)
    except Exception:
        return os.getenv(name, default)


def _find_git_root(start: Path) -> Optional[Path]:
    current = _safe_resolve(start)
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return os.path.abspath(left) == os.path.abspath(right)


def _safe_resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _looks_like_mutating_git_command(command: str) -> bool:
    for tokens in _split_shell_segments(command):
        for index, token in enumerate(tokens):
            if token != "git":
                continue
            subcommand, rest = _git_subcommand(tokens[index + 1 :])
            if not subcommand:
                continue
            if subcommand == "branch":
                if any(arg in _MUTATING_BRANCH_FLAGS for arg in rest):
                    return True
                # `git branch name` creates a branch; `git branch` lists.
                return bool(rest and not any(arg.startswith("-") for arg in rest))
            if subcommand in _READ_ONLY_GIT_SUBCOMMANDS:
                return False
            if subcommand in _MUTATING_GIT_SUBCOMMANDS:
                return True
            # Unknown git subcommands are potentially side-effecting; guard them.
            return True
    return False


def _git_subcommand(args: list[str]) -> tuple[Optional[str], list[str]]:
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return None, []
        if arg.startswith("-C"):
            index += 2 if arg == "-C" else 1
            continue
        if arg in {"-c", "--config-env"}:
            index += 2
            continue
        if arg.startswith("-"):
            index += 1
            continue
        return arg, args[index + 1 :]
    return None, []


def _split_shell_segments(command: str) -> Iterable[list[str]]:
    for segment in command.replace("&&", ";").replace("||", ";").split(";"):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if tokens:
            yield tokens

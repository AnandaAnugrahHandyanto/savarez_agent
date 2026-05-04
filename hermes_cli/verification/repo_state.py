from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RepoState:
    repo: str
    branch: str | None = None
    sha: str | None = None
    dirty: bool | None = None
    changed_files: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def collect_repo_state(repo: str | Path) -> RepoState:
    repo_path = Path(repo).expanduser().resolve()
    state = RepoState(repo=str(repo_path))

    inside = _git(repo_path, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        state.limitations.append("Repository state not collected: path is not inside a git work tree")
        return state

    branch = _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    if branch.returncode == 0:
        state.branch = branch.stdout.strip()
    else:
        state.limitations.append(f"Git branch not collected: {branch.stderr.strip()}")

    sha = _git(repo_path, "rev-parse", "HEAD")
    if sha.returncode == 0:
        state.sha = sha.stdout.strip()
    else:
        state.limitations.append(f"Git SHA not collected: {sha.stderr.strip()}")

    status = _git(repo_path, "status", "--short")
    if status.returncode == 0:
        state.changed_files = [line.strip() for line in status.stdout.splitlines() if line.strip()]
        state.dirty = bool(state.changed_files)
    else:
        state.limitations.append(f"Git status not collected: {status.stderr.strip()}")

    return state

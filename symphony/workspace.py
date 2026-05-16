"""Workspace and hook helpers for Symphony orchestration."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from symphony.errors import SymphonyError

_LOG = logging.getLogger(__name__)
_SAFE_IDENTIFIER = re.compile(r"[^A-Za-z0-9._-]")


@dataclass(frozen=True, slots=True)
class PreparedWorkspace:
    """Paths created for a Symphony issue workspace."""

    path: Path
    evidence_dir: Path


HookRunner = Callable[[str, Path], int | subprocess.CompletedProcess[Any] | None]
Sanitizer = Callable[[str], str]


def sanitize_issue_identifier(issue_identifier: str) -> str:
    """Return a deterministic filesystem segment for an issue identifier."""

    return _SAFE_IDENTIFIER.sub("_", issue_identifier)


def workspace_path(
    root: str | Path,
    issue_identifier: str,
    *,
    sanitizer: Sanitizer = sanitize_issue_identifier,
) -> Path:
    """Return the contained workspace path for an issue identifier.

    The issue identifier is first sanitized to a single path segment.  The final
    resolved path must remain below the resolved workspace root; otherwise a
    stable Symphony error is raised.
    """

    root_path = Path(root)
    sanitized = sanitizer(issue_identifier)
    candidate = root_path / sanitized

    root_resolved = root_path.resolve(strict=False)
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved == root_resolved or not candidate_resolved.is_relative_to(root_resolved):
        raise SymphonyError(
            "invalid_workspace_cwd",
            f"Workspace path escapes workspace root: {candidate}",
        )

    return candidate


def prepare_workspace(root: str | Path, issue_identifier: str) -> PreparedWorkspace:
    """Create and return the workspace and evidence directory paths."""

    path = workspace_path(root, issue_identifier)
    evidence_dir = path / ".symphony" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return PreparedWorkspace(path=path, evidence_dir=evidence_dir)


def run_hook(
    name: str,
    command: str,
    cwd: str | Path,
    *,
    fatal: bool | None = None,
    runner: HookRunner | None = None,
) -> int | None:
    """Run a lifecycle hook, raising only when fatal failures occur.

    If *fatal* is omitted, Symphony lifecycle defaults are applied:
    ``after_create`` and ``before_run`` are fatal; ``after_run`` and
    ``before_remove`` are best-effort.
    """

    cwd_path = Path(cwd)
    hook_runner = runner or _subprocess_runner
    is_fatal = _default_hook_fatality(name) if fatal is None else fatal

    try:
        raw_result = hook_runner(command, cwd_path)
    except Exception as exc:  # noqa: BLE001 - hook failures are deliberately normalized/logged.
        message = f"Symphony hook {name!r} failed: {exc}"
        if is_fatal:
            raise SymphonyError("hook_failed", message) from exc
        _LOG.warning(message)
        return None

    return_code = _return_code(raw_result)
    if return_code != 0:
        message = f"Symphony hook {name!r} failed with exit code {return_code}: {command}"
        if is_fatal:
            raise SymphonyError("hook_failed", message)
        _LOG.warning(message)

    return return_code


def _default_hook_fatality(name: str) -> bool:
    return name in {"after_create", "before_run"}


def _subprocess_runner(command: str, cwd: Path) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(command, cwd=cwd, shell=True, check=False)  # noqa: S602 - configured hook command.


def _return_code(result: int | subprocess.CompletedProcess[Any] | None) -> int:
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    return result.returncode

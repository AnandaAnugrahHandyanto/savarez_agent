from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from .repo_manager import is_safe_git_branch_name


class DraftPrPublisherError(RuntimeError):
    pass


RunCommand = Callable[[list[str], Path | None], str]


class DraftPrPublisher:
    def __init__(
        self,
        *,
        run_command: RunCommand | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        self._run_command = run_command or self._default_run
        self.timeout_seconds = timeout_seconds

    def publish(
        self,
        *,
        worktree: str | Path,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> str:
        safe_branch_name = str(branch_name or "").strip()
        if not safe_branch_name:
            raise DraftPrPublisherError("branch_name is required.")
        if not is_safe_git_branch_name(safe_branch_name):
            raise DraftPrPublisherError("branch_name must be a safe git branch name.")
        safe_base_branch = str(base_branch or "").strip()
        if not is_safe_git_branch_name(safe_base_branch):
            raise DraftPrPublisherError("base_branch must be a safe git branch name.")
        title_text = str(title or "").strip()
        if not title_text:
            raise DraftPrPublisherError("title is required.")
        body_text = str(body or "").strip()
        if not body_text:
            raise DraftPrPublisherError("body is required.")
        _validate_pr_body(body_text)
        worktree_path = Path(worktree)
        if not worktree_path.is_dir():
            raise DraftPrPublisherError(f"worktree does not exist: {worktree_path}")
        if not (worktree_path / ".git").exists():
            raise DraftPrPublisherError(f"worktree is not a git worktree: {worktree_path}")
        current_branch = self._run_command(["git", "branch", "--show-current"], worktree_path).strip()
        if current_branch != safe_branch_name:
            raise DraftPrPublisherError(
                f"worktree branch mismatch: expected {safe_branch_name}, got {current_branch or 'detached HEAD'}"
            )
        status = self._run_command(["git", "status", "--porcelain"], worktree_path)
        if status.strip():
            self._run_command(["git", "add", "-A"], worktree_path)
            self._run_command(
                [
                    "git",
                    "-c",
                    "user.name=Monica",
                    "-c",
                    "user.email=monica@hermes.local",
                    "commit",
                    "-m",
                    title_text,
                ],
                worktree_path,
            )

        diff = self._run_command(
            ["git", "diff", "--name-only", f"origin/{safe_base_branch}...HEAD"],
            worktree_path,
        )
        if not diff.strip():
            raise DraftPrPublisherError("No committed changes to publish.")

        self._run_command(
            ["git", "push", "origin", f"HEAD:{safe_branch_name}"],
            worktree_path,
        )
        create_command = [
            "gh",
            "pr",
            "create",
            "--draft",
            "--base",
            safe_base_branch,
            "--head",
            safe_branch_name,
            "--title",
            title_text,
            "--body",
            body_text,
        ]
        try:
            output = self._run_command(create_command, worktree_path)
        except DraftPrPublisherError as exc:
            if url := _extract_pr_url(str(exc)):
                return url
            raise
        if not (match := _extract_pr_url(output)):
            raise DraftPrPublisherError("gh did not return a draft PR URL.")
        return match

    def _default_run(self, cmd: list[str], cwd: Path | None = None) -> str:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            executable = cmd[0] if cmd else "command"
            raise DraftPrPublisherError(f"executable not found: {executable}") from exc
        except subprocess.TimeoutExpired as exc:
            raise DraftPrPublisherError(f"command timed out: {' '.join(cmd)}") from exc
        if proc.returncode != 0:
            raise DraftPrPublisherError(_command_failure_message(cmd, cwd, proc))
        return proc.stdout


def _command_failure_message(
    cmd: list[str],
    cwd: Path | None,
    proc: subprocess.CompletedProcess[str],
) -> str:
    return "\n".join(
        part
        for part in [
            f"command failed ({proc.returncode}): {' '.join(cmd)}",
            f"cwd: {cwd}" if cwd else "",
            f"stdout: {_tail(proc.stdout)}" if _tail(proc.stdout) else "",
            f"stderr: {_tail(proc.stderr)}" if _tail(proc.stderr) else "",
        ]
        if part
    )


def _tail(value: str | None, *, limit: int = 2000) -> str:
    return str(value or "").strip()[-limit:]


def _extract_pr_url(value: str) -> str:
    match = re.search(r"https://\S+/pull/\d+", str(value or ""))
    return match.group(0) if match else ""


def _validate_pr_body(body: str) -> None:
    if not _has_named_link(body, "Linear"):
        raise DraftPrPublisherError("body must include Linear issue context.")
    if not _has_named_link(body, "Slack"):
        raise DraftPrPublisherError("body must include Slack thread context.")
    if not _verification_section_text(body):
        raise DraftPrPublisherError("body must include verification evidence.")
    if not _proof_section_text(body):
        raise DraftPrPublisherError("body must include proof evidence.")


def _has_named_link(body: str, label: str) -> bool:
    pattern = re.compile(rf"(?im)^\s*(?:-\s*)?{re.escape(label)}\s*:\s*(.+?)\s*$")
    match = pattern.search(body)
    if not match:
        return False
    value = match.group(1).strip()
    return bool(value and value.lower() not in {"unavailable", "none", "n/a"})


def _verification_section_text(body: str) -> str:
    match = re.search(r"(?ims)^##\s+Verification\s*$([\s\S]*?)(?:^##\s+|\Z)", body)
    if not match:
        return ""
    return re.sub(r"[`#\s-]+", "", match.group(1)).strip()


def _proof_section_text(body: str) -> str:
    match = re.search(r"(?ims)^##\s+Proof\s*$([\s\S]*?)(?:^##\s+|\Z)", body)
    if not match:
        return ""
    return re.sub(r"[`#\s-]+", "", match.group(1)).strip()

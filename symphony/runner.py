"""Hermes runner primitives for Symphony orchestration."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Protocol

from symphony.config import HermesConfig
from symphony.errors import SymphonyError


class RunnerStatus(StrEnum):
    """Stable runner-facing turn statuses."""

    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    TURN_TIMEOUT = "turn_timeout"


@dataclass(frozen=True, slots=True)
class RunnerResult:
    """Result of one runner turn."""

    status: RunnerStatus
    events: list[str]
    started_at: datetime
    ended_at: datetime
    evidence_dir: Path
    evidence_path: Path
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None


class WorkspaceLease(Protocol):
    """Minimal workspace lease shape required by the runner."""

    path: Path
    evidence_dir: Path


class SubprocessRun(Protocol):
    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]: ...


_SAFE_ENV_KEYS = frozenset({"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TERM"})


@dataclass(slots=True)
class HermesRunner:
    """Synchronous Hermes subprocess runner MVP."""

    config: HermesConfig = field(default_factory=HermesConfig)
    subprocess_run: SubprocessRun = subprocess.run
    base_env: Mapping[str, str] | None = None

    def run_turn(
        self,
        prompt: str,
        workspace: WorkspaceLease,
        *,
        timeout_seconds: int | float | None = None,
    ) -> RunnerResult:
        """Run one Hermes turn in the leased workspace."""

        if self.config.mode == "in_process":
            raise SymphonyError(
                "unsupported_runner_mode",
                "Hermes in-process runner mode is not supported until cwd/tool scoping is implemented.",
            )
        if self.config.mode != "subprocess":
            raise SymphonyError(
                "unsupported_runner_mode",
                f"Unsupported Hermes runner mode: {self.config.mode}",
            )

        started_at = _now()
        events = ["turn_started"]
        evidence_dir = Path(workspace.evidence_dir)
        try:
            command = _command_argv(self.config.command) + ["chat", "-q", prompt]
        except ValueError as exc:
            raise SymphonyError("invalid_runner_command", f"Invalid Hermes runner command: {exc}") from exc
        env = _runner_env(self.base_env, evidence_dir)

        try:
            completed = self.subprocess_run(
                command,
                cwd=Path(workspace.path),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            ended_at = _now()
            events.append(RunnerStatus.TURN_TIMEOUT.value)
            return RunnerResult(
                status=RunnerStatus.TURN_TIMEOUT,
                events=events,
                started_at=started_at,
                ended_at=ended_at,
                evidence_dir=evidence_dir,
                evidence_path=evidence_dir,
                stdout=_text(exc.output),
                stderr=_text(exc.stderr),
                returncode=None,
            )
        except OSError as exc:
            ended_at = _now()
            events.append(RunnerStatus.TURN_FAILED.value)
            return RunnerResult(
                status=RunnerStatus.TURN_FAILED,
                events=events,
                started_at=started_at,
                ended_at=ended_at,
                evidence_dir=evidence_dir,
                evidence_path=evidence_dir,
                stdout="",
                stderr=str(exc),
                returncode=None,
            )

        returncode = int(completed.returncode)
        status = RunnerStatus.TURN_COMPLETED if returncode == 0 else RunnerStatus.TURN_FAILED
        events.append(status.value)
        return RunnerResult(
            status=status,
            events=events,
            started_at=started_at,
            ended_at=_now(),
            evidence_dir=evidence_dir,
            evidence_path=evidence_dir,
            stdout=_text(completed.stdout),
            stderr=_text(completed.stderr),
            returncode=returncode,
        )


def _command_argv(command: str | None) -> list[str]:
    if command is None or not command.strip():
        return ["hermes"]
    return shlex.split(command)


def _runner_env(base_env: Mapping[str, str] | None, evidence_dir: Path) -> dict[str, str]:
    source = os.environ if base_env is None else base_env
    env = {key: value for key, value in source.items() if key in _SAFE_ENV_KEYS}
    env["SYMPHONY_EVIDENCE_DIR"] = str(evidence_dir)
    return env


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)

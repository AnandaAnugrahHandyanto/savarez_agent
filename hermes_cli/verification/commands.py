from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from hermes_cli.verification.report import VerificationArtifact, VerificationCheck

TAIL_CHARS = 4000


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip().lower()).strip("-")
    return safe or "command"


def _tail(text: str, limit: int = TAIL_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_command_check(
    *,
    name: str,
    command: str,
    cwd: str | Path,
    output_dir: str | Path,
    timeout_seconds: float = 300,
) -> tuple[VerificationCheck, VerificationArtifact]:
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    log_path = output_path / f"{_safe_name(name)}.log"

    started = time.monotonic()
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    message: str | None = None
    status = "failed"

    try:
        completed = subprocess.run(
            command,
            cwd=Path(cwd).expanduser().resolve(),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
        status = "passed" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        message = f"Command timed out after {timeout_seconds:g}s"
        status = "failed"
    duration = time.monotonic() - started

    log_path.write_text(
        "\n".join(
            [
                f"$ {command}",
                f"cwd: {Path(cwd).expanduser().resolve()}",
                f"exit_code: {exit_code}",
                f"duration_seconds: {duration:.3f}",
                "",
                "--- stdout ---",
                stdout,
                "",
                "--- stderr ---",
                stderr,
                "",
            ]
        ),
        encoding="utf-8",
    )

    artifact = VerificationArtifact(kind="log", path=str(log_path), description=f"Output for {name}")
    check = VerificationCheck(
        name=name,
        kind="command",
        status=status,  # type: ignore[arg-type]
        command=command,
        exit_code=exit_code,
        duration_seconds=duration,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
        message=message,
        artifacts=[str(log_path)],
    )
    return check, artifact

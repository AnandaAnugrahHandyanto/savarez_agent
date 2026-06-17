"""Claude Code worker tool.

Runs the local ``claude`` CLI in print mode and stores proof artifacts under
``get_hermes_home()/outputs/proof-artifacts/claude-worker``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from hermes_constants import get_hermes_home
from tools.registry import registry


DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 1200
DEFAULT_MAX_TURNS = 5
MAX_MAX_TURNS = 20
VALID_PERMISSION_MODES = {"default", "acceptEdits", "plan"}
CLAUDE_FALLBACK_PATH = Path.home() / ".local" / "bin" / "claude"
TAIL_CHARS = 8000


ASK_CLAUDE_CODE_SCHEMA = {
    "name": "ask_claude_code",
    "description": (
        "Run the local Claude Code CLI as a bounded worker and return proof "
        "artifact paths plus stdout/stderr tails. The tool invokes `claude -p` "
        "with list arguments (never a shell)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Task prompt to send to Claude Code.",
            },
            "workdir": {
                "type": "string",
                "description": "Working directory for the Claude Code process. Defaults to the current backend cwd.",
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in seconds. Default {DEFAULT_TIMEOUT_SECONDS}, capped at {MAX_TIMEOUT_SECONDS}.",
                "default": DEFAULT_TIMEOUT_SECONDS,
            },
            "max_turns": {
                "type": "integer",
                "description": f"Claude Code maximum turns. Default {DEFAULT_MAX_TURNS}, capped at {MAX_MAX_TURNS}.",
                "default": DEFAULT_MAX_TURNS,
            },
            "permission_mode": {
                "type": "string",
                "enum": sorted(VALID_PERMISSION_MODES),
                "description": "Permission mode passed to Claude Code via --permission-mode. Dangerous bypass modes are not accepted.",
                "default": "default",
            },
            "expected_artifact": {
                "type": "string",
                "description": "Optional path to verify exists after Claude Code exits. Relative paths are resolved against workdir.",
            },
        },
        "required": ["prompt"],
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_int(value: Any, default: int, maximum: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    if coerced <= 0:
        return default
    return min(coerced, maximum)


def _tail(text: str, limit: int = TAIL_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _find_claude_binary() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    if CLAUDE_FALLBACK_PATH.exists() and CLAUDE_FALLBACK_PATH.is_file():
        return str(CLAUDE_FALLBACK_PATH)
    return None


def check_claude_code_requirements() -> bool:
    return _find_claude_binary() is not None


def _resolve_expected_artifact(expected_artifact: str | None, workdir: Path) -> tuple[str | None, bool | None]:
    if not expected_artifact:
        return None, None
    path = Path(expected_artifact).expanduser()
    if not path.is_absolute():
        path = workdir / path
    return str(path), path.exists()


def _artifact_paths() -> tuple[Path, Path, Path]:
    run_id = f"{int(time.time())}-{uuid4().hex[:8]}"
    artifact_dir = get_hermes_home() / "outputs" / "proof-artifacts" / "claude-worker"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return (
        artifact_dir / f"{run_id}.stdout.txt",
        artifact_dir / f"{run_id}.stderr.txt",
        artifact_dir / f"{run_id}.metadata.json",
    )


def _build_result(
    *,
    success: bool,
    exit_code: int | None,
    elapsed_seconds: float,
    stdout: str,
    stderr: str,
    stdout_path: Path,
    stderr_path: Path,
    metadata_path: Path,
    expected_artifact_exists: bool | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "success": success,
        "exit_code": exit_code,
        "elapsed_seconds": elapsed_seconds,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "metadata_path": str(metadata_path),
        "expected_artifact_exists": expected_artifact_exists,
        "error": error,
    }


def _write_result_artifacts(
    *,
    stdout: str,
    stderr: str,
    stdout_path: Path,
    stderr_path: Path,
    metadata_path: Path,
    metadata: dict[str, Any],
) -> None:
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def _preflight_failure(error: str, **metadata_overrides: Any) -> str:
    stdout_path, stderr_path, metadata_path = _artifact_paths()
    metadata = {
        "tool": "ask_claude_code",
        "started_at": _utc_now_iso(),
        "ended_at": _utc_now_iso(),
        "elapsed_seconds": 0,
        "workdir": None,
        "timeout": None,
        "max_turns": None,
        "permission_mode": None,
        "exit_code": None,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "expected_artifact": None,
        "expected_artifact_exists": None,
        "error": error,
    }
    metadata.update(metadata_overrides)
    _write_result_artifacts(
        stdout="",
        stderr="",
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        metadata_path=metadata_path,
        metadata=metadata,
    )
    result = _build_result(
        success=False,
        exit_code=None,
        elapsed_seconds=0,
        stdout="",
        stderr="",
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        metadata_path=metadata_path,
        expected_artifact_exists=metadata["expected_artifact_exists"],
        error=error,
    )
    return json.dumps(result, ensure_ascii=False)


def ask_claude_code(
    prompt: str,
    workdir: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_turns: int = DEFAULT_MAX_TURNS,
    permission_mode: str = "default",
    expected_artifact: str | None = None,
) -> str:
    """Run Claude Code and return a JSON string with execution metadata."""
    if not isinstance(prompt, str) or not prompt.strip():
        return _preflight_failure("prompt is required")

    if permission_mode not in VALID_PERMISSION_MODES:
        return _preflight_failure(
            f"invalid permission_mode: {permission_mode!r}",
            permission_mode=permission_mode,
            valid_permission_modes=sorted(VALID_PERMISSION_MODES),
        )

    claude_bin = _find_claude_binary()
    if not claude_bin:
        return _preflight_failure("claude CLI not found on PATH or fallback path", permission_mode=permission_mode)

    timeout_seconds = _coerce_int(timeout, DEFAULT_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS)
    max_turns_value = _coerce_int(max_turns, DEFAULT_MAX_TURNS, MAX_MAX_TURNS)
    cwd = Path(workdir).expanduser() if workdir else Path.cwd()
    cwd = cwd.resolve()
    if not cwd.exists() or not cwd.is_dir():
        expected_path = str(Path(expected_artifact).expanduser()) if expected_artifact else None
        return _preflight_failure(
            f"workdir does not exist or is not a directory: {cwd}",
            workdir=str(cwd),
            timeout=timeout_seconds,
            max_turns=max_turns_value,
            permission_mode=permission_mode,
            expected_artifact=expected_path,
        )

    stdout_path, stderr_path, metadata_path = _artifact_paths()

    effective_prompt = prompt
    if permission_mode == "plan":
        effective_prompt = "Plan only; do not edit files.\n\n" + prompt

    command = [
        claude_bin,
        "-p",
        effective_prompt,
        "--max-turns",
        str(max_turns_value),
        "--output-format",
        "text",
        "--permission-mode",
        permission_mode,
    ]

    started_at = _utc_now_iso()
    start = time.monotonic()
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    error: str | None = None

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        error = f"claude CLI timed out after {timeout_seconds} seconds"
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
    except Exception as exc:  # pragma: no cover - defensive around process spawn
        error = f"failed to run claude CLI: {exc}"

    elapsed_seconds = round(time.monotonic() - start, 3)
    ended_at = _utc_now_iso()
    expected_path, expected_exists = _resolve_expected_artifact(expected_artifact, cwd)

    success = error is None and exit_code == 0 and (expected_exists is not False)
    if error is None and exit_code != 0:
        error = f"claude CLI exited with code {exit_code}"
    elif error is None and expected_exists is False:
        error = f"expected_artifact was not found: {expected_path}"

    metadata = {
        "tool": "ask_claude_code",
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_seconds": elapsed_seconds,
        "workdir": str(cwd),
        "timeout": timeout_seconds,
        "max_turns": max_turns_value,
        "permission_mode": permission_mode,
        "exit_code": exit_code,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "expected_artifact": expected_path,
        "expected_artifact_exists": expected_exists,
        "error": error,
    }
    _write_result_artifacts(
        stdout=stdout,
        stderr=stderr,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        metadata_path=metadata_path,
        metadata=metadata,
    )

    result = _build_result(
        success=success,
        exit_code=exit_code,
        elapsed_seconds=elapsed_seconds,
        stdout=stdout,
        stderr=stderr,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        metadata_path=metadata_path,
        expected_artifact_exists=expected_exists,
        error=error,
    )
    return json.dumps(result, ensure_ascii=False)


registry.register(
    name="ask_claude_code",
    toolset="claude_code",
    schema=ASK_CLAUDE_CODE_SCHEMA,
    handler=lambda args, **kw: ask_claude_code(
        prompt=args.get("prompt"),
        workdir=args.get("workdir"),
        timeout=args.get("timeout", DEFAULT_TIMEOUT_SECONDS),
        max_turns=args.get("max_turns", DEFAULT_MAX_TURNS),
        permission_mode=args.get("permission_mode", "default"),
        expected_artifact=args.get("expected_artifact"),
    ),
    check_fn=check_claude_code_requirements,
    emoji="🤖",
    max_result_size_chars=50_000,
)

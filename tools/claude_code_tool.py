"""Claude Code worker tool.

Runs the local ``claude`` CLI in print mode and stores proof artifacts under
``get_hermes_home()/outputs/proof-artifacts/claude-worker``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
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
MAX_OUTPUT_CHARS = 50_000
AUTH_CHECK_TIMEOUT_SECONDS = 20
ENV_ALLOWLIST = {
    "HOME",
    "PATH",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "SHELL",
    "TERM",
    "TMPDIR",
}
ENV_POLICY = (
    "Subprocess env is allowlisted for Claude CLI runtime only. HOME is retained because "
    "Claude CLI may need its user config/cache; HERMES_HOME and common secret-bearing "
    "env vars (key, secret, token, password, pass, credential, auth, cookie, session) are not passed."
)
SECRET_ENV_SUBSTRINGS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASS",
    "CREDENTIAL",
    "AUTH",
    "COOKIE",
    "SESSION",
)


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
                "description": "Optional path under workdir to verify exists after Claude Code exits. Relative paths are resolved against workdir; absolute paths outside workdir are rejected.",
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


def _cap_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool, int]:
    """Return bounded persisted output, whether it was truncated, and original char count."""
    return _format_bounded_tail(text, len(text), limit)


def _format_bounded_tail(text: str, original_chars: int, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool, int]:
    """Format an already-tail-bounded string with truncation metadata."""
    if original_chars <= limit:
        return text, False, original_chars
    marker = f"\n\n[... truncated to last {limit} of {original_chars} chars ...]\n"
    keep = max(0, limit - len(marker))
    return marker + text[-keep:], True, original_chars


def _find_claude_binary() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    if CLAUDE_FALLBACK_PATH.exists() and CLAUDE_FALLBACK_PATH.is_file():
        return str(CLAUDE_FALLBACK_PATH)
    return None


def _sanitized_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key in ENV_ALLOWLIST
        and not any(secret_fragment in key.upper() for secret_fragment in SECRET_ENV_SUBSTRINGS)
    }


def _artifact_signature(path: str | None) -> dict[str, int] | None:
    if not path:
        return None
    try:
        stat = Path(path).stat()
    except FileNotFoundError:
        return None
    return {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}


def _collect_claude_metadata(claude_bin: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "claude_path": claude_bin,
        "claude_version": None,
        "claude_version_error": None,
    }
    try:
        completed = subprocess.run(
            [claude_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            check=False,
            env=_sanitized_env(),
        )
        version_text = (completed.stdout or completed.stderr or "").strip()
        metadata["claude_version"] = version_text or None
        if completed.returncode != 0:
            metadata["claude_version_error"] = f"claude --version exited with code {completed.returncode}"
    except Exception as exc:  # pragma: no cover - best-effort metadata only
        metadata["claude_version_error"] = str(exc)
    return metadata


def _check_claude_auth_available(claude_bin: str) -> bool:
    """Return True when Claude Code can run non-interactively with local auth.

    Claude Code CLI versions do not expose one stable machine-readable
    auth-status command. A tiny print-mode, plan-permission probe is the most
    reliable generic availability gate for Hermes: it verifies the binary,
    local login/session, and non-interactive execution path without granting
    edit permissions.
    """
    try:
        completed = subprocess.run(
            [
                claude_bin,
                "-p",
                "Reply with OK.",
                "--max-turns",
                "1",
                "--output-format",
                "text",
                "--permission-mode",
                "plan",
            ],
            capture_output=True,
            text=True,
            timeout=AUTH_CHECK_TIMEOUT_SECONDS,
            shell=False,
            check=False,
            env=_sanitized_env(),
        )
    except Exception:
        return False
    return completed.returncode == 0


def check_claude_code_requirements() -> bool:
    claude_bin = _find_claude_binary()
    if not claude_bin:
        return False
    return _check_claude_auth_available(claude_bin)


def _resolve_expected_artifact(expected_artifact: str | None, workdir: Path) -> tuple[str | None, bool | None, str | None]:
    if not expected_artifact:
        return None, None, None
    path = Path(expected_artifact).expanduser()
    if not path.is_absolute():
        path = workdir / path
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(workdir)
    except ValueError:
        return str(resolved), None, f"expected_artifact must be inside workdir: {resolved}"
    return str(resolved), resolved.exists(), None


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
    expected_artifact_existed_before: bool | None,
    success_basis: str,
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
        "expected_artifact_existed_before": expected_artifact_existed_before,
        "success_basis": success_basis,
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


def _read_bounded_text(path: Path, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool, int]:
    """Read text from a process-output file while retaining only the tail in memory."""
    total_chars = 0
    tail = ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            total_chars += len(chunk)
            tail = (tail + chunk)[-limit:]
    marker_prefix = "\n\n[... truncated to last "
    if tail.startswith(marker_prefix):
        try:
            original = int(tail.split(" of ", 1)[1].split(" chars ...]", 1)[0])
        except (IndexError, ValueError):
            original = total_chars
        return tail, True, original
    if total_chars <= limit:
        return tail, False, total_chars
    marker = f"\n\n[... truncated to last {limit} of {total_chars} chars ...]\n"
    keep = max(0, limit - len(marker))
    return marker + tail[-keep:], True, total_chars


def _run_claude_process(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[int | None, str | None]:
    """Run Claude with bounded stdout/stderr capture and persistence."""
    # Backward-compatible unit-test seam: existing tests monkeypatch subprocess.run.
    # Production uses Popen pipes plus bounded tail buffers so neither memory nor
    # persisted artifacts grow without limit while Claude is running.
    if getattr(subprocess.run, "__module__", "subprocess") != "subprocess":
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
                env=_sanitized_env(),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            stdout_path.write_text(_format_bounded_tail(stdout, len(stdout))[0], encoding="utf-8")
            stderr_path.write_text(_format_bounded_tail(stderr, len(stderr))[0], encoding="utf-8")
            return None, f"claude CLI timed out after {timeout_seconds} seconds"
        stdout_path.write_text(_format_bounded_tail(completed.stdout or "", len(completed.stdout or ""))[0], encoding="utf-8")
        stderr_path.write_text(_format_bounded_tail(completed.stderr or "", len(completed.stderr or ""))[0], encoding="utf-8")
        return completed.returncode, None

    buffers = {"stdout": "", "stderr": ""}
    totals = {"stdout": 0, "stderr": 0}

    def _drain(stream: Any, key: str) -> None:
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                totals[key] += len(chunk)
                buffers[key] = (buffers[key] + chunk)[-MAX_OUTPUT_CHARS:]
        finally:
            try:
                stream.close()
            except Exception:
                pass

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        env=_sanitized_env(),
    )
    threads = [
        threading.Thread(target=_drain, args=(process.stdout, "stdout"), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=2)
        stdout_path.write_text(_format_bounded_tail(buffers["stdout"], totals["stdout"])[0], encoding="utf-8")
        stderr_path.write_text(_format_bounded_tail(buffers["stderr"], totals["stderr"])[0], encoding="utf-8")
        return None, f"claude CLI timed out after {timeout_seconds} seconds"
    for thread in threads:
        thread.join(timeout=2)
    stdout_path.write_text(_format_bounded_tail(buffers["stdout"], totals["stdout"])[0], encoding="utf-8")
    stderr_path.write_text(_format_bounded_tail(buffers["stderr"], totals["stderr"])[0], encoding="utf-8")
    return process.returncode, None


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
        "expected_artifact_existed_before": None,
        "success_basis": "preflight_failed",
        "claude_path": None,
        "claude_version": None,
        "claude_version_error": None,
        "env_allowlist": sorted(ENV_ALLOWLIST),
        "env_policy": ENV_POLICY,
        "max_output_chars": MAX_OUTPUT_CHARS,
        "capture_memory_bound": True,
        "artifact_persistence_bound": True,
        "stdout_truncated": False,
        "stderr_truncated": False,
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
        expected_artifact_existed_before=metadata["expected_artifact_existed_before"],
        success_basis=metadata["success_basis"],
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
    expected_path, expected_existed_before, expected_error = _resolve_expected_artifact(expected_artifact, cwd)
    if expected_error:
        return _preflight_failure(
            expected_error,
            workdir=str(cwd),
            timeout=timeout_seconds,
            max_turns=max_turns_value,
            permission_mode=permission_mode,
            expected_artifact=expected_path,
            expected_artifact_existed_before=expected_existed_before,
        )
    expected_signature_before = _artifact_signature(expected_path)
    claude_metadata = _collect_claude_metadata(claude_bin)

    effective_prompt = prompt
    if permission_mode == "plan":
        # This prompt prefix is advisory; the hard boundary is Claude Code's own plan permission mode enforcement.
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
        exit_code, error = _run_claude_process(
            command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    except Exception as exc:  # pragma: no cover - defensive around process spawn
        error = f"failed to run claude CLI: {exc}"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")

    stdout, stdout_truncated, stdout_chars = _read_bounded_text(stdout_path)
    stderr, stderr_truncated, stderr_chars = _read_bounded_text(stderr_path)

    elapsed_seconds = round(time.monotonic() - start, 3)
    ended_at = _utc_now_iso()
    expected_exists = Path(expected_path).exists() if expected_path else None
    expected_signature_after = _artifact_signature(expected_path)
    expected_artifact_changed = (
        expected_signature_after is not None and expected_signature_after != expected_signature_before
    ) if expected_path else None

    process_success = error is None and exit_code == 0
    task_success = process_success
    if process_success and expected_path:
        task_success = expected_artifact_changed is True
    success = task_success
    if process_success and expected_path and expected_existed_before and not expected_artifact_changed:
        success_basis = "expected_artifact_preexisting_unchanged"
    elif process_success and expected_path and expected_existed_before is False and expected_artifact_changed:
        success_basis = "expected_artifact_created"
    elif process_success and expected_path and expected_artifact_changed:
        success_basis = "expected_artifact_modified"
    elif process_success and expected_path and expected_exists is False:
        success_basis = "expected_artifact_missing"
    elif process_success:
        success_basis = "process_exit_zero_unverified"
    elif expected_exists is False:
        success_basis = "expected_artifact_missing"
    elif error and "timed out" in error:
        success_basis = "timeout"
    else:
        success_basis = "process_failed"
    if error is None and exit_code != 0:
        error = f"claude CLI exited with code {exit_code}"
    elif error is None and expected_exists is False:
        error = f"expected_artifact was not found: {expected_path}"
    elif error is None and expected_path and success_basis == "expected_artifact_preexisting_unchanged":
        error = f"expected_artifact existed before run and was unchanged: {expected_path}"

    metadata = {
        "tool": "ask_claude_code",
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_seconds": elapsed_seconds,
        "workdir": str(cwd),
        "timeout": timeout_seconds,
        "max_turns": max_turns_value,
        "permission_mode": permission_mode,
        "plan_mode_boundary": "Plan prompt prefix is advisory; file-edit prevention relies on Claude Code --permission-mode plan enforcement.",
        "exit_code": exit_code,
        "success": success,
        "process_success": process_success,
        "task_success": task_success,
        "success_basis": success_basis,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_chars": stdout_chars,
        "stderr_chars": stderr_chars,
        "stdout_tail_chars": min(len(stdout), TAIL_CHARS),
        "stderr_tail_chars": min(len(stderr), TAIL_CHARS),
        "max_output_chars": MAX_OUTPUT_CHARS,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "full_output_artifacts": not (stdout_truncated or stderr_truncated),
        "capture_memory_bound": True,
        "artifact_persistence_bound": True,
        "env_allowlist": sorted(ENV_ALLOWLIST),
        "env_policy": ENV_POLICY,
        "expected_artifact": expected_path,
        "expected_artifact_exists": expected_exists,
        "expected_artifact_existed_before": expected_existed_before,
        "expected_artifact_signature_before": expected_signature_before,
        "expected_artifact_signature_after": expected_signature_after,
        "expected_artifact_changed": expected_artifact_changed,
        "error": error,
    }
    metadata.update(claude_metadata)
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
        expected_artifact_existed_before=expected_existed_before,
        success_basis=success_basis,
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

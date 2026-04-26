"""Offloaded terminal job tool.

This module provides a small, dependency-free job runner for commands that are
expected to be long-running or memory-heavy.  Unlike ``terminal(background=True)``
for the local backend, the preferred Linux path starts work through
``systemd-run --user`` so the command lives in its own user unit instead of as a
child of ``hermes-gateway.service``.  Metadata and logs are persisted in the
active Hermes profile so gateway restarts do not lose the job handle.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import shlex
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from hermes_constants import display_hermes_home, get_hermes_home
from tools.approval import check_all_command_guards
from tools.registry import registry
from tools.terminal_tool import _validate_workdir

_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_DEFAULT_TAIL_LINES = 80
_DEFAULT_LIST_LIMIT = 20


def _now() -> float:
    return time.time()


def _iso(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts or _now()))


def _jobs_dir() -> Path:
    path = get_hermes_home() / "offload_jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_dir(job_id: str) -> Path:
    if not _JOB_ID_RE.match(job_id):
        raise ValueError("invalid job_id")
    return _jobs_dir() / job_id


def _meta_path(job_id: str) -> Path:
    return _job_dir(job_id) / "job.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _read_job(job_id: str) -> dict[str, Any]:
    path = _meta_path(job_id)
    if not path.exists():
        raise FileNotFoundError(f"Unknown offload job: {job_id}")
    return _read_json(path)


def _write_job(job: dict[str, Any]) -> None:
    _atomic_write_json(_meta_path(str(job["job_id"])), job)


def _new_job_id(label: str | None = None) -> str:
    prefix = "job"
    if label:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", label.strip().lower()).strip("-._")
        if cleaned:
            prefix = cleaned[:32]
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _coerce_positive_int(value: Any, default: int, *, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed <= 0:
        parsed = default
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _resolve_workdir(workdir: str | None) -> str:
    candidate = workdir or os.getenv("TERMINAL_CWD") or os.getcwd()
    candidate = os.path.abspath(os.path.expanduser(candidate))
    error = _validate_workdir(candidate)
    if error:
        raise ValueError(error)
    return candidate


def _write_scripts(job: dict[str, Any]) -> None:
    job_path = _job_dir(job["job_id"])
    command_path = job_path / "command.sh"
    runner_path = job_path / "runner.sh"
    log_path = Path(job["log_path"])
    pid_path = Path(job["pid_path"])
    exit_path = Path(job["exit_code_path"])
    timeout = job.get("timeout_seconds")

    command_path.write_text(
        "#!/usr/bin/env bash\nset -o pipefail\n" + job["command"] + "\n",
        encoding="utf-8",
    )
    command_path.chmod(0o700)

    if timeout:
        run_line = (
            f"timeout --kill-after=5s {int(timeout)}s "
            f"/usr/bin/env bash {shlex.quote(str(command_path))}"
        )
    else:
        run_line = f"/usr/bin/env bash {shlex.quote(str(command_path))}"

    runner_path.write_text(
        "#!/usr/bin/env bash\n"
        "set +e\n"
        f"cd {json.dumps(job['workdir'])} || exit 126\n"
        f"echo $$ > {json.dumps(str(pid_path))}\n"
        f"printf '[%s] offload job started: %s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" {json.dumps(job['job_id'])} >> {json.dumps(str(log_path))}\n"
        f"{run_line} >> {json.dumps(str(log_path))} 2>&1\n"
        "ec=$?\n"
        f"printf '%s\\n' \"$ec\" > {json.dumps(str(exit_path))}\n"
        f"printf '[%s] offload job exited with code %s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" \"$ec\" >> {json.dumps(str(log_path))}\n"
        "exit $ec\n",
        encoding="utf-8",
    )
    runner_path.chmod(0o700)

    job["command_path"] = str(command_path)
    job["runner_path"] = str(runner_path)


def _systemd_run_available() -> bool:
    return bool(
        shutil.which("systemd-run")
        and shutil.which("systemctl")
        and os.getenv("XDG_RUNTIME_DIR")
    )


def _start_systemd_job(job: dict[str, Any]) -> None:
    unit_name = f"hermes-offload-{job['job_id']}"
    cmd = ["systemd-run", "--user", "--unit", unit_name]
    cmd.extend(["--property", f"WorkingDirectory={job['workdir']}"])
    memory_max = job.get("memory_max")
    cpu_quota = job.get("cpu_quota")
    if memory_max:
        cmd.extend(["--property", f"MemoryMax={memory_max}"])
    if cpu_quota:
        cmd.extend(["--property", f"CPUQuota={cpu_quota}"])
    cmd.extend(["/usr/bin/env", "bash", job["runner_path"]])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "systemd-run failed").strip()
        raise RuntimeError(stderr)
    job["runner"] = "systemd"
    job["unit_name"] = unit_name
    job["systemd_run_stdout"] = result.stdout.strip()


def _start_subprocess_job(job: dict[str, Any]) -> None:
    log_file = open(job["launcher_log_path"], "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            ["/usr/bin/env", "bash", job["runner_path"]],
            cwd=job["workdir"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_file.close()
    job["runner"] = "subprocess"
    job["launcher_pid"] = proc.pid


def _read_exit_code(job: dict[str, Any]) -> int | None:
    path = Path(job.get("exit_code_path", ""))
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _systemd_show(unit: str) -> dict[str, str]:
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "--property=ActiveState",
            "--property=SubState",
            "--property=Result",
            "--property=ExecMainStatus",
            "--property=MainPID",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return {}
    out: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


def _refresh_status(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("status") == "cancelled":
        return job

    exit_code = _read_exit_code(job)
    if exit_code is not None:
        if job.get("runner") == "systemd" and job.get("unit_name"):
            show = _systemd_show(job["unit_name"])
            if show:
                job["systemd"] = show
                main_pid = show.get("MainPID")
                if main_pid and main_pid != "0":
                    job["pid"] = int(main_pid)
                elif main_pid == "0":
                    job.pop("pid", None)
        job["exit_code"] = exit_code
        job["status"] = "succeeded" if exit_code == 0 else "failed"
        job.setdefault("completed_at", _iso())
        _write_job(job)
        return job

    if job.get("runner") == "systemd" and job.get("unit_name"):
        show = _systemd_show(job["unit_name"])
        if show:
            job["systemd"] = show
            active = show.get("ActiveState")
            result = show.get("Result")
            main_pid = show.get("MainPID")
            if main_pid and main_pid != "0":
                job["pid"] = int(main_pid)
            if active in {"active", "activating", "reloading"}:
                job["status"] = "running"
            elif active in {"failed", "inactive", "deactivating"}:
                exec_status = show.get("ExecMainStatus")
                if exec_status is not None and exec_status.isdigit():
                    job["exit_code"] = int(exec_status)
                if result == "success" and job.get("exit_code", 1) == 0:
                    job["status"] = "succeeded"
                elif result:
                    job["status"] = "failed"
                else:
                    job["status"] = "unknown"
                job.setdefault("completed_at", _iso())
            _write_job(job)
        return job

    pid = job.get("launcher_pid") or job.get("pid")
    if _process_alive(pid):
        job["status"] = "running"
    else:
        job["status"] = "unknown"
        job.setdefault("completed_at", _iso())
    _write_job(job)
    return job


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "job_id",
        "status",
        "runner",
        "unit_name",
        "pid",
        "launcher_pid",
        "exit_code",
        "command",
        "workdir",
        "log_path",
        "created_at",
        "started_at",
        "completed_at",
        "created_at_ts",
        "memory_max",
        "cpu_quota",
        "timeout_seconds",
        "systemd",
    ]
    return {key: job[key] for key in keys if key in job}


def _tail_log(job: dict[str, Any], lines: int) -> str:
    path = Path(job["log_path"])
    if not path.exists():
        return ""
    # Avoid loading unbounded logs into memory.
    data = path.read_bytes()[-256_000:]
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _list_jobs(limit: int, status_filter: str | None = None) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for meta in _jobs_dir().glob("*/job.json"):
        try:
            job = _refresh_status(_read_json(meta))
        except Exception:
            continue
        if status_filter and job.get("status") != status_filter:
            continue
        jobs.append(_public_job(job))
    jobs.sort(key=lambda item: item.get("created_at_ts", 0), reverse=True)
    return jobs[:limit]


def _cancel_job(job: dict[str, Any]) -> dict[str, Any]:
    job = _refresh_status(job)
    if job.get("status") in {"succeeded", "failed", "cancelled"}:
        return job

    if job.get("runner") == "systemd" and job.get("unit_name") and shutil.which("systemctl"):
        subprocess.run(
            ["systemctl", "--user", "kill", job["unit_name"]],
            capture_output=True,
            text=True,
            timeout=10,
        )
        subprocess.run(
            ["systemctl", "--user", "stop", job["unit_name"]],
            capture_output=True,
            text=True,
            timeout=15,
        )
    else:
        pid = job.get("launcher_pid") or job.get("pid")
        if pid:
            try:
                os.killpg(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError:
                os.kill(int(pid), signal.SIGTERM)

    job["status"] = "cancelled"
    job["cancelled_at"] = _iso()
    job.setdefault("completed_at", job["cancelled_at"])
    _write_job(job)
    return job


def offload_job_tool(
    action: str,
    command: str | None = None,
    job_id: str | None = None,
    workdir: str | None = None,
    timeout: int | None = None,
    memory_max: str | None = None,
    cpu_quota: str | None = None,
    label: str | None = None,
    tail_lines: int | None = None,
    limit: int | None = None,
    status_filter: str | None = None,
    force: bool = False,
) -> str:
    """Dispatch offload job actions and return a JSON string."""
    try:
        action = (action or "").strip().lower()
        if action == "start":
            if not command or not isinstance(command, str):
                return json.dumps({"success": False, "error": "command is required for action=start"}, ensure_ascii=False)

            if not force:
                approval = check_all_command_guards(command, "local")
                if not approval.get("approved"):
                    if approval.get("status") == "approval_required":
                        return json.dumps({
                            "success": False,
                            "status": "approval_required",
                            "error": approval.get("message", "Waiting for user approval"),
                            "command": approval.get("command", command),
                            "description": approval.get("description", "command flagged"),
                            "pattern_key": approval.get("pattern_key", ""),
                        }, ensure_ascii=False)
                    return json.dumps({
                        "success": False,
                        "status": "blocked",
                        "error": approval.get("message", "Command blocked by approval guard"),
                    }, ensure_ascii=False)

            resolved_workdir = _resolve_workdir(workdir)
            new_id = _new_job_id(label)
            job_path = _job_dir(new_id)
            job_path.mkdir(parents=True, exist_ok=False)
            job = {
                "job_id": new_id,
                "status": "starting",
                "command": command,
                "workdir": resolved_workdir,
                "created_at": _iso(),
                "created_at_ts": _now(),
                "started_at": _iso(),
                "log_path": str(job_path / "job.log"),
                "launcher_log_path": str(job_path / "launcher.log"),
                "pid_path": str(job_path / "job.pid"),
                "exit_code_path": str(job_path / "exit_code"),
                "memory_max": memory_max,
                "cpu_quota": cpu_quota,
                "timeout_seconds": int(timeout) if timeout else None,
            }
            _write_scripts(job)
            Path(job["log_path"]).touch()
            _write_job(job)

            try:
                if _systemd_run_available():
                    _start_systemd_job(job)
                else:
                    _start_subprocess_job(job)
            except Exception as exc:
                # If systemd-run is present but rejects the job, keep the long-running
                # command usable by falling back to a detached subprocess and make the
                # reduced isolation explicit in metadata.
                job["systemd_error"] = str(exc)
                _start_subprocess_job(job)

            job["status"] = "running"
            _write_job(job)
            return json.dumps({"success": True, "job": _public_job(job)}, ensure_ascii=False)

        if action == "status":
            if not job_id:
                return json.dumps({"success": False, "error": "job_id is required for action=status"}, ensure_ascii=False)
            return json.dumps({"success": True, "job": _public_job(_refresh_status(_read_job(job_id)))}, ensure_ascii=False)

        if action == "tail":
            if not job_id:
                return json.dumps({"success": False, "error": "job_id is required for action=tail"}, ensure_ascii=False)
            lines = _coerce_positive_int(tail_lines, _DEFAULT_TAIL_LINES, maximum=1000)
            job = _refresh_status(_read_job(job_id))
            return json.dumps({"success": True, "job": _public_job(job), "tail": _tail_log(job, lines)}, ensure_ascii=False)

        if action == "list":
            count = _coerce_positive_int(limit, _DEFAULT_LIST_LIMIT, maximum=200)
            return json.dumps({"success": True, "jobs": _list_jobs(count, status_filter=status_filter)}, ensure_ascii=False)

        if action == "cancel":
            if not job_id:
                return json.dumps({"success": False, "error": "job_id is required for action=cancel"}, ensure_ascii=False)
            return json.dumps({"success": True, "job": _public_job(_cancel_job(_read_job(job_id)))}, ensure_ascii=False)

        return json.dumps({"success": False, "error": "action must be one of: start, status, tail, list, cancel"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


OFFLOAD_JOB_SCHEMA = {
    "name": "offload_job",
    "description": (
        "Queue and manage long-running or memory-heavy shell commands as offloaded jobs. "
        "Use this instead of terminal(background=true) for benchmarks, indexing, model inference, "
        "training, or other gateway-hostile workloads. On Linux it prefers systemd-run --user so "
        "the job runs outside hermes-gateway.service; metadata/logs are stored under "
        f"{display_hermes_home()}/offload_jobs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "status", "tail", "list", "cancel"],
                "description": "Job operation to perform.",
            },
            "command": {
                "type": "string",
                "description": "Shell command to run. Required for action=start.",
            },
            "job_id": {
                "type": "string",
                "description": "Job id returned by action=start. Required for status, tail, and cancel.",
            },
            "workdir": {
                "type": "string",
                "description": "Working directory for action=start. Defaults to the terminal session cwd.",
            },
            "timeout": {
                "type": "integer",
                "description": "Optional maximum runtime in seconds; implemented with timeout(1).",
            },
            "memory_max": {
                "type": "string",
                "description": "Optional systemd MemoryMax value such as '32G' or '8192M'. Applies only to systemd-run jobs.",
            },
            "cpu_quota": {
                "type": "string",
                "description": "Optional systemd CPUQuota value such as '800%'. Applies only to systemd-run jobs.",
            },
            "label": {
                "type": "string",
                "description": "Optional short label used as the job id prefix.",
            },
            "tail_lines": {
                "type": "integer",
                "description": "Number of log lines to return for action=tail. Default 80, max 1000.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum jobs to return for action=list. Default 20, max 200.",
            },
            "status_filter": {
                "type": "string",
                "description": "Optional status filter for action=list, for example 'running' or 'failed'.",
            },
        },
        "required": ["action"],
    },
}


def _handle_offload_job(args, **kw):
    return offload_job_tool(
        action=args.get("action", ""),
        command=args.get("command"),
        job_id=args.get("job_id"),
        workdir=args.get("workdir"),
        timeout=args.get("timeout"),
        memory_max=args.get("memory_max"),
        cpu_quota=args.get("cpu_quota"),
        label=args.get("label"),
        tail_lines=args.get("tail_lines"),
        limit=args.get("limit"),
        status_filter=args.get("status_filter"),
        force=bool(kw.get("force", False)),
    )


registry.register(
    name="offload_job",
    toolset="terminal",
    schema=OFFLOAD_JOB_SCHEMA,
    handler=_handle_offload_job,
    check_fn=lambda: True,
    emoji="🚚",
    max_result_size_chars=100_000,
)

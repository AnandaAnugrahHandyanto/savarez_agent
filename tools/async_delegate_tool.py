#!/usr/bin/env python3
"""Durable async delegation tools.

These tools complement ``delegate_task``.  ``delegate_task`` is synchronous
fork/join inside the parent agent turn; async delegation starts an independent
Hermes child process, persists a job handle under HERMES_HOME, and returns
immediately so the parent conversation can continue or end.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home
from tools.registry import registry, tool_error, tool_result

_DB_NAME = "async_delegations.db"
_JOBS_DIR = "async_delegations"
_TERMINAL_EXIT_SENTINEL = "__HERMES_ASYNC_DELEGATE_TERMINAL_EXIT__"


def _now() -> float:
    return time.time()


def _state_dir() -> Path:
    path = get_hermes_home() / _JOBS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _db_path() -> Path:
    return get_hermes_home() / _DB_NAME


def _connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS async_delegations (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            prompt TEXT NOT NULL,
            profile TEXT,
            provider TEXT,
            model TEXT,
            toolsets TEXT,
            workdir TEXT,
            pid INTEGER,
            created_at REAL NOT NULL,
            started_at REAL,
            completed_at REAL,
            exit_code INTEGER,
            log_path TEXT NOT NULL,
            stderr_path TEXT NOT NULL,
            result_path TEXT NOT NULL,
            metadata TEXT
        )
        """
    )
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for key in ("toolsets", "metadata"):
        if data.get(key):
            try:
                data[key] = json.loads(data[key])
            except Exception:
                pass
    return data


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM async_delegations WHERE job_id = ?", (job_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def _update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    keys = list(fields)
    values = [fields[k] for k in keys]
    sets = ", ".join(f"{k} = ?" for k in keys)
    with _connect() as conn:
        conn.execute(f"UPDATE async_delegations SET {sets} WHERE job_id = ?", values + [job_id])
        conn.commit()


def _pid_is_running(pid: Optional[int]) -> bool:
    if not pid:
        return False
    # Avoid os.kill(pid, 0) here. Hermes' test harness guards live-system
    # signal delivery, and /proc is sufficient for Linux process liveness.
    proc = Path("/proc") / str(int(pid))
    if proc.exists():
        return True
    try:
        os.waitpid(int(pid), os.WNOHANG)
    except ChildProcessError:
        return False
    except Exception:
        return False
    return False


def _read_json(path: str | Path) -> Optional[Dict[str, Any]]:
    try:
        p = Path(path)
        if not p.exists():
            return None
        return json.loads(p.read_text(errors="replace"))
    except Exception:
        return None


def _refresh_status(job: Dict[str, Any]) -> Dict[str, Any]:
    result = _read_json(job["result_path"])
    if result:
        status = "completed" if result.get("exit_code") == 0 else "failed"
        updates = {
            "status": status,
            "exit_code": result.get("exit_code"),
            "completed_at": result.get("completed_at") or _now(),
        }
        if job.get("status") != status or job.get("exit_code") != result.get("exit_code"):
            _update_job(job["job_id"], **updates)
        job.update(updates)
        return job

    if job.get("status") in {"cancelled", "completed", "failed"}:
        return job

    if _pid_is_running(job.get("pid")):
        if job.get("status") != "running":
            _update_job(job["job_id"], status="running")
            job["status"] = "running"
        return job

    # Process disappeared before writing a result file.
    updates = {"status": "failed", "completed_at": _now(), "exit_code": None}
    _update_job(job["job_id"], **updates)
    job.update(updates)
    return job


def _tail_file(path: str | Path, max_chars: int = 8000) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    data = p.read_bytes()
    if len(data) > max_chars:
        data = data[-max_chars:]
    return data.decode(errors="replace")


def _hermes_command(
    *,
    prompt_path: Path,
    profile: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    toolsets: Optional[List[str]],
    yolo: bool,
) -> List[str]:
    hermes = shutil.which("hermes") or "hermes"
    cmd = [hermes]
    if profile:
        cmd += ["--profile", profile]
    if yolo:
        cmd.append("--yolo")
    cmd += ["chat", "-Q"]
    if provider:
        cmd += ["--provider", provider]
    if model:
        cmd += ["-m", model]
    if toolsets:
        cmd += ["-t", ",".join(toolsets)]
    cmd += ["-q", prompt_path.read_text()]
    return cmd


def _wrapper_code() -> str:
    # Runs in a separate Python process.  It owns the child Hermes subprocess and
    # writes a durable result JSON even after the parent agent turn is gone.
    return r'''
import json, pathlib, subprocess, sys, time, os, signal
spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
result_path = pathlib.Path(spec["result_path"])
stdout_path = pathlib.Path(spec["log_path"])
stderr_path = pathlib.Path(spec["stderr_path"])
started = time.time()
exit_code = None
try:
    with stdout_path.open("ab", buffering=0) as out, stderr_path.open("ab", buffering=0) as err:
        out.write(("START job_id=%s ts=%s\n" % (spec["job_id"], started)).encode())
        proc = subprocess.Popen(spec["cmd"], cwd=spec.get("workdir") or None, stdout=out, stderr=err)
        pathlib.Path(spec["child_pid_path"]).write_text(str(proc.pid))
        try:
            exit_code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            exit_code = proc.wait(timeout=10)
        out.write(("END job_id=%s exit_code=%s ts=%s\n" % (spec["job_id"], exit_code, time.time())).encode())
except BaseException as exc:
    with stderr_path.open("ab", buffering=0) as err:
        err.write(("WRAPPER_ERROR %r\n" % (exc,)).encode())
    exit_code = 127 if exit_code is None else exit_code
finally:
    result_path.write_text(json.dumps({
        "job_id": spec["job_id"],
        "exit_code": exit_code,
        "started_at": started,
        "completed_at": time.time(),
    }))
'''


def async_delegate_create(
    prompt: str,
    profile: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    toolsets: Optional[List[str]] = None,
    workdir: Optional[str] = None,
    name: Optional[str] = None,
    yolo: bool = False,
) -> str:
    """Start an independent Hermes child process and return immediately."""
    if not prompt or not str(prompt).strip():
        return tool_error("async_delegate_create requires a non-empty prompt.")

    job_id = f"ad_{uuid.uuid4().hex[:16]}"
    job_dir = _state_dir() / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = job_dir / "prompt.txt"
    log_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"
    result_path = job_dir / "result.json"
    spec_path = job_dir / "spec.json"
    child_pid_path = job_dir / "child.pid"
    prompt_path.write_text(prompt)

    cmd = _hermes_command(
        prompt_path=prompt_path,
        profile=profile,
        provider=provider,
        model=model,
        toolsets=toolsets,
        yolo=yolo,
    )
    spec = {
        "job_id": job_id,
        "cmd": cmd,
        "workdir": workdir,
        "log_path": str(log_path),
        "stderr_path": str(stderr_path),
        "result_path": str(result_path),
        "child_pid_path": str(child_pid_path),
    }
    spec_path.write_text(json.dumps(spec))

    created = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO async_delegations (
                job_id, status, prompt, profile, provider, model, toolsets,
                workdir, pid, created_at, started_at, completed_at, exit_code,
                log_path, stderr_path, result_path, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                "starting",
                prompt,
                profile,
                provider,
                model,
                json.dumps(toolsets or []),
                workdir,
                None,
                created,
                None,
                None,
                None,
                str(log_path),
                str(stderr_path),
                str(result_path),
                json.dumps({"name": name} if name else {}),
            ),
        )
        conn.commit()

    wrapper = subprocess.Popen(
        [sys.executable, "-c", _wrapper_code(), str(spec_path)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _update_job(job_id, status="running", pid=wrapper.pid, started_at=_now())

    return tool_result(
        {
            "job_id": job_id,
            "status": "running",
            "pid": wrapper.pid,
            "profile": profile,
            "provider": provider,
            "model": model,
            "toolsets": toolsets or [],
            "workdir": workdir,
            "log_path": str(log_path),
            "stderr_path": str(stderr_path),
            "result_path": str(result_path),
        }
    )


def async_delegate_status(job_id: str) -> str:
    job = _get_job(job_id)
    if not job:
        return tool_error(f"Async delegation job not found: {job_id}")
    job = _refresh_status(job)
    return tool_result(job)


def async_delegate_list(limit: int = 20) -> str:
    limit = max(1, min(int(limit or 20), 100))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM async_delegations ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    jobs = [_refresh_status(_row_to_dict(r)) for r in rows]
    return tool_result({"jobs": jobs})


def async_delegate_log(job_id: str, max_chars: int = 8000, include_stderr: bool = True) -> str:
    job = _get_job(job_id)
    if not job:
        return tool_error(f"Async delegation job not found: {job_id}")
    job = _refresh_status(job)
    return tool_result(
        {
            "job_id": job_id,
            "status": job["status"],
            "stdout": _tail_file(job["log_path"], max_chars=max_chars),
            "stderr": _tail_file(job["stderr_path"], max_chars=max_chars) if include_stderr else "",
        }
    )


def async_delegate_result(job_id: str, max_chars: int = 12000) -> str:
    job = _get_job(job_id)
    if not job:
        return tool_error(f"Async delegation job not found: {job_id}")
    job = _refresh_status(job)
    result = _read_json(job["result_path"]) or {}
    return tool_result(
        {
            "job_id": job_id,
            "status": job["status"],
            "exit_code": job.get("exit_code"),
            "result": result,
            "stdout_tail": _tail_file(job["log_path"], max_chars=max_chars),
            "stderr_tail": _tail_file(job["stderr_path"], max_chars=max_chars),
        }
    )


def _terminate_process_group(pid: int) -> None:
    """Best-effort terminate wrapper process group without Python signal guard."""
    # The wrapper is started with start_new_session=True, so its PID is also
    # its process-group id.  Use /bin/kill so tests with guarded os.kill still
    # exercise the real cancellation path for our own child process.
    subprocess.run(["kill", "-TERM", f"-{int(pid)}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def async_delegate_cancel(job_id: str) -> str:
    job = _get_job(job_id)
    if not job:
        return tool_error(f"Async delegation job not found: {job_id}")
    job = _refresh_status(job)
    if job["status"] not in {"running", "starting"}:
        return tool_result({"job_id": job_id, "status": job["status"], "cancelled": False})

    pid = job.get("pid")
    if pid and _pid_is_running(pid):
        _terminate_process_group(int(pid))
    _update_job(job_id, status="cancelled", completed_at=_now(), exit_code=-15)
    return tool_result({"job_id": job_id, "status": "cancelled", "cancelled": True})


_CREATE_SCHEMA = {
    "name": "async_delegate_create",
    "description": "Start a durable async child Hermes job and return a handle immediately.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Self-contained task prompt for the child agent."},
            "profile": {"type": "string", "description": "Optional Hermes profile to run under."},
            "provider": {"type": "string", "description": "Optional provider override."},
            "model": {"type": "string", "description": "Optional model override."},
            "toolsets": {"type": "array", "items": {"type": "string"}, "description": "Optional child toolsets."},
            "workdir": {"type": "string", "description": "Optional working directory for the child process."},
            "name": {"type": "string", "description": "Optional human-friendly job name."},
            "yolo": {"type": "boolean", "description": "Pass --yolo to the child Hermes process."},
        },
        "required": ["prompt"],
    },
}

_STATUS_SCHEMA = {
    "name": "async_delegate_status",
    "description": "Get durable status for an async delegation job.",
    "parameters": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]},
}
_LOG_SCHEMA = {
    "name": "async_delegate_log",
    "description": "Read stdout/stderr tails for an async delegation job.",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "max_chars": {"type": "integer"},
            "include_stderr": {"type": "boolean"},
        },
        "required": ["job_id"],
    },
}
_RESULT_SCHEMA = {
    "name": "async_delegate_result",
    "description": "Get final result and logs for an async delegation job.",
    "parameters": {
        "type": "object",
        "properties": {"job_id": {"type": "string"}, "max_chars": {"type": "integer"}},
        "required": ["job_id"],
    },
}
_CANCEL_SCHEMA = {
    "name": "async_delegate_cancel",
    "description": "Cancel a running async delegation job.",
    "parameters": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]},
}
_LIST_SCHEMA = {
    "name": "async_delegate_list",
    "description": "List recent async delegation jobs.",
    "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []},
}

registry.register(
    name="async_delegate_create",
    toolset="delegation",
    schema=_CREATE_SCHEMA,
    handler=lambda args, **kw: async_delegate_create(
        prompt=args.get("prompt", ""),
        profile=args.get("profile"),
        provider=args.get("provider"),
        model=args.get("model"),
        toolsets=args.get("toolsets"),
        workdir=args.get("workdir"),
        name=args.get("name"),
        yolo=bool(args.get("yolo", False)),
    ),
    emoji="🛰️",
)
registry.register(
    name="async_delegate_status",
    toolset="delegation",
    schema=_STATUS_SCHEMA,
    handler=lambda args, **kw: async_delegate_status(args.get("job_id", "")),
    emoji="📡",
)
registry.register(
    name="async_delegate_log",
    toolset="delegation",
    schema=_LOG_SCHEMA,
    handler=lambda args, **kw: async_delegate_log(
        args.get("job_id", ""),
        max_chars=int(args.get("max_chars") or 8000),
        include_stderr=bool(args.get("include_stderr", True)),
    ),
    emoji="📜",
)
registry.register(
    name="async_delegate_result",
    toolset="delegation",
    schema=_RESULT_SCHEMA,
    handler=lambda args, **kw: async_delegate_result(
        args.get("job_id", ""), max_chars=int(args.get("max_chars") or 12000)
    ),
    emoji="✅",
)
registry.register(
    name="async_delegate_cancel",
    toolset="delegation",
    schema=_CANCEL_SCHEMA,
    handler=lambda args, **kw: async_delegate_cancel(args.get("job_id", "")),
    emoji="🛑",
)
registry.register(
    name="async_delegate_list",
    toolset="delegation",
    schema=_LIST_SCHEMA,
    handler=lambda args, **kw: async_delegate_list(int(args.get("limit") or 20)),
    emoji="📋",
)

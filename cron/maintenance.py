"""File-backed cron maintenance mode and running-job tracking."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from hermes_time import now as _hermes_now
from utils import atomic_replace


class MaintenanceStateError(RuntimeError):
    """Raised when cron maintenance state exists but cannot be read."""


_RUNNING_FILE_LOCK = threading.Lock()


def _home(hermes_home: Path | str | None = None) -> Path:
    return Path(hermes_home).expanduser() if hermes_home is not None else get_hermes_home()


def maintenance_file(hermes_home: Path | str | None = None) -> Path:
    return _home(hermes_home) / "cron" / "maintenance.json"


def running_file(hermes_home: Path | str | None = None) -> Path:
    return _home(hermes_home) / "cron" / "running.json"


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise MaintenanceStateError(f"Could not read {path}: {exc}") from exc


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now_aware() -> datetime:
    current = _hermes_now()
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current


def read_maintenance(hermes_home: Path | str | None = None) -> dict | None:
    data = _read_json(maintenance_file(hermes_home))
    if data is None:
        return None
    if not isinstance(data, dict):
        raise MaintenanceStateError("maintenance.json must contain an object")
    return data


def is_maintenance_active(now: datetime | None = None, hermes_home: Path | str | None = None) -> bool:
    try:
        state = read_maintenance(hermes_home)
    except MaintenanceStateError:
        # Fail safe: a corrupt maintenance file should stop new cron dispatches.
        return True
    if not state or not state.get("active", True):
        return False
    until = state.get("until")
    if until:
        try:
            until_dt = _parse_datetime(str(until))
        except (TypeError, ValueError):
            return True
        current = now or _now_aware()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current <= until_dt
    return True


def start_maintenance(until: str | None = None, reason: str = "maintenance", owner: str | None = None, hermes_home: Path | str | None = None) -> dict:
    if until:
        _parse_datetime(until)
    state = {
        "active": True,
        "reason": reason or "maintenance",
        "started_at": _now_aware().isoformat(),
        "until": until,
        "owner": owner or f"pid:{os.getpid()}",
    }
    _atomic_write_json(maintenance_file(hermes_home), state)
    return state


def stop_maintenance(hermes_home: Path | str | None = None) -> bool:
    path = maintenance_file(hermes_home)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def list_running_jobs(hermes_home: Path | str | None = None, *, prune_stale: bool = True) -> list[dict]:
    data = _read_json(running_file(hermes_home))
    if data is None:
        return []
    if isinstance(data, dict):
        jobs = data.get("jobs", [])
    else:
        jobs = data
    if not isinstance(jobs, list):
        raise MaintenanceStateError("running.json must contain a jobs list")
    normalized = [j for j in jobs if isinstance(j, dict) and j.get("id")]
    if prune_stale:
        live = []
        changed = False
        for job in normalized:
            pid = job.get("pid")
            if pid is not None:
                try:
                    if not _pid_alive(int(pid)):
                        changed = True
                        continue
                except (TypeError, ValueError):
                    pass
            live.append(job)
        if changed:
            _write_running_jobs(live, hermes_home)
        normalized = live
    return normalized


def _write_running_jobs(jobs: list[dict], hermes_home: Path | str | None = None) -> None:
    path = running_file(hermes_home)
    if jobs:
        _atomic_write_json(path, {"jobs": jobs})
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def record_job_started(job: dict, hermes_home: Path | str | None = None) -> None:
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        return
    schedule = job.get("schedule")
    if isinstance(schedule, dict):
        schedule_display = job.get("schedule_display") or schedule.get("value")
    else:
        schedule_display = job.get("schedule_display") or schedule
    with _RUNNING_FILE_LOCK:
        try:
            jobs = [j for j in list_running_jobs(hermes_home) if j.get("id") != job_id]
        except MaintenanceStateError:
            jobs = []
        jobs.append({
            "id": job_id,
            "name": job.get("name"),
            "started_at": _now_aware().isoformat(),
            "pid": os.getpid(),
            "schedule": schedule_display,
            "workdir": job.get("workdir"),
            "profile": job.get("profile"),
        })
        _write_running_jobs(jobs, hermes_home)


def record_job_finished(job_id: str, hermes_home: Path | str | None = None) -> None:
    with _RUNNING_FILE_LOCK:
        try:
            jobs = [j for j in list_running_jobs(hermes_home, prune_stale=False) if j.get("id") != job_id]
        except MaintenanceStateError:
            jobs = []
        _write_running_jobs(jobs, hermes_home)


def drain(timeout_seconds: float, poll_seconds: float = 5.0, hermes_home: Path | str | None = None) -> bool:
    deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
    poll = max(float(poll_seconds), 0.1)
    while True:
        if not list_running_jobs(hermes_home):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(poll, max(0.0, deadline - time.monotonic())))

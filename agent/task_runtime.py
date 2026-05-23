"""Durable background task runtime for Hermes agent teams.

P0 design:
- durable task metadata/output/result under ~/.hermes/tasks
- active work runs in background threads
- execution reuses delegate_task so named agents, credentials, tool scopes,
  result schemas, artifacts, and existing safety behavior remain consistent
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from agent.task_runners import DelegateTaskRunner, select_task_runner
from hermes_constants import get_hermes_home

TERMINAL_STATUSES = {"completed", "failed", "stopped", "timeout"}
NON_TERMINAL_STATUSES = {"pending", "running", "stopping"}
_MAX_PARALLEL_TASKS_ENV = "HERMES_AGENT_TASK_MAX_PARALLEL"
_TASK_RETENTION_DAYS_ENV = "HERMES_AGENT_TASK_RETENTION_DAYS"
_RUNTIME_INSTANCE_ID = uuid.uuid4().hex
_ACTIVE_TASKS: Dict[str, "TaskControl"] = {}
_ACTIVE_LOCK = threading.RLock()


@dataclass
class TaskControl:
    task_id: str
    thread: threading.Thread
    stop_event: threading.Event
    parent_agent: Any = None


class TaskStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else Path(get_hermes_home()) / "tasks"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def task_dir(self, task_id: str) -> Path:
        return self.root / task_id

    def meta_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "meta.json"

    def events_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "events.jsonl"

    def output_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "output.log"

    def result_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "result.json"

    def create_task(
        self,
        *,
        goal: str,
        agent: Optional[str] = None,
        context: Optional[str] = None,
        runtime: Optional[str] = None,
        result_schema: Optional[dict] = None,
        toolsets: Optional[Iterable[str]] = None,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        task_id = f"task_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        task_dir = self.task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=False)
        now = time.time()
        meta = {
            "task_id": task_id,
            "status": "pending",
            "goal": goal,
            "agent": agent,
            "context": context or "",
            "runtime": runtime or "hermes_default",
            "result_schema": result_schema,
            "toolsets": list(toolsets or []),
            "timeout_seconds": timeout_seconds,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "ended_at": None,
            "runtime_pid": os.getpid(),
            "runtime_instance_id": _RUNTIME_INSTANCE_ID,
            "error": None,
            "artifact_dir": str(task_dir),
            "events_path": str(self.events_path(task_id)),
            "output_path": str(self.output_path(task_id)),
            "result_path": str(self.result_path(task_id)),
            "metadata": metadata or {},
        }
        self._write_json(self.meta_path(task_id), meta)
        self.events_path(task_id).touch()
        self.output_path(task_id).touch()
        self.append_event(task_id, "created", {"agent": agent, "runtime": meta["runtime"]})
        return meta

    def get_task(self, task_id: str) -> Optional[dict]:
        path = self.meta_path(task_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def update_task(self, task_id: str, **updates: Any) -> dict:
        with self._lock:
            meta = self.get_task(task_id)
            if meta is None:
                raise KeyError(f"Task not found: {task_id}")
            meta.update(updates)
            meta["updated_at"] = time.time()
            self._write_json(self.meta_path(task_id), meta)
            return meta

    def append_event(self, task_id: str, event: str, data: Optional[dict] = None) -> None:
        record = {"ts": time.time(), "event": event, "data": data or {}}
        with self._lock:
            with self.events_path(task_id).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def append_output(self, task_id: str, text: str) -> None:
        if not text:
            return
        with self._lock:
            with self.output_path(task_id).open("a", encoding="utf-8") as fh:
                fh.write(text)
                if not text.endswith("\n"):
                    fh.write("\n")

    def write_result(self, task_id: str, result: dict) -> None:
        self._write_json(self.result_path(task_id), result)

    def read_result(self, task_id: str) -> Optional[dict]:
        path = self.result_path(task_id)
        if not path.exists() or path.stat().st_size == 0:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def read_output(self, task_id: str, max_chars: int = 6000) -> str:
        path = self.output_path(task_id)
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if max_chars and len(text) > max_chars:
            return text[-max_chars:]
        return text

    def list_tasks(self, status: Optional[str] = None, limit: int = 20) -> list[dict]:
        metas = []
        for meta in self._iter_task_metas():
            if status and meta.get("status") != status:
                continue
            metas.append(meta)
        metas.sort(key=lambda item: item.get("created_at", 0), reverse=True)
        if limit is None:
            return metas
        return metas[:limit]

    def recover_stale_tasks(self) -> list[dict]:
        recovered = []
        for meta in self._iter_task_metas():
            status = meta.get("status")
            task_id = meta.get("task_id")
            if not task_id or status not in NON_TERMINAL_STATUSES:
                continue
            if _task_has_live_control(task_id):
                continue
            if _task_owner_process_is_alive(meta):
                continue

            new_status = "stopped" if status == "stopping" else "failed"
            error = meta.get("error") or f"Task recovered as stale from {status}; no live runtime owner"
            self.append_event(task_id, "stale_recovered", {"from_status": status, "status": new_status, "error": error})
            recovered.append(self.update_task(task_id, status=new_status, ended_at=time.time(), error=error))
        return recovered

    def cleanup_artifacts(
        self,
        *,
        retention_days: Optional[float] = None,
        retention_seconds: Optional[float] = None,
        keep_last: Optional[int] = None,
        terminal_only: bool = True,
        now: Optional[float] = None,
    ) -> dict:
        if retention_days is not None and retention_seconds is not None:
            raise ValueError("Specify either retention_days or retention_seconds, not both")
        if retention_days is None and retention_seconds is None:
            retention_days = _configured_retention_days()

        now = time.time() if now is None else now
        cutoff = None
        if retention_seconds is not None:
            cutoff = now - float(retention_seconds)
        elif retention_days is not None:
            cutoff = now - (float(retention_days) * 86400)

        metas = self.list_tasks(limit=None)
        keep_ids = set()
        if keep_last and keep_last > 0:
            keep_ids = {meta.get("task_id") for meta in metas[:keep_last]}

        report = {"deleted": [], "kept": [], "errors": []}
        if cutoff is None and not keep_ids:
            return report
        for meta in metas:
            task_id = meta.get("task_id")
            if not task_id:
                continue
            if task_id in keep_ids:
                report["kept"].append(task_id)
                continue
            if terminal_only and meta.get("status") not in TERMINAL_STATUSES:
                report["kept"].append(task_id)
                continue
            if _task_has_live_control(task_id):
                report["kept"].append(task_id)
                continue
            ref_ts = meta.get("ended_at") or meta.get("updated_at") or meta.get("created_at") or 0
            if cutoff is not None and ref_ts > cutoff:
                report["kept"].append(task_id)
                continue

            try:
                shutil.rmtree(self.task_dir(task_id))
                report["deleted"].append(task_id)
            except FileNotFoundError:
                report["deleted"].append(task_id)
            except Exception as exc:
                report["errors"].append({"task_id": task_id, "error": str(exc)})
        return report

    def diagnostics(self) -> dict:
        metas = self.list_tasks(limit=None)
        status_counts: dict[str, int] = {}
        stale_candidates = []
        artifact_bytes = 0
        for meta in metas:
            status = meta.get("status") or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
            task_id = meta.get("task_id")
            if task_id and status in NON_TERMINAL_STATUSES and not _task_has_live_control(task_id) and not _task_owner_process_is_alive(meta):
                stale_candidates.append(task_id)
            task_dir = self.task_dir(task_id) if task_id else None
            if task_dir and task_dir.exists():
                for path in task_dir.rglob("*"):
                    if path.is_file():
                        try:
                            artifact_bytes += path.stat().st_size
                        except OSError:
                            pass

        max_parallel_error = None
        try:
            max_parallel_tasks = _configured_max_parallel_tasks()
        except ValueError as exc:
            max_parallel_tasks = None
            max_parallel_error = str(exc)

        active_tasks = _active_task_snapshot()
        return {
            "root": str(self.root),
            "task_count": len(metas),
            "status_counts": status_counts,
            "active_count": len(active_tasks),
            "active_tasks": active_tasks,
            "stale_task_ids": stale_candidates,
            "artifact_bytes": artifact_bytes,
            "max_parallel_tasks": max_parallel_tasks,
            "max_parallel_config_error": max_parallel_error,
            "blocked_by_parallel_limit": bool(max_parallel_tasks and len(active_tasks) >= max_parallel_tasks),
        }

    def _iter_task_metas(self) -> Iterable[dict]:
        for path in self.root.glob("task_*/meta.json"):
            try:
                yield json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def _configured_retention_days() -> Optional[float]:
    raw = os.environ.get(_TASK_RETENTION_DAYS_ENV)
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{_TASK_RETENTION_DAYS_ENV} must be a number") from exc
    if value < 0:
        raise ValueError(f"{_TASK_RETENTION_DAYS_ENV} must be non-negative")
    return value


def _configured_max_parallel_tasks(max_parallel_tasks: Optional[int] = None) -> Optional[int]:
    raw: Any = max_parallel_tasks
    if raw is None:
        raw = os.environ.get(_MAX_PARALLEL_TASKS_ENV)
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"max_parallel_tasks must be an integer") from exc
    if value <= 0:
        return None
    return value


def _control_is_live(control: TaskControl) -> bool:
    return control.thread.ident is None or control.thread.is_alive()


def _task_has_live_control(task_id: str) -> bool:
    with _ACTIVE_LOCK:
        control = _ACTIVE_TASKS.get(task_id)
        if control is None:
            return False
        if _control_is_live(control):
            return True
        _ACTIVE_TASKS.pop(task_id, None)
        return False


def _active_task_snapshot() -> list[dict]:
    with _ACTIVE_LOCK:
        stale_controls = [task_id for task_id, control in _ACTIVE_TASKS.items() if not _control_is_live(control)]
        for task_id in stale_controls:
            _ACTIVE_TASKS.pop(task_id, None)
        return [
            {
                "task_id": task_id,
                "thread_name": control.thread.name,
                "stop_requested": control.stop_event.is_set(),
                "thread_alive": control.thread.is_alive(),
            }
            for task_id, control in _ACTIVE_TASKS.items()
        ]


def _task_owner_process_is_alive(meta: dict) -> bool:
    pid = meta.get("runtime_pid")
    if pid is None:
        return False
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    if pid_int == os.getpid():
        return meta.get("runtime_instance_id") == _RUNTIME_INSTANCE_ID
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _enforce_max_parallel_tasks(max_parallel_tasks: Optional[int]) -> None:
    limit = _configured_max_parallel_tasks(max_parallel_tasks)
    if not limit:
        return
    active_count = len(_active_task_snapshot())
    if active_count >= limit:
        raise RuntimeError(f"max_parallel_tasks limit reached ({active_count}/{limit}); wait for an active agent task to finish")


def default_store() -> TaskStore:
    return TaskStore()


def start_agent_task(
    *,
    goal: str,
    agent: Optional[str] = None,
    context: Optional[str] = None,
    runtime: Optional[str] = None,
    result_schema: Optional[dict] = None,
    toolsets: Optional[Iterable[str]] = None,
    timeout_seconds: Optional[int] = None,
    max_parallel_tasks: Optional[int] = None,
    retention_days: Optional[float] = None,
    metadata: Optional[dict] = None,
    parent_agent: Any = None,
    store: Optional[TaskStore] = None,
    runner: Optional[Callable[[dict, threading.Event, Any, TaskStore], dict]] = None,
) -> dict:
    store = store or default_store()
    store.recover_stale_tasks()
    store.cleanup_artifacts(retention_days=retention_days)
    _enforce_max_parallel_tasks(max_parallel_tasks)
    meta = store.create_task(
        goal=goal,
        agent=agent,
        context=context,
        runtime=runtime,
        result_schema=result_schema,
        toolsets=toolsets,
        timeout_seconds=timeout_seconds,
        metadata=metadata,
    )
    task_id = meta["task_id"]
    stop_event = threading.Event()
    selected_runner = runner or select_task_runner(meta)

    def target() -> None:
        store.update_task(task_id, status="running", started_at=time.time())
        store.append_event(task_id, "started", {"agent": agent, "runtime": meta.get("runtime")})
        try:
            result = _run_runner_with_optional_timeout(
                selected_runner,
                meta,
                stop_event,
                parent_agent,
                store,
                timeout_seconds,
            )
            store.write_result(task_id, result or {})
            status = "stopped" if stop_event.is_set() else "completed"
            store.append_event(task_id, status, {})
            store.update_task(task_id, status=status, ended_at=time.time(), error=None)
        except TimeoutError as exc:
            store.append_event(task_id, "timeout", {"error": str(exc)})
            store.update_task(task_id, status="timeout", ended_at=time.time(), error=str(exc))
        except Exception as exc:
            store.append_event(task_id, "failed", {"error": str(exc)})
            store.update_task(task_id, status="failed", ended_at=time.time(), error=str(exc))
            store.append_output(task_id, f"[task failed] {exc}")
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_TASKS.pop(task_id, None)

    thread = threading.Thread(target=target, name=f"hermes-agent-task-{task_id}", daemon=True)
    with _ACTIVE_LOCK:
        _ACTIVE_TASKS[task_id] = TaskControl(task_id=task_id, thread=thread, stop_event=stop_event, parent_agent=parent_agent)
    thread.start()
    return store.get_task(task_id) or meta


def _run_runner_with_optional_timeout(
    runner: Callable[[dict, threading.Event, Any, TaskStore], dict],
    meta: dict,
    stop_event: threading.Event,
    parent_agent: Any,
    store: TaskStore,
    timeout_seconds: Optional[int],
) -> dict:
    if not timeout_seconds:
        return runner(meta, stop_event, parent_agent, store)
    if timeout_seconds <= 0:
        raise TimeoutError("timeout_seconds must be positive")

    holder: dict[str, Any] = {}

    def run_inner() -> None:
        try:
            holder["result"] = runner(meta, stop_event, parent_agent, store)
        except BaseException as exc:
            holder["error"] = exc

    inner = threading.Thread(target=run_inner, name=f"hermes-agent-task-runner-{meta['task_id']}", daemon=True)
    inner.start()
    inner.join(timeout_seconds)
    if inner.is_alive():
        stop_event.set()
        raise TimeoutError(f"Agent task timed out after {timeout_seconds} seconds")
    if "error" in holder:
        raise holder["error"]
    return holder.get("result") or {}


def _run_with_delegate_task(meta: dict, stop_event: threading.Event, parent_agent: Any, store: TaskStore) -> dict:
    return DelegateTaskRunner()(meta, stop_event, parent_agent, store)


def get_task(task_id: str, store: Optional[TaskStore] = None) -> Optional[dict]:
    return (store or default_store()).get_task(task_id)


def list_tasks(status: Optional[str] = None, limit: int = 20, store: Optional[TaskStore] = None) -> list[dict]:
    return (store or default_store()).list_tasks(status=status, limit=limit)


def recover_stale_tasks(store: Optional[TaskStore] = None) -> list[dict]:
    return (store or default_store()).recover_stale_tasks()


def cleanup_task_artifacts(
    *,
    retention_days: Optional[float] = None,
    retention_seconds: Optional[float] = None,
    keep_last: Optional[int] = None,
    terminal_only: bool = True,
    now: Optional[float] = None,
    store: Optional[TaskStore] = None,
) -> dict:
    return (store or default_store()).cleanup_artifacts(
        retention_days=retention_days,
        retention_seconds=retention_seconds,
        keep_last=keep_last,
        terminal_only=terminal_only,
        now=now,
    )


def task_runtime_diagnostics(store: Optional[TaskStore] = None) -> dict:
    return (store or default_store()).diagnostics()


def diagnose_task_runtime(store: Optional[TaskStore] = None) -> dict:
    return task_runtime_diagnostics(store=store)


def read_task_output(task_id: str, max_chars: int = 6000, store: Optional[TaskStore] = None) -> dict:
    store = store or default_store()
    meta = store.get_task(task_id)
    if meta is None:
        raise KeyError(f"Task not found: {task_id}")
    return {"task": meta, "output": store.read_output(task_id, max_chars=max_chars), "result": store.read_result(task_id)}


def stop_task(task_id: str, store: Optional[TaskStore] = None) -> dict:
    store = store or default_store()
    meta = store.get_task(task_id)
    if meta is None:
        raise KeyError(f"Task not found: {task_id}")
    with _ACTIVE_LOCK:
        control = _ACTIVE_TASKS.get(task_id)
    if control:
        control.stop_event.set()
        store.append_event(task_id, "stop_requested", {})
        return store.update_task(task_id, status="stopping")
    if meta.get("status") not in TERMINAL_STATUSES:
        return store.update_task(task_id, status="stopped", ended_at=time.time())
    return meta


def wait_for_task(task_id: str, timeout_seconds: float = 0, store: Optional[TaskStore] = None) -> dict:
    store = store or default_store()
    deadline = time.time() + timeout_seconds if timeout_seconds else None
    while True:
        meta = store.get_task(task_id)
        if meta is None:
            raise KeyError(f"Task not found: {task_id}")
        if meta.get("status") in TERMINAL_STATUSES:
            return meta
        if deadline and time.time() >= deadline:
            return meta
        time.sleep(0.2)

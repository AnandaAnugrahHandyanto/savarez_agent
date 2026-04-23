from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any, Optional

from agent.task_store import TaskStatus, TaskStore


class BackgroundDelegateLaunchError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_background_delegate_command(task_id: str, store_root: str) -> str:
    code = (
        "from tools.delegate_tool import run_persistent_delegate_task; "
        f"run_persistent_delegate_task({task_id!r}, {store_root!r})"
    )
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def _wrap_background_command(command: str, exit_code_path: str) -> str:
    quoted_exit_path = shlex.quote(exit_code_path)
    return (
        "bash -lc "
        + shlex.quote(
            f"{command}; rc=$?; mkdir -p {shlex.quote(str(Path(exit_code_path).parent))}; "
            f"printf '%s\\n' \"$rc\" > {quoted_exit_path}; exit $rc"
        )
    )


def _ensure_failed_launch_state(
    task_store: TaskStore,
    task_id: str,
    *,
    error: str,
    command: Optional[str] = None,
) -> None:
    record = task_store.require_task(task_id)
    if record.execution.status == TaskStatus.draft:
        record = task_store.transition_task(task_id, TaskStatus.queued, background=True)
    if record.execution.status not in {TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled}:
        task_store.record_result(
            task_id,
            status=TaskStatus.failed,
            result={"error": error, "command": command},
            summary=record.summary,
            error=error,
            exit_code=record.execution.exit_code,
        )


def _build_background_payload(record, *, process_state: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    process_state = dict(process_state or {})
    payload = {
        "task_id": record.id,
        "persistent": True,
        "background": bool(record.execution.background),
        "status": record.execution.status.value,
        "summary": record.summary,
        "result": record.execution.result,
        "error": record.execution.last_error,
        "exit_code": record.execution.exit_code,
        "owner_session_id": record.owner_session_id,
        "session_delegation_id": record.session_delegation_id,
        "process_session_id": record.execution.process_session_id,
        "process_command": record.execution.process_command,
        "process_task_id": record.execution.process_task_id,
    }
    if process_state:
        payload["process"] = process_state
        if process_state.get("status"):
            payload["process_status"] = process_state.get("status")
        if process_state.get("pid") is not None:
            payload["pid"] = process_state.get("pid")
        if process_state.get("output_preview"):
            payload["output_preview"] = process_state.get("output_preview")
    return payload


def launch_background_delegate_task(
    task_id: str,
    *,
    store: Optional[TaskStore] = None,
    process_registry_obj=None,
) -> dict[str, Any]:
    from tools.process_registry import process_registry as default_process_registry

    task_store = store or TaskStore()
    registry = process_registry_obj or default_process_registry
    record = task_store.require_task(task_id)
    launch_spec = dict(record.launch_spec or {})
    if launch_spec.get("runner") != "delegate":
        raise ValueError(f"task {task_id} is not a delegate-backed persistent task")

    command = _build_background_delegate_command(task_id, str(task_store.root_dir))
    task_store.clear_delegate_exit_artifact(task_id)
    exit_code_path = str(task_store.root_dir / f"{task_id}.exit")
    wrapped_command = _wrap_background_command(command, exit_code_path)
    proc_session = None
    try:
        proc_session = registry.spawn_local(
            command=wrapped_command,
            cwd=str(_repo_root()),
            task_id=task_id,
        )
        registry.attach_task(
            proc_session.id,
            linked_task_id=task_id,
            store_root=str(task_store.root_dir),
            task_kind="delegate_background",
            exit_code_path=exit_code_path,
        )
        record = task_store.attach_process(
            task_id,
            process_session_id=proc_session.id,
            process_command=command,
            process_task_id=task_id,
            background=True,
        )
        process_state = registry.poll(proc_session.id)
        return _build_background_payload(record, process_state=process_state)
    except Exception as exc:
        cleanup_error = None
        if proc_session is not None and getattr(proc_session, "id", None):
            try:
                cleanup_result = registry.kill_process(proc_session.id)
                if cleanup_result.get("status") == "error":
                    cleanup_error = cleanup_result.get("error") or "unknown cleanup failure"
            except Exception as cleanup_exc:
                cleanup_error = str(cleanup_exc)
        error_message = str(exc)
        if cleanup_error:
            error_message = f"{error_message}; cleanup_error={cleanup_error}"
        _ensure_failed_launch_state(task_store, task_id, error=error_message, command=command)
        raise BackgroundDelegateLaunchError(error_message) from exc


def get_background_delegate_result(
    task_id: str,
    *,
    store: Optional[TaskStore] = None,
    process_registry_obj=None,
) -> dict[str, Any]:
    from tools.process_registry import process_registry as default_process_registry

    task_store = store or TaskStore()
    registry = process_registry_obj or default_process_registry
    record = task_store.reconcile_task(task_id, process_registry=registry)
    process_state = None
    linked_sessions = registry.get_linked_sessions(task_id)
    if record.execution.process_session_id:
        process_state = registry.poll(record.execution.process_session_id)
    elif linked_sessions:
        # Keep recent process context available even after the task is terminal.
        newest = max(linked_sessions, key=lambda session: session.started_at)
        process_state = registry.poll(newest.id)
    return _build_background_payload(record, process_state=process_state)


__all__ = [
    "BackgroundDelegateLaunchError",
    "get_background_delegate_result",
    "launch_background_delegate_task",
]

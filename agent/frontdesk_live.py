"""Opt-in live frontdesk pre-dispatch helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from utils import is_truthy_value


_DEFAULT_WORKER_LANE = "main"
_DEFAULT_WORKER_TIMEOUT_SECONDS = 60 * 60
_COMPLETION_NOTICE_LIMIT = 1200
_FRONTDESK_NOTIFIERS: dict[tuple[int, str | None], Callable[[str], Any]] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _worker_prompt(goal: str) -> str:
    return (
        "You are a background worker lane launched by Hermes frontdesk. "
        "Complete the user's task independently. Do not ask clarification unless absolutely impossible. "
        "If the task references local files, inspect and edit them directly as requested. "
        "Return a concise Korean completion report with paths/artifacts changed and any caveats.\n\n"
        f"USER TASK:\n{goal}"
    )


def _run_default_worker_subprocess(goal: str, token: Any) -> str:
    """Run one frontdesk worker task in a detached Hermes oneshot subprocess."""
    cmd = [sys.executable, "-m", "hermes_cli.main", "-z", _worker_prompt(goal)]
    env = dict(os.environ)
    env["HERMES_FRONTDESK_WORKER"] = "1"
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(
        cmd,
        cwd=str(_repo_root()),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    started = time.monotonic()
    while proc.poll() is None:
        if getattr(token, "cancelled", False):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            from agent.worker_lanes import WorkerCancelled

            raise WorkerCancelled("frontdesk worker cancelled")
        if time.monotonic() - started > _DEFAULT_WORKER_TIMEOUT_SECONDS:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
            raise TimeoutError(
                f"frontdesk worker timed out after {_DEFAULT_WORKER_TIMEOUT_SECONDS}s\n{stderr or stdout}"
            )
        time.sleep(0.5)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        detail = (stderr or stdout or "").strip()
        raise RuntimeError(f"frontdesk worker exited {proc.returncode}: {detail}")
    return (stdout or "").strip() or "worker completed with no output"


def _completion_notice(task_id: str | None, summary: str) -> str:
    text = summary.strip()
    if len(text) > _COMPLETION_NOTICE_LIMIT:
        text = text[: _COMPLETION_NOTICE_LIMIT - 1].rstrip() + "…"
    return f"worker complete: {task_id or 'untracked'}\n\n{text}"


def _linked_worker_id(runtime: Any, task_id: str | None) -> str | None:
    if not task_id:
        return None
    for _ in range(20):
        task = runtime.task_registry.get_task(task_id)
        worker_id = getattr(task, "active_worker_id", None) if task is not None else None
        if isinstance(worker_id, str) and worker_id:
            return worker_id
        time.sleep(0.01)
    return None


def _attach_worker_result(
    runtime: Any,
    *,
    task_id: str | None,
    worker_id: str | None,
    status: str,
    summary: str,
    error: str | None = None,
) -> None:
    if task_id is None:
        return
    payload = {
        "worker_id": worker_id,
        "task_id": task_id,
        "status": status,
        "summary": summary,
    }
    if error:
        payload["error"] = error
    try:
        runtime.attach_worker_result(
            task_id=task_id,
            worker_id=worker_id or "",
            result=payload,
        )
    except Exception:
        try:
            runtime.task_registry.attach_worker_result(task_id, payload)
        except Exception:
            pass


def ensure_default_worker_lane(
    owner: Any,
    *,
    session_key: str | None = None,
    notify_callback: Callable[[str], Any] | None = None,
) -> None:
    """Ensure every live frontdesk runtime has a default worker lane.

    The live gate must not expose a worker-capable control plane with an empty
    registry.  This registers one conservative Hermes oneshot-backed lane per
    runtime.  Results are also pushed back through a per-session notifier when a
    gateway/TUI surface supplies one.
    """
    from agent.orchestration_runtime import get_or_create_orchestration_runtime
    from agent.worker_lanes import ThreadWorkerLane, WorkerSpec, CancelToken

    runtime = get_or_create_orchestration_runtime(owner)
    if notify_callback is not None:
        _FRONTDESK_NOTIFIERS[(id(owner), session_key)] = notify_callback

    if _DEFAULT_WORKER_LANE in runtime.worker_registry.lane_names():
        return

    owner_id = id(owner)
    run_default_worker = _run_default_worker_subprocess

    def runner(spec: WorkerSpec, token: CancelToken) -> str:
        worker_id = _linked_worker_id(runtime, spec.task_id)
        try:
            result = run_default_worker(spec.goal, token)
        except BaseException as exc:
            from agent.worker_lanes import WorkerCancelled

            status = "cancelled" if isinstance(exc, WorkerCancelled) else "failed"
            summary = "worker cancelled" if status == "cancelled" else "worker failed"
            _attach_worker_result(
                runtime,
                task_id=spec.task_id,
                worker_id=worker_id,
                status=status,
                summary=summary,
                error=str(exc) or type(exc).__name__,
            )
            raise
        _attach_worker_result(
            runtime,
            task_id=spec.task_id,
            worker_id=worker_id,
            status="succeeded",
            summary=result,
        )
        sk = None
        if isinstance(spec.metadata, dict):
            raw_sk = spec.metadata.get("session_key")
            sk = raw_sk if isinstance(raw_sk, str) else None
        notifier = _FRONTDESK_NOTIFIERS.get((owner_id, sk)) or _FRONTDESK_NOTIFIERS.get(
            (owner_id, None)
        )
        if notifier is not None:
            try:
                notifier(_completion_notice(spec.task_id, result))
            except Exception:
                pass
        return result

    runtime.worker_registry.register(ThreadWorkerLane(runner=runner, name=_DEFAULT_WORKER_LANE))


def frontdesk_live_enabled(owner: Any, *, session: dict | None = None) -> bool:
    """Return whether live frontdesk interception is explicitly enabled."""
    for carrier in (session, owner):
        if not carrier:
            continue
        if isinstance(carrier, dict):
            if "frontdesk_live_enabled" in carrier:
                return bool(carrier.get("frontdesk_live_enabled"))
            cfg = carrier.get("config")
        else:
            if hasattr(carrier, "frontdesk_live_enabled"):
                return bool(getattr(carrier, "frontdesk_live_enabled"))
            if hasattr(carrier, "_frontdesk_live_enabled"):
                return bool(getattr(carrier, "_frontdesk_live_enabled"))
            cfg = getattr(carrier, "config", None)
        if isinstance(cfg, dict):
            orchestration = cfg.get("orchestration") or {}
            if isinstance(orchestration, dict):
                raw = orchestration.get("frontdesk_live_enabled")
                if raw is not None:
                    return is_truthy_value(raw, default=False)
    return False


def handle_frontdesk_live_input(
    owner: Any,
    request_text: Any,
    *,
    session: dict | None = None,
    session_key: str | None = None,
    source_surface: str,
    main_in_flight: bool = False,
    steer_callback: Callable[[str], Any] | None = None,
    cancel_callback: Callable[[str], Any] | None = None,
    notify_callback: Callable[[str], Any] | None = None,
):
    """Run the frontdesk control gate and return a consumed result or ``None``.

    ``None`` means the caller should continue its existing main-model path.
    Every non-``None`` result is a local control response and must not be
    enqueued, replayed, or sent to the main model.
    """
    if not frontdesk_live_enabled(owner, session=session):
        return None
    if not isinstance(request_text, str) or not request_text.strip():
        return None

    from agent.orchestration_runtime import (
        OrchestrationRuntime,
        get_or_create_orchestration_runtime,
    )

    if session is None:
        ensure_default_worker_lane(
            owner,
            session_key=session_key,
            notify_callback=notify_callback,
        )

    runtime_owner = session if session is not None else owner
    if isinstance(runtime_owner, dict):
        runtime = runtime_owner.get("_orchestration_runtime")
        if not isinstance(runtime, OrchestrationRuntime):
            runtime = OrchestrationRuntime.create()
            runtime_owner["_orchestration_runtime"] = runtime
    else:
        runtime = get_or_create_orchestration_runtime(runtime_owner)
    result = runtime.handle_frontdesk_input(
        request_text,
        frontdesk_mode_active=True,
        session_key=session_key,
        source_surface=source_surface,
        main_in_flight=main_in_flight,
        steer_callback=steer_callback,
    )
    if result.action == "main":
        return None
    if result.action == "stopped" and cancel_callback is not None:
        cancel_callback(request_text)
    return result

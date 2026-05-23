"""Task runner abstraction for durable Hermes agent tasks."""

from __future__ import annotations

import json
import threading
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Protocol


_DELEGATE_PARENT_LOCKS: dict[int, threading.RLock] = {}
_DELEGATE_PARENT_LOCKS_GUARD = threading.RLock()


def _parent_delegate_lock(parent_agent: Any):
    if parent_agent is None:
        return nullcontext()
    key = id(parent_agent)
    with _DELEGATE_PARENT_LOCKS_GUARD:
        lock = _DELEGATE_PARENT_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _DELEGATE_PARENT_LOCKS[key] = lock
        return lock


def run_delegate_task_with_parent_lock(parent_agent: Any, **kwargs: Any) -> str:
    with _parent_delegate_lock(parent_agent):
        from tools.delegate_tool import delegate_task

        return delegate_task(parent_agent=parent_agent, **kwargs)


class TaskRunner(Protocol):
    name: str

    def __call__(self, meta: dict, stop_event: threading.Event, parent_agent: Any, store: Any) -> dict:
        """Run a task and return a JSON-serializable result payload."""


@dataclass(frozen=True)
class DelegateTaskRunner:
    """Run a task through Hermes delegate_task, preserving existing behavior."""

    name: str = "delegate_task"

    def __call__(self, meta: dict, stop_event: threading.Event, parent_agent: Any, store: Any) -> dict:
        if parent_agent is None:
            raise RuntimeError("agent_task_create requires a parent agent for real execution")
        if stop_event.is_set():
            return {"status": "stopped", "reason": "stop requested before execution"}

        store.append_output(meta["task_id"], f"[agent_task] delegating to {meta.get('agent') or 'default'}")
        raw = run_delegate_task_with_parent_lock(
            parent_agent,
            goal=meta["goal"],
            context=meta.get("context") or "",
            agent=meta.get("agent"),
            result_schema=meta.get("result_schema"),
            toolsets=meta.get("toolsets") or None,
        )
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            parsed = {"raw": raw}
        if isinstance(parsed, dict) and parsed.get("summary"):
            store.append_output(meta["task_id"], str(parsed["summary"]))
        return {"delegate_task": parsed}


class CodexTaskRunnerUnavailable(RuntimeError):
    """Raised when the Codex runner is selected but no safe implementation is wired."""


@dataclass(frozen=True)
class CodexTaskRunner:
    """Explicit Codex runner interface/stub.

    This runner intentionally does not call Hermes delegate_task or use a parent
    Hermes agent. Until a real Codex app-server execution bridge is wired, it
    fails clearly instead of pretending the task ran.
    """

    name: str = "codex_app_server_stub"

    def __call__(self, meta: dict, stop_event: threading.Event, parent_agent: Any, store: Any) -> dict:
        if stop_event.is_set():
            return {"status": "stopped", "reason": "stop requested before execution", "runner": self.name}

        message = (
            "Codex task runner selected for "
            f"runtime={meta.get('runtime')!r}, agent={meta.get('agent')!r}, "
            "but real Codex execution is not safely wired yet. "
            "This stub does not expose Hermes loop tools and did not execute the task."
        )
        store.append_output(meta["task_id"], f"[agent_task] {message}")
        raise CodexTaskRunnerUnavailable(message)


def should_use_codex_runner(meta: dict) -> bool:
    runtime = str(meta.get("runtime") or "").strip().lower()
    agent = str(meta.get("agent") or "").strip().lower()
    return runtime == "codex_app_server" or agent == "coder"


def select_task_runner(meta: dict) -> TaskRunner:
    if should_use_codex_runner(meta):
        return CodexTaskRunner()
    return DelegateTaskRunner()

"""Worker-spawn runtime strategy for the kanban dispatcher.

This module isolates *how* a kanban worker process gets created from *when*
the dispatcher decides to spawn one. The dispatcher remains responsible for
claim acquisition, DAG promotion, retry policy, and PID-tracking; the
runtime is responsible only for "produce a handle to a running worker
that has the supplied env contract."

Contract: every runtime gets the same env vars in scope (HERMES_KANBAN_*,
HERMES_PROFILE, HERMES_TENANT, etc.) and must launch a process that runs
``hermes -p <profile> --skills kanban-worker chat -q "work kanban task <id>"``.

The default ``LocalRuntime`` is a thin wrapper around ``_default_spawn`` in
``hermes_cli/kanban_db.py`` so that ``worker_runtime: local`` is byte-identical
to pre-D1 behavior.

See also:
    ~/.hermes/plans/2026-05-12-d1-kanban-worker-runtime.md  (this file's plan)
    ~/.hermes/skills/software-development/mission-control-architecture/SKILL.md
"""
from __future__ import annotations

import logging
import os
import signal
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class WorkerRuntime(Protocol):
    """Strategy interface for spawning kanban workers.

    Implementations:
      - LocalRuntime — bare subprocess (today's default)
      - DockerRuntime — `docker run --rm` per-task container (D1 Task 3)
      - (future) ModalRuntime, SSHRuntime, etc.

    Attributes:
        name: short identifier matching the config key
              (`local`, `docker`, `modal`, `ssh`).

    Methods:
        spawn(task, workspace, board=None) -> handle:
            Launch a worker. Returns a *handle* (int PID for local/ssh,
            container_id string for docker, Modal call_id for modal).
            Must be string-able and stable for the worker's lifetime.
            ``None`` indicates a benign skip (e.g. dry-run or already-running).
            Raise on unrecoverable errors (image missing, daemon down, etc.).
        is_alive(handle) -> bool:
            Probe whether the worker is still running. Best-effort; the
            dispatcher's claim-TTL logic remains the authoritative
            crash detector.
        terminate(handle, reason) -> None:
            Best-effort SIGTERM (or container kill). Used by `kanban
            reclaim` and shutdown paths.
    """

    name: str

    def spawn(
        self,
        task: Any,
        workspace: str,
        *,
        board: Optional[str] = None,
    ) -> Optional[int | str]: ...

    def is_alive(self, handle: int | str) -> bool: ...

    def terminate(self, handle: int | str, reason: str = "") -> None: ...


# ---------------------------------------------------------------------------
# LocalRuntime — the regression-safe default
# ---------------------------------------------------------------------------

class LocalRuntime:
    """Today's behavior: ``hermes`` on PATH via subprocess.Popen.

    Wraps ``hermes_cli.kanban_db._default_spawn`` so ``worker_runtime: local``
    is byte-identical to pre-D1 behavior.
    """

    name = "local"

    def __init__(self, cfg: Optional[dict] = None) -> None:
        # No config consumed at v1. Reserved for future fields like
        # `start_new_session`, `cgroup_path`, etc.
        self._cfg = cfg or {}

    def spawn(
        self,
        task: Any,
        workspace: str,
        *,
        board: Optional[str] = None,
    ) -> Optional[int]:
        # Lazy import to avoid a circular dep with kanban_db (which imports
        # things from gateway/run.py at module top, and gateway/run.py may
        # in turn import this module via the runtime-loading helper).
        from hermes_cli import kanban_db
        return kanban_db._default_spawn(task, workspace, board=board)

    def is_alive(self, handle: int | str) -> bool:
        try:
            pid = int(handle)
        except (TypeError, ValueError):
            return False
        if pid <= 0:
            return False
        try:
            # Signal 0 doesn't kill; just probes existence.
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
        except OSError:
            return False

    def terminate(self, handle: int | str, reason: str = "") -> None:
        try:
            pid = int(handle)
        except (TypeError, ValueError):
            return
        if pid <= 0:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("LocalRuntime: SIGTERM pid=%d (%s)", pid, reason)
        except ProcessLookupError:
            pass  # Already dead; not an error.
        except OSError as exc:
            logger.warning(
                "LocalRuntime: terminate failed pid=%d: %s", pid, exc
            )


# ---------------------------------------------------------------------------
# Factory + registry
# ---------------------------------------------------------------------------

# Registry — populated below. D1 Task 3 extends with DockerRuntime;
# future deliverables add ModalRuntime / SSHRuntime via register_runtime().
_RUNTIMES: dict[str, type] = {
    "local": LocalRuntime,
}


def register_runtime(name: str, cls: type) -> None:
    """Register a new runtime implementation.

    Used by D1 Task 3 (DockerRuntime), future deliverables, and tests
    that need to swap in a fake runtime.

    Raises ValueError if ``name`` is already registered — re-registration
    is almost always a bug (two plugins fighting over the same key).
    """
    if name in _RUNTIMES:
        raise ValueError(
            f"runtime {name!r} already registered "
            f"(existing: {_RUNTIMES[name].__name__})"
        )
    _RUNTIMES[name] = cls


def load_runtime(name: str, cfg: Optional[dict] = None) -> WorkerRuntime:
    """Resolve a config name to a runtime instance.

    Raises ValueError on unknown names so the gateway boot fails loudly
    rather than silently fall back to local (which would mask config typos).
    """
    if name not in _RUNTIMES:
        available = ", ".join(sorted(_RUNTIMES.keys()))
        raise ValueError(
            f"unknown worker_runtime={name!r}. Available: {available}"
        )
    return _RUNTIMES[name](cfg or {})

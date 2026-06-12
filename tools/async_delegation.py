#!/usr/bin/env python3
"""
Async Delegation -- Background Subagent Architecture

Daemon-executor registry for dispatching subagents that run in the background
and return a handle immediately — the parent turn is NOT blocked.

When a subagent finishes, its result is pushed as an ``async_delegation`` event
onto the shared ``process_registry.completion_queue`` so that the existing
idle-drain rail in ``gateway/run.py`` and ``cli.py`` picks it up without any
mid-loop splice.

Capacity
--------
Async delegation is capped at ``delegation.max_async_children`` (default 3).
Dispatches that would exceed the cap are rejected with a fall-back-to-sync hint.
v1 is single-task only; ``background=True`` + multi-item ``tasks`` is rejected.

Event shape
-----------
``{"type": "async_delegation", "delegation_id": str, "session_key": str,
  "goal": str, "context": str, "status": str, "result": Any,
  "dispatch_time": float, "completion_time": float}``

The ``session_key`` field is used by the gateway watcher to route the result
back into the originating session.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Config helpers
# ----------------------------------------------------------------------

def _get_max_async_children() -> int:
    """Read delegation.max_async_children from the config."""
    try:
        from hermes_cli.config import CLI_CONFIG
        delegation = CLI_CONFIG.get("delegation", {})
        return int(delegation.get("max_async_children", 3))
    except Exception:
        return 3  # safe default


# ----------------------------------------------------------------------
# Daemon executor registry
# ----------------------------------------------------------------------

# In-memory registry of running async delegations.
# Key = delegation_id, Value = {"thread": threading.Thread, "stop_event": threading.Event, ...}
_running: Dict[str, Dict[str, Any]] = {}
_running_lock = threading.Lock()


def dispatch(
    runner_fn: Callable[..., Any],
    task_info: Dict[str, Any],
    completion_queue,  # queue.Queue — shared with process_registry
    session_key: str,
    parent_agent=None,
) -> Dict[str, Any]:
    """
    Dispatch a subagent to run in the background.

    Returns immediately with ``{"status": "dispatched", "delegation_id": str}``.
    When the subagent finishes, an ``async_delegation`` event is pushed onto
    ``completion_queue``.

    Parameters
    ----------
    runner_fn
        Callable that takes no arguments and returns the subagent result dict.
        Typically a lambda that captures the pre-built child agent.
    task_info
        Dict with ``goal``, ``context``, ``toolsets``, ``role``, ``model``,
        ``provider`` — stored in the completion event so the re-injected
        message carries full provenance.
    completion_queue
        The shared ``process_registry.completion_queue`` instance.
    session_key
        Opaque routing key for the gateway watcher to know which session
        to inject the result into. Typically ``f"{platform}:{chat_id}"``.
    parent_agent
        The parent AIAgent instance (for heartbeat / stale detection).

    Returns
    -------
    ``{"status": "dispatched", "delegation_id": str, "mode": "background"}``
    on success; ``{"error": str, "status": "rejected"}`` when at capacity.
    """
    max_children = _get_max_async_children()

    with _running_lock:
        active = len(_running)
        if active >= max_children:
            return {
                "error": (
                    f"Async delegation at capacity ({active}/{max_children}). "
                    f"Wait for a running delegation to complete, or set "
                    f"background=false to run synchronously."
                ),
                "status": "rejected",
            }

        delegation_id = f"deleg_{uuid.uuid4().hex[:8]}"
        stop_event = threading.Event()
        task_info_copy = dict(task_info)  # shallow copy
        dispatch_time = time.time()

    def _runner() -> None:
        """Worker thread: runs the subagent and pushes result to completion_queue."""
        logger.info("Async delegation %s started", delegation_id)

        # Heartbeat: periodically touch the parent so the gateway doesn't
        # think the parent agent is idle and kill it.
        _heartbeat_stop = threading.Event()
        _heartbeat_thread = threading.Thread(
            target=_async_heartbeat_loop,
            args=(parent_agent, delegation_id, _heartbeat_stop),
            daemon=True,
        )
        _heartbeat_thread.start()

        try:
            result = runner_fn()
        except Exception as exc:
            logger.exception("Async delegation %s raised: %s", delegation_id, exc)
            result = {"error": str(exc), "status": "error"}
        finally:
            _heartbeat_stop.set()
            _heartbeat_thread.join(timeout=2.0)

        completion_time = time.time()
        evt = {
            "type": "async_delegation",
            "delegation_id": delegation_id,
            "session_key": session_key,
            "status": result.get("status", "completed") if isinstance(result, dict) else "completed",
            "goal": task_info_copy.get("goal", ""),
            "context": task_info_copy.get("context", ""),
            "toolsets": task_info_copy.get("toolsets"),
            "role": task_info_copy.get("role"),
            "model": task_info_copy.get("model"),
            "provider": task_info_copy.get("provider"),
            "result": result,
            "dispatch_time": dispatch_time,
            "completion_time": completion_time,
            "duration_seconds": round(completion_time - dispatch_time, 2),
        }

        try:
            completion_queue.put(evt)
            logger.info(
                "Async delegation %s completed in %.1fs, result queued",
                delegation_id,
                evt["duration_seconds"],
            )
        except Exception:
            logger.exception("Failed to push async delegation %s result to queue", delegation_id)

        with _running_lock:
            _running.pop(delegation_id, None)

    thread = threading.Thread(target=_runner, daemon=True)
    with _running_lock:
        _running[delegation_id] = {
            "thread": thread,
            "stop_event": stop_event,
            "dispatch_time": dispatch_time,
            "goal": task_info.get("goal", "")[:40],
        }
    thread.start()

    return {"status": "dispatched", "delegation_id": delegation_id, "mode": "background"}


def _async_heartbeat_loop(
    parent_agent, delegation_id: str, stop_event: threading.Event
) -> None:
    """Touch the parent agent's activity flag while the async delegation runs."""
    interval = 30.0  # match _HEARTBEAT_INTERVAL in delegate_tool.py
    while not stop_event.wait(interval):
        if parent_agent is None:
            continue
        touch = getattr(parent_agent, "_touch_activity", None)
        if not touch:
            continue
        try:
            touch(f"async_delegation: {delegation_id} running")
        except Exception:
            pass


def interrupt_all() -> int:
    """
    Signal all running async delegations to stop.
    Returns the number of delegations that were signalled.
    """
    with _running_lock:
        count = 0
        for info in _running.values():
            info["stop_event"].set()
            count += 1
    return count


def count_running() -> int:
    """Return the number of currently active async delegations."""
    with _running_lock:
        return len(_running)


def get_running_ids() -> list[str]:
    """Return list of active delegation_ids (for debugging/admin)."""
    with _running_lock:
        return list(_running.keys())
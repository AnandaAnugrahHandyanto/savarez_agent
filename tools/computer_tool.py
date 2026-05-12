"""Computer tool — drive Perplexity Computer-style runs from inside the agent.

Wraps :mod:`computer.runtime` so the model can:

* start a persistent Computer run (foreground or background),
* list / get / inspect events for prior runs,
* cancel a running run,
* schedule a recurring Computer run via the existing cron scheduler.

Implementation notes:

* The actual launch (``start_computer_run``) and cron creation
  (``cron.jobs.create_job``) are referenced via module-level aliases so
  tests can ``monkeypatch.setattr`` them without touching the tool's
  internal logic.  Do not inline-import them or the test contract breaks.
* All handlers return JSON strings via :func:`tools.registry.tool_result` /
  :func:`tools.registry.tool_error`.
* This tool deliberately does *not* try to invent a second agent loop —
  every action delegates to runtime/cron primitives the rest of Hermes
  already uses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from computer.runtime import (
    ComputerStore,
    build_scheduled_computer_prompt,
    start_computer_run as _runtime_start_computer_run,
)
from cron.jobs import create_job as _cron_create_job  # noqa: F401 — re-exported for tests
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)


# Module-level alias so tests can monkeypatch start launching without
# patching the runtime module globally. Keep this name stable.
start_computer_run = _runtime_start_computer_run


# Cached store, lazy-instantiated. Tests monkeypatch ``_get_store`` directly.
_store: Optional[ComputerStore] = None


def _get_store() -> ComputerStore:
    global _store
    if _store is None:
        _store = ComputerStore()
    return _store


_VALID_ACTIONS = frozenset({"start", "list", "get", "events", "cancel", "schedule"})


def computer(
    action: str,
    goal: Optional[str] = None,
    features: Optional[List[str]] = None,
    start_background: bool = False,
    run_id: Optional[str] = None,
    schedule: Optional[str] = None,
    name: Optional[str] = None,
    deliver: Optional[str] = None,
    source: Optional[str] = None,
    task_id: Optional[str] = None,
) -> str:
    """Unified Computer-runtime tool.

    Returns a JSON string matching the conventions of other Hermes tools
    (``success`` / ``error`` plus payload fields).
    """
    del task_id  # accepted for handler-signature parity; unused

    normalized = (action or "").strip().lower()
    if normalized not in _VALID_ACTIONS:
        return tool_error(
            f"Unknown computer action {action!r}. "
            f"Valid actions: {sorted(_VALID_ACTIONS)}",
            success=False,
        )

    store = _get_store()

    try:
        if normalized == "start":
            return _handle_start(
                store,
                goal=goal,
                features=features,
                start_background=start_background,
                source=source,
                deliver=deliver,
            )

        if normalized == "list":
            runs = store.list_runs()
            return tool_result(success=True, count=len(runs), runs=runs)

        if normalized == "get":
            return _handle_get(store, run_id)

        if normalized == "events":
            return _handle_events(store, run_id)

        if normalized == "cancel":
            return _handle_cancel(store, run_id)

        if normalized == "schedule":
            return _handle_schedule(
                store,
                goal=goal,
                schedule=schedule,
                name=name,
                deliver=deliver,
                features=features,
                source=source,
            )

    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("computer tool failed: %s", exc)
        return tool_error(f"computer tool failed: {exc!r}", success=False)

    # Unreachable — every branch returns above.
    return tool_error("computer tool: unreachable branch", success=False)


# ── action handlers ───────────────────────────────────────────────────────────


def _handle_start(
    store: ComputerStore,
    *,
    goal: Optional[str],
    features: Optional[List[str]],
    start_background: bool,
    source: Optional[str],
    deliver: Optional[str],
) -> str:
    if not goal or not str(goal).strip():
        return tool_error("computer(action='start') requires a non-empty goal.", success=False)

    run = store.create_run(
        goal=str(goal).strip(),
        features=features,
        source=source,
        deliver=deliver,
    )

    launched = False
    if start_background:
        try:
            launched = bool(start_computer_run(run["id"], store=store))
        except Exception as exc:
            store.update_run(run["id"], status="failed", error=f"launch failed: {exc!r}")
            return tool_error(
                f"failed to launch background Computer run: {exc!r}",
                success=False,
                run=store.get_run(run["id"]),
            )
        # Reload so the response reflects any status flip the launcher made.
        run = store.get_run(run["id"]) or run

    return tool_result(
        success=True,
        run=run,
        launched=launched,
        message=(
            f"Computer run {run['id']} created"
            + (" and background launch attempted." if start_background else ".")
        ),
    )


def _handle_get(store: ComputerStore, run_id: Optional[str]) -> str:
    if not run_id:
        return tool_error("computer(action='get') requires run_id.", success=False)
    run = store.get_run(run_id)
    if run is None:
        return tool_error(f"unknown computer run: {run_id}", success=False)
    return tool_result(success=True, run=run)


def _handle_events(store: ComputerStore, run_id: Optional[str]) -> str:
    if not run_id:
        return tool_error("computer(action='events') requires run_id.", success=False)
    if store.get_run(run_id) is None:
        return tool_error(f"unknown computer run: {run_id}", success=False)
    events = store.list_events(run_id)
    return tool_result(success=True, run_id=run_id, count=len(events), events=events)


def _handle_cancel(store: ComputerStore, run_id: Optional[str]) -> str:
    if not run_id:
        return tool_error("computer(action='cancel') requires run_id.", success=False)
    run = store.get_run(run_id)
    if run is None:
        return tool_error(f"unknown computer run: {run_id}", success=False)
    if run.get("status") == "cancelled":
        return tool_result(success=True, run=run, message="run already cancelled")

    # We deliberately do NOT shell out to ``kill -9`` here. The background
    # subprocess receives SIGTERM via os.kill only when we have a stored pid
    # AND it still belongs to us. Broad ``pkill`` patterns are forbidden
    # because they can take down unrelated hermes processes.
    pid = (run.get("background") or {}).get("pid")
    kill_error: Optional[str] = None
    if pid:
        try:
            import os
            import signal

            os.kill(int(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, ValueError) as exc:
            kill_error = f"could not signal pid {pid}: {exc!r}"

    updated = store.update_run(
        run_id,
        status="cancelled",
        error=kill_error,
    )
    store.append_event(
        run_id,
        "computer.run.cancelled",
        {"pid": pid, "kill_error": kill_error},
    )
    return tool_result(success=True, run=updated)


def _handle_schedule(
    store: ComputerStore,
    *,
    goal: Optional[str],
    schedule: Optional[str],
    name: Optional[str],
    deliver: Optional[str],
    features: Optional[List[str]],
    source: Optional[str],
) -> str:
    if not goal or not str(goal).strip():
        return tool_error("computer(action='schedule') requires a non-empty goal.", success=False)
    if not schedule or not str(schedule).strip():
        return tool_error("computer(action='schedule') requires a schedule.", success=False)

    feature_list = list(features) if features else ["runtime", "parallel_research", "continuous_monitoring"]
    if "continuous_monitoring" not in feature_list:
        feature_list.append("continuous_monitoring")

    run = store.create_run(
        goal=str(goal).strip(),
        features=feature_list,
        source=source,
        deliver=deliver,
    )

    scheduled_prompt = build_scheduled_computer_prompt(run)

    try:
        job = _cron_create_job(
            prompt=scheduled_prompt,
            schedule=str(schedule).strip(),
            name=name or f"Computer: {run['goal'][:40]}",
            deliver=deliver,
        )
    except Exception as exc:
        store.update_run(run["id"], status="failed", error=f"cron create failed: {exc!r}")
        return tool_error(
            f"failed to create cron job: {exc!r}",
            success=False,
            run=store.get_run(run["id"]),
        )

    job_id = job.get("id") if isinstance(job, dict) else None
    updated = store.update_run(
        run["id"],
        status="scheduled",
        schedule=str(schedule).strip(),
        schedule_job_id=job_id,
    )
    store.append_event(
        run["id"],
        "computer.schedule.created",
        {"cron_job_id": job_id, "schedule": str(schedule).strip()},
    )

    return tool_result(
        success=True,
        run=updated,
        cron_job=job,
        message=(
            f"Scheduled Computer run {run['id']} via cron job {job_id} "
            f"on schedule '{schedule}'."
        ),
    )


# ── Tool schema + registration ────────────────────────────────────────────────


COMPUTER_SCHEMA = {
    "name": "computer",
    "description": (
        "Drive Perplexity Computer-style persistent workflow runs inside Hermes. "
        "Each run has a goal, a plan, an event log, an artifact directory, and a "
        "lifecycle (queued/running/scheduled/completed/failed/cancelled). "
        "Use action='start' to kick off a one-off Computer run (set "
        "start_background=true to launch it in a background hermes process). "
        "Use action='schedule' to register a recurring Computer run via the "
        "cron scheduler — useful for continuous monitoring. "
        "Use action='list' / 'get' / 'events' to inspect prior runs, and "
        "action='cancel' to stop one. "
        "All deliverables should be written into the run's artifact directory "
        "so the user can find them later."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": sorted(_VALID_ACTIONS),
                "description": "One of: start, list, get, events, cancel, schedule.",
            },
            "goal": {
                "type": "string",
                "description": "Natural-language goal for the Computer run (required for start/schedule).",
            },
            "features": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional feature labels to attach to the run, e.g. "
                    "['runtime', 'parallel_research', 'continuous_monitoring']."
                ),
            },
            "start_background": {
                "type": "boolean",
                "description": (
                    "When true, start a background `hermes chat -q ...` process that "
                    "executes the Computer prompt. Defaults to false (the calling "
                    "session executes the run inline)."
                ),
            },
            "run_id": {
                "type": "string",
                "description": "Required for get / events / cancel.",
            },
            "schedule": {
                "type": "string",
                "description": (
                    "Cron-style schedule (e.g. '0 9 * * *') or any string parse_schedule accepts. "
                    "Required for action='schedule'."
                ),
            },
            "name": {
                "type": "string",
                "description": "Optional friendly name for the scheduled cron job.",
            },
            "deliver": {
                "type": "string",
                "description": (
                    "Optional cron delivery target. Pass 'origin' to deliver back to the "
                    "originating chat (recommended), 'local' to save only, or a "
                    "platform:chat_id[:thread_id] string for a specific destination."
                ),
            },
            "source": {
                "type": "string",
                "description": "Optional free-form source label (e.g. 'cli', 'gateway').",
            },
        },
        "required": ["action"],
    },
}


registry.register(
    name="computer",
    toolset="computer",
    schema=COMPUTER_SCHEMA,
    handler=lambda args, **kw: computer(
        action=args.get("action", ""),
        goal=args.get("goal"),
        features=args.get("features"),
        start_background=bool(args.get("start_background", False)),
        run_id=args.get("run_id"),
        schedule=args.get("schedule"),
        name=args.get("name"),
        deliver=args.get("deliver"),
        source=args.get("source"),
        task_id=kw.get("task_id"),
    ),
    emoji="🖥️",
    description=(
        "Persistent Perplexity Computer-style workflow runtime — start, schedule, list, "
        "inspect, and cancel long-running Hermes runs with artifacts and event logs."
    ),
)


__all__ = [
    "computer",
    "start_computer_run",
    "_cron_create_job",
    "_get_store",
    "COMPUTER_SCHEMA",
]

"""Agent Team task tools."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from agent import task_runtime
from tools.registry import registry, tool_error


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _task_id_error(task_id: Any) -> Optional[str]:
    if not task_id or not isinstance(task_id, str):
        return "task_id is required"
    return None


def _agent_team_config() -> dict:
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly()
    except Exception:
        cfg = {}
    team = cfg.get("agent_team") if isinstance(cfg, dict) else None
    return team if isinstance(team, dict) else {}


def _owner_metadata(parent_agent: Any) -> dict:
    if parent_agent is None:
        return {}
    owner = {
        "owner_session_id": getattr(parent_agent, "session_id", None),
        "owner_platform": getattr(parent_agent, "platform", None),
        "owner_user_id": getattr(parent_agent, "user_id", None) or getattr(parent_agent, "authorized_user_id", None),
    }
    return {k: v for k, v in owner.items() if v is not None}


def _task_visible_to_parent(task: dict, parent_agent: Any) -> bool:
    if parent_agent is None:
        return True
    owner_session_id = (task.get("metadata") or {}).get("owner_session_id")
    if not owner_session_id:
        return True
    return owner_session_id == getattr(parent_agent, "session_id", None)


def _get_owned_task(task_id: str, parent_agent: Any) -> Optional[dict]:
    task = task_runtime.get_task(task_id)
    if task is None:
        return None
    if not _task_visible_to_parent(task, parent_agent):
        raise PermissionError(f"Task not found or not owned by this session: {task_id}")
    return task


def _configured_timeout(args: dict, team_cfg: dict) -> Optional[int]:
    if args.get("timeout_seconds") is not None:
        return args.get("timeout_seconds")
    return team_cfg.get("task_timeout_seconds")


def _configured_max_parallel(team_cfg: dict) -> Optional[int]:
    return team_cfg.get("max_parallel_tasks")


def _configured_retention(team_cfg: dict) -> Optional[float]:
    return team_cfg.get("artifact_retention_days")


def agent_task_create(args: dict, parent_agent: Any = None, **_: Any) -> str:
    args = args or {}
    goal = args.get("goal") if isinstance(args, dict) else None
    if not goal or not isinstance(goal, str):
        return tool_error("goal is required")
    team_cfg = _agent_team_config()
    if team_cfg.get("enabled", True) is False:
        return tool_error("Agent Team is disabled by agent_team.enabled=false")
    try:
        meta = task_runtime.start_agent_task(
            goal=goal,
            agent=args.get("agent"),
            context=args.get("context") or "",
            runtime=args.get("runtime"),
            result_schema=args.get("result_schema"),
            toolsets=args.get("toolsets"),
            timeout_seconds=_configured_timeout(args, team_cfg),
            max_parallel_tasks=_configured_max_parallel(team_cfg),
            retention_days=_configured_retention(team_cfg),
            metadata=_owner_metadata(parent_agent),
            parent_agent=parent_agent,
        )
        return _json({"ok": True, "task": meta})
    except Exception as exc:
        return tool_error(str(exc))


def agent_task_status(args: dict, parent_agent: Any = None, **_: Any) -> str:
    task_id = args.get("task_id") if isinstance(args, dict) else None
    err = _task_id_error(task_id)
    if err:
        return tool_error(err)
    try:
        task = _get_owned_task(task_id, parent_agent)
    except Exception as exc:
        return tool_error(str(exc))
    if task is None:
        return tool_error(f"Task not found: {task_id}")
    return _json({"ok": True, "task": task})


def _last_task_event(task: dict) -> Optional[dict]:
    events_path = task.get("events_path")
    if not events_path or not isinstance(events_path, str):
        return None
    last_event = None
    try:
        with open(events_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                last_event = json.loads(line)
    except (OSError, json.JSONDecodeError):
        return None
    return last_event


def _task_elapsed_seconds(task: dict) -> Optional[float]:
    start = task.get("started_at") or task.get("created_at")
    if not isinstance(start, (int, float)):
        return None
    end = task.get("ended_at")
    if not isinstance(end, (int, float)):
        end = time.time()
    return round(max(0.0, end - start), 3)


def agent_task_diagnostics(args: dict, parent_agent: Any = None, **_: Any) -> str:
    task_id = args.get("task_id") if isinstance(args, dict) else None
    err = _task_id_error(task_id)
    if err:
        return tool_error(err)
    try:
        task = _get_owned_task(task_id, parent_agent)
    except Exception as exc:
        return tool_error(str(exc))
    if task is None:
        return tool_error(f"Task not found: {task_id}")
    diagnostics = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "elapsed_seconds": _task_elapsed_seconds(task),
        "last_event": _last_task_event(task),
        "paths": {
            "artifact_dir": task.get("artifact_dir"),
            "events_path": task.get("events_path"),
            "output_path": task.get("output_path"),
            "result_path": task.get("result_path"),
        },
        "runtime": task.get("runtime"),
        "agent": task.get("agent"),
        "error": task.get("error"),
        "owner": task.get("metadata") or {},
        "timestamps": {
            "created_at": task.get("created_at"),
            "started_at": task.get("started_at"),
            "updated_at": task.get("updated_at"),
            "ended_at": task.get("ended_at"),
        },
    }
    return _json({"ok": True, "diagnostics": diagnostics})


def agent_task_output(args: dict, parent_agent: Any = None, **_: Any) -> str:
    task_id = args.get("task_id") if isinstance(args, dict) else None
    err = _task_id_error(task_id)
    if err:
        return tool_error(err)
    try:
        _get_owned_task(task_id, parent_agent)
        if args.get("block"):
            task_runtime.wait_for_task(task_id, timeout_seconds=args.get("timeout_seconds") or 30)
        payload = task_runtime.read_task_output(task_id, max_chars=args.get("max_chars") or 6000)
        return _json({"ok": True, **payload})
    except Exception as exc:
        return tool_error(str(exc))


def agent_task_stop(args: dict, parent_agent: Any = None, **_: Any) -> str:
    task_id = args.get("task_id") if isinstance(args, dict) else None
    err = _task_id_error(task_id)
    if err:
        return tool_error(err)
    try:
        _get_owned_task(task_id, parent_agent)
        task = task_runtime.stop_task(task_id)
        return _json({"ok": True, "task": task})
    except Exception as exc:
        return tool_error(str(exc))


def agent_task_list(args: dict, parent_agent: Any = None, **_: Any) -> str:
    args = args or {}
    try:
        tasks = task_runtime.list_tasks(status=args.get("status"), limit=args.get("limit") or 20)
        tasks = [task for task in tasks if _task_visible_to_parent(task, parent_agent)]
        return _json({"ok": True, "tasks": tasks})
    except Exception as exc:
        return tool_error(str(exc))


_TASK_CREATE_SCHEMA = {
    "name": "agent_task_create",
    "description": "Create a durable background sub-agent task for Agent Team execution.",
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "Sub-agent task goal."},
            "agent": {"type": "string", "description": "Named agent profile, for example researcher/coder/reviewer/evaluator."},
            "context": {"type": "string", "description": "Relevant bounded context for this task."},
            "runtime": {"type": "string", "description": "Requested runtime. codex_app_server currently selects an explicit unsupported-runner failure until safe Codex execution is wired."},
            "result_schema": {"type": "object", "description": "Optional JSON result contract."},
            "toolsets": {"type": "array", "items": {"type": "string"}, "description": "Optional toolsets override."},
            "timeout_seconds": {"type": "integer", "description": "Optional soft timeout. Defaults to agent_team.task_timeout_seconds when configured."},
        },
        "required": ["goal"],
    },
}

registry.register("agent_task_create", "agent_team", _TASK_CREATE_SCHEMA, agent_task_create, emoji="🧩", max_result_size_chars=6000)
registry.register(
    "agent_task_status",
    "agent_team",
    {"name": "agent_task_status", "description": "Get a durable Agent Team task status.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    agent_task_status,
    emoji="🧩",
    max_result_size_chars=6000,
)
registry.register(
    "agent_task_diagnostics",
    "agent_team",
    {
        "name": "agent_task_diagnostics",
        "description": "Get Agent Team task diagnostics: status, elapsed time, last event, artifact paths, runtime, agent, and error.",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]},
    },
    agent_task_diagnostics,
    emoji="🧩",
    max_result_size_chars=8000,
)
registry.register(
    "agent_task_output",
    "agent_team",
    {
        "name": "agent_task_output",
        "description": "Read Agent Team task output/result, optionally waiting briefly.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "block": {"type": "boolean"},
                "timeout_seconds": {"type": "number"},
                "max_chars": {"type": "integer"},
            },
            "required": ["task_id"],
        },
    },
    agent_task_output,
    emoji="🧩",
    max_result_size_chars=12000,
)
registry.register(
    "agent_task_stop",
    "agent_team",
    {"name": "agent_task_stop", "description": "Request cancellation for an active Agent Team task.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    agent_task_stop,
    emoji="🧩",
    max_result_size_chars=6000,
)
registry.register(
    "agent_task_list",
    "agent_team",
    {"name": "agent_task_list", "description": "List recent durable Agent Team tasks visible to this session.", "parameters": {"type": "object", "properties": {"status": {"type": "string"}, "limit": {"type": "integer"}}}},
    agent_task_list,
    emoji="🧩",
    max_result_size_chars=12000,
)

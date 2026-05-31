"""Dynamic workflow orchestration tool for Hermes.

A workflow is intentionally only an orchestration layer: it coordinates
subagents via ``delegate_task`` and persists run state, but it does not read or
write project files or execute shell commands directly. Agents spawned by the
workflow do the actual work under their own tool allowlists.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home
from tools.delegate_tool import delegate_task
from tools.registry import registry, tool_error

_DIRECT_RUNTIME_KEYS = {
    "bash",
    "command",
    "commands",
    "exec",
    "file",
    "files",
    "path",
    "paths",
    "python",
    "script",
    "shell",
    "write_file",
}


def _load_workflow_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
    except Exception:
        cfg = {}
    workflows = cfg.get("workflows") if isinstance(cfg, dict) else None
    delegation = cfg.get("delegation") if isinstance(cfg, dict) else None

    def _config_int(section: Any, key: str, default: int) -> int:
        if not isinstance(section, dict):
            return default
        try:
            return int(section.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "enabled": True if not isinstance(workflows, dict) else workflows.get("enabled", True),
        "max_concurrency": _config_int(workflows, "max_concurrency", 3),
        "max_agents_per_run": _config_int(workflows, "max_agents_per_run", 100),
        "delegation_max_concurrent_children": _config_int(delegation, "max_concurrent_children", 3),
    }


def _runs_dir() -> Path:
    path = Path(get_hermes_home()) / "workflows" / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_path(run_id: str) -> Path:
    return _runs_dir() / f"{run_id}.json"


def _safe_int(value: Any, default: int, *, floor: int = 1, ceiling: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    parsed = max(floor, parsed)
    if ceiling is not None:
        parsed = min(ceiling, parsed)
    return parsed


def _iter_task_batches(tasks: list[dict[str, Any]], size: int):
    for start in range(0, len(tasks), size):
        yield tasks[start : start + size]


def _reject_direct_runtime_actions(obj: Any, path: str = "workflow") -> str | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key) in _DIRECT_RUNTIME_KEYS:
                return f"{path}.{key} declares a direct runtime action; workflows may only orchestrate subagents"
            nested = _reject_direct_runtime_actions(value, f"{path}.{key}")
            if nested:
                return nested
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            nested = _reject_direct_runtime_actions(item, f"{path}[{idx}]")
            if nested:
                return nested
    return None


def _normalize_phases(phases: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(phases, list) or not phases:
        return None, "phases must be a non-empty list"
    normalized: list[dict[str, Any]] = []
    for phase_idx, phase in enumerate(phases):
        if not isinstance(phase, dict):
            return None, f"phase {phase_idx} must be an object"
        name = str(phase.get("name") or f"phase_{phase_idx + 1}").strip()
        raw_tasks = phase.get("tasks")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            return None, f"phase {name!r} must contain a non-empty tasks list"
        tasks: list[dict[str, Any]] = []
        for task_idx, task in enumerate(raw_tasks):
            if not isinstance(task, dict):
                return None, f"phase {name!r} task {task_idx} must be an object"
            goal = task.get("goal")
            if not isinstance(goal, str) or not goal.strip():
                return None, f"phase {name!r} task {task_idx} is missing a goal"
            clean = {
                "goal": goal.strip(),
                "context": task.get("context"),
                "toolsets": task.get("toolsets"),
                "role": task.get("role", "leaf"),
            }
            # Preserve provider/ACP overrides supported by delegate_task without
            # admitting direct runtime actions.
            for optional in ("acp_command", "acp_args"):
                if optional in task:
                    clean[optional] = task[optional]
            tasks.append(clean)
        normalized.append(
            {
                "name": name,
                "context": phase.get("context"),
                "tasks": tasks,
                "carry_previous_results": phase.get("carry_previous_results", True),
            }
        )
    return normalized, None


def _compose_task_context(
    *,
    workflow_context: str,
    phase_context: Any,
    task_context: Any,
    previous_results: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    if workflow_context.strip():
        parts.append("WORKFLOW CONTEXT:\n" + workflow_context.strip())
    if isinstance(phase_context, str) and phase_context.strip():
        parts.append("PHASE CONTEXT:\n" + phase_context.strip())
    if isinstance(task_context, str) and task_context.strip():
        parts.append("TASK CONTEXT:\n" + task_context.strip())
    if previous_results:
        compact = []
        for phase in previous_results:
            phase_name = phase.get("name", "phase")
            summaries = []
            for result in phase.get("results", []):
                if not isinstance(result, dict):
                    continue
                summary = result.get("summary") or result.get("error")
                if summary:
                    summaries.append(str(summary))
            if summaries:
                compact.append(f"## {phase_name}\n" + "\n".join(f"- {s}" for s in summaries))
        if compact:
            parts.append("PREVIOUS PHASE RESULTS:\n" + "\n\n".join(compact))
    return "\n\n".join(parts)


def _parse_delegate_result(raw: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        return [], f"delegate_task returned invalid JSON: {exc}"
    if isinstance(parsed, dict) and parsed.get("error"):
        return [], str(parsed.get("error"))
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        return [], "delegate_task result did not contain a results list"
    return [r if isinstance(r, dict) else {"summary": str(r)} for r in results], None


def workflow_run(
    name: str | None = None,
    phases: list[dict[str, Any]] | None = None,
    context: str | None = None,
    max_concurrency: int | None = None,
    max_agents_per_run: int | None = None,
    parent_agent=None,
) -> str:
    """Run a dynamic workflow by executing phases of delegated subagents."""
    if parent_agent is None:
        return tool_error("workflow_run requires a parent agent context.")

    cfg = _load_workflow_config()
    if not cfg.get("enabled", True):
        return tool_error("Dynamic workflows are disabled by workflows.enabled=false.")

    direct_error = _reject_direct_runtime_actions(phases)
    if direct_error:
        return tool_error(direct_error)

    normalized_phases, phase_error = _normalize_phases(phases)
    if phase_error:
        return tool_error(phase_error)
    assert normalized_phases is not None

    total_tasks = sum(len(phase["tasks"]) for phase in normalized_phases)
    max_agents = _safe_int(max_agents_per_run, cfg["max_agents_per_run"], floor=1)
    if total_tasks > max_agents:
        return tool_error(
            f"workflow has {total_tasks} tasks, exceeding max_agents_per_run={max_agents}"
        )

    requested_concurrency = _safe_int(
        max_concurrency,
        cfg["max_concurrency"],
        floor=1,
        ceiling=16,
    )
    delegation_cap = _safe_int(cfg.get("delegation_max_concurrent_children"), 3, floor=1)
    effective_concurrency = max(1, min(requested_concurrency, delegation_cap))

    run_id = f"wf-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    workflow_name = (name or "workflow").strip() or "workflow"
    started_at = time.time()
    run: dict[str, Any] = {
        "run_id": run_id,
        "name": workflow_name,
        "status": "running",
        "started_at": started_at,
        "updated_at": started_at,
        "max_concurrency": effective_concurrency,
        "requested_max_concurrency": requested_concurrency,
        "total_tasks": total_tasks,
        "phases": [],
    }
    _run_path(run_id).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    workflow_context = context if isinstance(context, str) else ""
    previous_phase_records: list[dict[str, Any]] = []
    try:
        for phase in normalized_phases:
            phase_started = time.time()
            phase_results: list[dict[str, Any]] = []
            phase_errors: list[str] = []
            for batch in _iter_task_batches(phase["tasks"], effective_concurrency):
                delegated_tasks = []
                for task in batch:
                    task_copy = dict(task)
                    task_copy["context"] = _compose_task_context(
                        workflow_context=workflow_context,
                        phase_context=phase.get("context"),
                        task_context=task.get("context"),
                        previous_results=(
                            previous_phase_records
                            if phase.get("carry_previous_results", True)
                            else []
                        ),
                    )
                    delegated_tasks.append(task_copy)
                raw = delegate_task(tasks=delegated_tasks, parent_agent=parent_agent)
                batch_results, batch_error = _parse_delegate_result(raw)
                if batch_error:
                    phase_errors.append(batch_error)
                phase_results.extend(batch_results)

            phase_record = {
                "name": phase["name"],
                "status": "error" if phase_errors else "success",
                "started_at": phase_started,
                "completed_at": time.time(),
                "task_count": len(phase["tasks"]),
                "results": phase_results,
                "errors": phase_errors,
            }
            previous_phase_records.append(phase_record)
            run["phases"].append(phase_record)
            run["updated_at"] = time.time()
            _run_path(run_id).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

            if phase_errors:
                run["status"] = "error"
                break
        else:
            run["status"] = "success"
    except Exception as exc:
        run["status"] = "error"
        run["error"] = f"{type(exc).__name__}: {exc}"

    run["completed_at"] = time.time()
    run["duration_seconds"] = round(run["completed_at"] - started_at, 3)
    run["updated_at"] = run["completed_at"]
    _run_path(run_id).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    final_chunks: list[str] = []
    if run.get("phases"):
        for result in run["phases"][-1].get("results", []):
            if isinstance(result, dict):
                summary = result.get("summary") or result.get("error")
                if summary:
                    final_chunks.append(str(summary))
    response = {
        "success": run.get("status") == "success",
        "run_id": run_id,
        "name": workflow_name,
        "status": run.get("status"),
        "duration_seconds": run.get("duration_seconds"),
        "phases": run.get("phases", []),
        "final_summary": "\n".join(final_chunks),
        "run_file": str(_run_path(run_id)),
    }
    if run.get("error"):
        response["error"] = run["error"]
    elif run.get("status") == "error":
        errors = []
        for phase in run.get("phases", []):
            errors.extend(phase.get("errors", []))
        response["error"] = "; ".join(errors) or "workflow failed"
    return json.dumps(response, ensure_ascii=False)


def list_workflow_runs(limit: int = 10) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(_runs_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            data.setdefault("run_file", str(path))
            runs.append(data)
        if len(runs) >= limit:
            break
    return runs


def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    candidate = _run_path(run_id)
    if not candidate.exists():
        matches = list(_runs_dir().glob(f"*{run_id}*.json"))
        candidate = matches[0] if matches else candidate
    if not candidate.exists():
        return None
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def format_workflow_runs(limit: int = 10) -> str:
    runs = list_workflow_runs(limit=limit)
    if not runs:
        return "No workflow runs yet."
    lines = ["Workflow runs:"]
    for run in runs:
        phase_count = len(run.get("phases", []))
        lines.append(
            f"- {run.get('run_id')} · {run.get('name')} · {run.get('status')} · "
            f"{phase_count} phase(s) · {run.get('total_tasks', '?')} task(s)"
        )
    return "\n".join(lines)


def check_workflow_requirements() -> bool:
    return True


registry.register(
    name="workflow_run",
    toolset="workflow",
    schema={
        "description": (
            "Run a dynamic workflow: a phased, bounded orchestration of many "
            "subagents. The workflow runtime itself cannot run shell commands "
            "or edit files; each task is delegated to subagents with their own "
            "tool allowlists. Use for codebase audits, large migrations, and "
            "cross-checked research."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Human-friendly workflow name."},
                "context": {"type": "string", "description": "Shared context passed to every phase."},
                "max_concurrency": {
                    "type": "integer",
                    "description": "Requested concurrent subagents per phase; capped by config and delegation limits.",
                },
                "max_agents_per_run": {
                    "type": "integer",
                    "description": "Safety cap for total task count in this workflow run.",
                },
                "phases": {
                    "type": "array",
                    "description": "Ordered workflow phases. Tasks within a phase run in parallel batches.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "carry_previous_results": {"type": "boolean"},
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "goal": {"type": "string"},
                                        "context": {"type": "string"},
                                        "toolsets": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "role": {"type": "string", "enum": ["leaf", "orchestrator"]},
                                    },
                                    "required": ["goal"],
                                },
                            },
                        },
                        "required": ["tasks"],
                    },
                },
            },
            "required": ["phases"],
        },
    },
    handler=lambda args, **kw: workflow_run(
        name=args.get("name"),
        phases=args.get("phases"),
        context=args.get("context"),
        max_concurrency=args.get("max_concurrency"),
        max_agents_per_run=args.get("max_agents_per_run"),
        parent_agent=kw.get("parent_agent"),
    ),
    check_fn=check_workflow_requirements,
    description="Dynamic workflow orchestration over subagents",
    emoji="🧩",
    max_result_size_chars=50000,
)

"""agent_bus tool — lets Hermes dispatch tasks to OpenClaw and track completion.

Wraps agent_bus.core functions in a single tool with an `action` dispatcher,
matching the pattern used by other multi-action Hermes tools.
"""

import json
import logging
from typing import Any, Dict

from tools.registry import registry, tool_result, tool_error

logger = logging.getLogger(__name__)

AGENT_BUS_SCHEMA: Dict[str, Any] = {
    "name": "agent_bus",
    "description": (
        "Agent-to-agent task bus. Dispatch tasks to OpenClaw, track completion, "
        "and pull your own inbox. Hermes is always 'hermes'; peer is 'openclaw'. "
        "Every state change broadcasts to Slack #ops-evolution.\n\n"
        "Use this whenever you need OpenClaw to do something (browser work, UI "
        "automation, computer-use) instead of doing it yourself.\n\n"
        "IMPORTANT: When you dispatch via action=assign, the bus automatically "
        "pings the user (@mention in #hermes-inbox) when OpenClaw completes/fails/"
        "times out. You do NOT need to separately message the user about the "
        "outcome — just confirm the dispatch briefly (e.g., 'assigned T-XXX, "
        "watchdog will notify you on completion') and move on. Extra '已完成' "
        "messages duplicate the automatic ping."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "assign", "ack", "progress", "done", "fail",
                    "inbox", "outbox", "show", "recent", "check_timeouts",
                    "wiki_query",
                ],
                "description": (
                    "What to do. `assign` sends a new task to OpenClaw. "
                    "`ack`/`progress`/`done`/`fail` update a task Hermes received "
                    "(only the recipient can change state). `inbox` lists tasks "
                    "assigned to Hermes that are still open. `outbox` lists "
                    "tasks Hermes sent. `show` returns full task + event log. "
                    "`wiki_query` searches `~/wiki/` (Obsidian vault) for past "
                    "learnings, notes, or concepts — use BEFORE assigning a new "
                    "task to check if you've solved the same thing before."
                ),
            },
            # assign
            "goal": {"type": "string", "description": "[assign] One-line description of what to do"},
            "success_criteria": {"type": "string", "description": "[assign] How to verify it's done"},
            "context": {"type": "string", "description": "[assign] Extra context (markdown ok)"},
            "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"], "description": "[assign] default P2"},
            "deadline_minutes": {"type": "integer", "description": "[assign] Deadline in minutes from now"},
            "parent_task_id": {"type": "string", "description": "[assign] Parent task for sub-tasks"},
            "skip_prior_learnings": {
                "type": "boolean",
                "description": "[assign] Skip auto-retrieval of prior wiki learnings into the task context (default false). Only set true for trivial ping/test tasks where history is irrelevant.",
            },
            # state changes
            "task_id": {"type": "string", "description": "[ack/progress/done/fail/show] Task ID like T-A1B2C3"},
            "note": {"type": "string", "description": "[ack/progress] Status note"},
            "result": {"type": "string", "description": "[done] What was accomplished"},
            "reason": {"type": "string", "description": "[fail] Why it failed"},
            "learning": {"type": "string", "description": "[done/fail] One-line insight to persist in wiki"},
            # listing
            "include_terminal": {"type": "boolean", "description": "[outbox] include done/fail tasks"},
            "limit": {"type": "integer", "description": "[recent/wiki_query] default 20/10"},
            # wiki_query
            "query": {"type": "string", "description": "[wiki_query] search term (grep against ~/wiki/*.md)"},
        },
        "required": ["action"],
    },
}

_HERMES = "hermes"


def _handle(args: Dict[str, Any], **_kwargs) -> str:
    from agent_bus import core

    action = args.get("action")
    if not action:
        return tool_error("action is required")

    try:
        if action == "assign":
            goal = args.get("goal")
            if not goal:
                return tool_error("'goal' is required for assign")
            task = core.assign_task(
                from_agent=_HERMES,
                to_agent="openclaw",
                goal=goal,
                success_criteria=args.get("success_criteria"),
                context=args.get("context"),
                priority=args.get("priority") or "P2",
                deadline_minutes=args.get("deadline_minutes"),
                parent_task_id=args.get("parent_task_id"),
                skip_prior_learnings=bool(args.get("skip_prior_learnings")),
            )
            return tool_result({
                "task_id": task["task_id"],
                "slack_thread_ts": task.get("slack_thread_ts"),
                "slack_channel": task.get("slack_channel"),
                "status": task["status"],
                "deadline": task.get("deadline"),
            })

        if action in ("ack", "progress", "done", "fail"):
            task_id = args.get("task_id")
            if not task_id:
                return tool_error(f"'task_id' is required for {action}")
            fn_map = {
                "ack": lambda: core.ack_task(
                    task_id=task_id, agent=_HERMES, note=args.get("note")),
                "progress": lambda: core.progress_task(
                    task_id=task_id, agent=_HERMES, note=args.get("note", "")),
                "done": lambda: core.complete_task(
                    task_id=task_id, agent=_HERMES,
                    result=args.get("result", ""), learning=args.get("learning")),
                "fail": lambda: core.fail_task(
                    task_id=task_id, agent=_HERMES,
                    reason=args.get("reason", ""), learning=args.get("learning")),
            }
            task = fn_map[action]()
            return tool_result({
                "task_id": task["task_id"],
                "status": task["status"],
            })

        if action == "inbox":
            tasks = core.get_outstanding(_HERMES)
            return tool_result({"count": len(tasks), "tasks": tasks})

        if action == "outbox":
            tasks = core.get_sent(
                _HERMES, include_terminal=bool(args.get("include_terminal"))
            )
            return tool_result({"count": len(tasks), "tasks": tasks})

        if action == "show":
            task_id = args.get("task_id")
            if not task_id:
                return tool_error("'task_id' is required for show")
            task = core.get_task(task_id)
            if not task:
                return tool_error(f"Task not found: {task_id}")
            return tool_result(task)

        if action == "recent":
            limit = args.get("limit") or 20
            tasks = core.list_recent(limit=int(limit))
            return tool_result({"count": len(tasks), "tasks": tasks})

        if action == "check_timeouts":
            timed = core.check_timeouts()
            return tool_result({"count": len(timed), "timed_out": timed})

        if action == "wiki_query":
            q = args.get("query")
            if not q:
                return tool_error("'query' is required for wiki_query")
            hits = core.wiki_query(q, limit=int(args.get("limit") or 10))
            return tool_result({"count": len(hits), "hits": hits})

        return tool_error(f"Unknown action: {action}")
    except ValueError as exc:
        return tool_error(str(exc))
    except Exception as exc:
        logger.exception("agent_bus tool failed")
        return tool_error(f"{type(exc).__name__}: {exc}")


def check_requirements() -> bool:
    """Always available — the DB is created on first write."""
    return True


registry.register(
    name="agent_bus",
    toolset="delegation",
    schema=AGENT_BUS_SCHEMA,
    handler=_handle,
    check_fn=check_requirements,
    emoji="🚌",
    description=AGENT_BUS_SCHEMA["description"],
)

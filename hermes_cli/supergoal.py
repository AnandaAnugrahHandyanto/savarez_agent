"""Supergoal orchestration helpers.

A /supergoal is intentionally separate from /goal:

* /goal = keep the current agent loop working on one standing objective.
* /supergoal = create a durable Kanban control-plane task and kick Hermes
  off as the orchestrator for decomposition, worker spawning, review, and
  progress reporting.

This module is UI-agnostic so CLI, gateway, and TUI surfaces can share the
same behavior without duplicating Kanban writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from hermes_cli import kanban_db as kb


@dataclass(frozen=True)
class SupergoalResult:
    task_id: str
    title: str
    kickoff_prompt: str


PROOF_RULES = """Acceptance criteria / operating rules:
- Decompose this supergoal into concrete Kanban child tasks before building.
- Prefer isolated git worktrees for code changes.
- Assign coding work to builder workers/Codex when appropriate.
- Add reviewer/QA tasks before declaring the supergoal complete.
- No worker may mark work done without proof: branch/commit/PR, command output, tests, screenshots/logs, or an explicit blocker.
- If a task is blocked, record what was tried and the exact next decision needed.
- Keep the originating chat updated when meaningful milestones, blockers, or completion happen.
"""


def _source_value(source: Any, name: str) -> Optional[str]:
    value = getattr(source, name, None)
    if value is None:
        return None
    value = str(value)
    return value if value else None


def _body_for_objective(objective: str) -> str:
    return (
        "Supergoal parent task created by /supergoal.\n\n"
        f"Objective:\n{objective.strip()}\n\n"
        f"{PROOF_RULES}\n"
        "Orchestrator notes:\n"
        "- Treat this task as the durable control-plane record for the larger mission.\n"
        "- Create/link smaller tasks as needed, but do not rely on chat memory alone.\n"
        "- Use status/proof in Kanban comments so another agent can resume.\n"
    )


def _kickoff_prompt(task_id: str, objective: str) -> str:
    return f"""orchestrate supergoal {task_id}

Objective: {objective.strip()}

You are Hermes acting as the supergoal orchestrator, not a one-shot builder.
Use the Kanban board as durable state. First inspect task {task_id}, then:
1. Clarify assumptions only if truly blocking; otherwise proceed with sensible defaults.
2. Decompose the supergoal into concrete Kanban tasks with acceptance criteria.
3. Assign/spawn builder workers for implementation work when appropriate.
4. Require proof for every completion: branch/commit/PR, tests, command output, screenshots/logs, or exact blocker.
5. Add review/QA/release tasks before marking the supergoal complete.
6. Report concise progress back to the user when milestones/blockers happen.

Do not mark {task_id} complete until the required child work is done and verified."""


def create_supergoal(
    objective: str,
    *,
    source: Any = None,
    created_by: str = "user",
    tenant: Optional[str] = None,
    board: Optional[str] = None,
) -> SupergoalResult:
    """Create a Kanban parent/control-plane task for a supergoal.

    If ``source`` is a gateway source object with platform/chat/thread fields,
    subscribe that source to terminal Kanban notifications for the task.
    """
    objective = (objective or "").strip()
    if not objective:
        raise ValueError("supergoal text is empty")

    title = f"Supergoal: {objective}"
    with kb.connect(board=board) as conn:
        task_id = kb.create_task(
            conn,
            title=title,
            body=_body_for_objective(objective),
            assignee=None,
            created_by=created_by,
            tenant=tenant,
            priority=100,
            idempotency_key=None,
        )

        platform = _source_value(source, "platform") if source is not None else None
        chat_id = _source_value(source, "chat_id") if source is not None else None
        if platform and chat_id:
            kb.add_notify_sub(
                conn,
                task_id=task_id,
                platform=platform,
                chat_id=chat_id,
                thread_id=_source_value(source, "thread_id"),
                user_id=_source_value(source, "user_id"),
            )

    return SupergoalResult(
        task_id=task_id,
        title=title,
        kickoff_prompt=_kickoff_prompt(task_id, objective),
    )


def format_created(result: SupergoalResult) -> str:
    return (
        f"🚀 Supergoal created: {result.task_id}\n"
        f"{result.title}\n\n"
        "I queued the orchestrator kickoff. Hermes will decompose it into Kanban tasks, "
        "spawn builders where useful, and require proof before completion."
    )


def status_line(limit: int = 10, *, board: Optional[str] = None) -> str:
    """Return a compact status summary of recent non-archived supergoals."""
    with kb.connect(board=board) as conn:
        tasks = [
            t for t in kb.list_tasks(conn, include_archived=False, limit=100)
            if t.title.startswith("Supergoal:")
        ][:limit]
    if not tasks:
        return "No supergoals found. Set one with /supergoal <big objective>."
    lines = ["Active supergoals:"]
    for task in tasks:
        lines.append(f"- {task.id} [{task.status}] {task.title}")
    return "\n".join(lines)

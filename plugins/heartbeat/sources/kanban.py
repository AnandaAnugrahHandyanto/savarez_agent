"""Read-only Kanban Heartbeat source."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from ..models import SourceObservation


def collect_kanban(config: Dict[str, Any]) -> SourceObservation:
    now = datetime.now(timezone.utc).isoformat()
    max_tasks = int(config.get("max_tasks", 30))
    try:
        from hermes_cli.kanban_db import board_stats, connect, list_tasks, task_age

        with connect() as conn:
            stats = board_stats(conn)
            tasks = list_tasks(conn, limit=max_tasks + 1, order_by="priority")
        truncated = len(tasks) > max_tasks
        items = []
        for task in tasks[:max_tasks]:
            items.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "assignee": task.assignee,
                    "age": task_age(task),
                }
            )
        return SourceObservation(
            source="kanban",
            collected_at=now,
            summary=f"{len(items)} active task(s); stats={stats}",
            items=items,
            truncated=truncated,
        )
    except Exception as exc:
        return SourceObservation(
            source="kanban",
            collected_at=now,
            summary="Kanban source unavailable.",
            error=str(exc),
        )

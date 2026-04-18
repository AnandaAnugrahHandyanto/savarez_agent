"""Agent-to-agent task bus.

Shared SQLite-backed task queue for Hermes <-> OpenClaw coordination.
Both agents can assign tasks to each other, track status, and record
learnings that sync back to the wiki memory graph.
"""

from agent_bus.core import (
    assign_task,
    ack_task,
    progress_task,
    complete_task,
    fail_task,
    get_task,
    get_outstanding,
    get_sent,
    list_recent,
    check_timeouts,
    ensure_side_effects,
    nudge_stale_pending,
    process_outbox,
    ensure_user_notifications,
    wiki_query,
)

__all__ = [
    "assign_task",
    "ack_task",
    "progress_task",
    "complete_task",
    "fail_task",
    "get_task",
    "get_outstanding",
    "get_sent",
    "list_recent",
    "check_timeouts",
]

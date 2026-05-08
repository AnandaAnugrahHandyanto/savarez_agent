"""Kanban agent check-in — ask a running agent to self-report status.

This is the *agent-intelligence* complement to :func:`~hermes_cli.kanban_db.heartbeat_worker`,
which records bare liveness pings.  A liveness heartbeat answers "is the
process alive?".  A check-in answers "is the agent making progress, or is it
stuck and needs help?".

The check-in prompt mirrors the protocol used by `Minions
<https://github.com/Agent-3-7/hermes-agent-mission-control>`_ (Agent37, 2026):
inject a structured ``[AUTOMATED CHECK-IN]`` turn into the agent's active
session; parse its ``<status_report>`` response to determine whether the task
is progressing, blocked on human input, or ready for review.

Usage::

    hermes kanban checkin <task-id>
    hermes kanban checkin --all         # check all stale in-progress tasks
    hermes kanban checkin --stale 30    # check tasks idle for 30+ minutes
    hermes kanban checkin --dry-run     # print prompt without sending

Environment::

    HERMES_CHECKIN_MODEL          Override the model used for check-ins
                                  (default: configured auxiliary fast model,
                                   falls back to main model).
    HERMES_CHECKIN_STALE_MINUTES  Tasks idle this long are eligible for
                                  automatic check-in (default: 30).
    HERMES_CHECKIN_TIMEOUT        Seconds to wait for an agent response
                                  (default: 120).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from hermes_cli import kanban_db as kb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STALE_MINUTES: int = int(os.environ.get("HERMES_CHECKIN_STALE_MINUTES", "30"))
DEFAULT_TIMEOUT_S: int = int(os.environ.get("HERMES_CHECKIN_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Check-in prompt  (mirrors the Minions heartbeat prompt format)
# ---------------------------------------------------------------------------

_CHECKIN_SYSTEM = """\
You are completing an automated check-in for an ongoing Hermes Kanban task.
Your PRIMARY job is to ADVANCE the task — not merely report on it.
"""

def build_checkin_prompt(recent_checkins: list[dict]) -> str:
    """Build the check-in prompt injected into the agent's session.

    ``recent_checkins`` is a list of previous check-in records (newest last),
    each a dict with keys ``created_at`` (ISO timestamp) and ``summary``.
    """
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    if not recent_checkins:
        history = "No previous check-ins recorded."
    else:
        lines = []
        for entry in recent_checkins[-3:]:          # last 3 check-ins
            ts = entry.get("created_at", "?")
            summary = entry.get("summary", "")
            lines.append(f"- [{ts}] {summary}")
        history = "\n".join(lines)

    return f"""\
[AUTOMATED CHECK-IN]

<checkin>
<context>
Current time: {now}
</context>

<previous_checkins>
{history}
</previous_checkins>

<instructions>
Your primary job during this check-in is to ADVANCE your task — not just report.

- If you were waiting for the user to answer a question and they have not \
responded: assume a reasonable answer and proceed.  Do not wait any longer.
- If your current approach is stuck: try a different one right now before \
reporting blocked.
- If you have tools available: use them to make concrete progress this turn.
- Only report "blocked" if you have genuinely exhausted alternatives and \
cannot proceed without specific human input.
- Report "completed" only when the task is fully done and ready for human review.
</instructions>

<output_format>
After taking any actions, report your status inside a <status_report> tag.

Fields:
- status (required): one of "progressing", "completed", or "blocked"
  - "progressing" — you made progress; continue on the next check-in
  - "completed"   — work is fully done; ready for human review
  - "blocked"     — exhausted alternatives; need specific human input
- summary (required): what you did this turn and your current state (1-3 sentences)
- user_message (optional): only include when the user needs to see something —
  you need their input, finished the task, hit a milestone, or something
  unexpected happened.  Omit entirely for routine progress.

Example:

<status_report>
{{"status": "progressing", "summary": "Wrote the data-fetcher module, tests passing. \
Next: integrate with the main pipeline."}}
</status_report>
</output_format>
</checkin>"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

@dataclass
class CheckinResult:
    """Parsed result of a single agent check-in."""

    task_id: str
    status: str                    # "progressing" | "completed" | "blocked"
    summary: str
    user_message: Optional[str] = None
    raw_response: str = ""
    parse_ok: bool = True
    error: str = ""
    checkin_at: int = field(default_factory=lambda: int(time.time()))


_STATUS_REPORT_RE = re.compile(
    r"<status_report>\s*(.*?)\s*</status_report>", re.DOTALL
)
_VALID_STATUSES = frozenset({"progressing", "completed", "blocked"})


def parse_checkin_response(task_id: str, response: str) -> CheckinResult:
    """Extract and validate the ``<status_report>`` from an agent response."""
    match = _STATUS_REPORT_RE.search(response)
    if not match:
        return CheckinResult(
            task_id=task_id,
            status="unknown",
            summary="",
            raw_response=response[:500],
            parse_ok=False,
            error="No <status_report> tag found in response.",
        )

    try:
        # Strip markdown code fences if the model wrapped the JSON
        raw_json = match.group(1).strip()
        raw_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json, flags=re.DOTALL)
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return CheckinResult(
            task_id=task_id,
            status="unknown",
            summary="",
            raw_response=response[:500],
            parse_ok=False,
            error=f"JSON parse error: {exc}",
        )

    status = data.get("status", "")
    if status not in _VALID_STATUSES:
        return CheckinResult(
            task_id=task_id,
            status="unknown",
            summary=data.get("summary", ""),
            raw_response=response[:500],
            parse_ok=False,
            error=f"Invalid status value: {status!r}",
        )

    return CheckinResult(
        task_id=task_id,
        status=status,
        summary=data.get("summary", ""),
        user_message=data.get("user_message") or None,
        raw_response=response[:500],
        parse_ok=True,
    )


# ---------------------------------------------------------------------------
# Stale task detection
# ---------------------------------------------------------------------------

def find_stale_tasks(
    conn,
    stale_minutes: int = DEFAULT_STALE_MINUTES,
) -> list[dict]:
    """Return in-progress tasks that have been idle longer than *stale_minutes*.

    "Idle" is defined as no ``last_heartbeat_at`` update in the window.
    Falls back to ``updated_at`` when heartbeat data is absent.
    """
    cutoff = int(time.time()) - stale_minutes * 60
    rows = conn.execute(
        """
        SELECT id, title, assignee, status,
               COALESCE(last_heartbeat_at, updated_at) AS last_active
          FROM tasks
         WHERE status = 'running'
           AND COALESCE(last_heartbeat_at, updated_at) < ?
         ORDER BY last_active ASC
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Check-in log helpers
# ---------------------------------------------------------------------------

def record_checkin(
    conn,
    task_id: str,
    result: CheckinResult,
) -> None:
    """Append a ``checkin`` event to the task's event log."""
    payload: dict = {
        "status": result.status,
        "summary": result.summary,
        "parse_ok": result.parse_ok,
    }
    if result.user_message:
        payload["user_message"] = result.user_message
    if not result.parse_ok:
        payload["error"] = result.error

    # Re-use the existing _append_event helper via kanban_db internals
    # (avoids duplicating the write-transaction pattern)
    kb._append_event(conn, task_id, "checkin", payload)          # type: ignore[attr-defined]
    conn.execute(
        "UPDATE tasks SET last_heartbeat_at = ? WHERE id = ?",
        (result.checkin_at, task_id),
    )

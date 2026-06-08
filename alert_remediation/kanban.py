from __future__ import annotations

from dataclasses import dataclass

from alert_remediation.models import AlertEvent, RouteDecision


MAX_TITLE_LENGTH = 120


@dataclass(frozen=True)
class KanbanCardDraft:
    title: str
    body: str
    assignee: str
    idempotency_key: str
    initial_status: str


@dataclass(frozen=True)
class KanbanCreateResult:
    task_id: str
    created: bool
    status: str


def create_kanban_card(
    draft: KanbanCardDraft,
    *,
    board: str | None = None,
    created_by: str = "alert-remediation",
    workspace_kind: str = "scratch",
    priority: int = 0,
) -> KanbanCreateResult:
    """Create or reuse a Kanban card for an alert draft.

    This is the first side-effecting adapter in the remediation pipeline. It
    intentionally delegates idempotency and status semantics to Hermes' existing
    Kanban DB layer instead of reimplementing board behavior here.
    """

    from hermes_cli import kanban_db as kb

    with kb.connect(board=board) as conn:
        existing = _find_existing_task(conn, draft.idempotency_key)
        if existing is not None:
            return KanbanCreateResult(
                task_id=existing["id"],
                created=False,
                status=existing["status"],
            )

        task_id = kb.create_task(
            conn,
            title=draft.title,
            body=draft.body,
            assignee=draft.assignee,
            created_by=created_by,
            workspace_kind=workspace_kind,
            priority=priority,
            idempotency_key=draft.idempotency_key,
            initial_status=draft.initial_status,
            board=board,
        )
        task = kb.get_task(conn, task_id)
        status = task.status if task is not None else draft.initial_status
        return KanbanCreateResult(task_id=task_id, created=True, status=status)


def format_kanban_card(
    event: AlertEvent,
    decision: RouteDecision,
    *,
    outcome: str | None = None,
) -> KanbanCardDraft:
    """Format an alert escalation as a Kanban card draft without side effects."""

    title = _truncate_title(
        f"[{decision.severity}] {event.service} on {event.host or 'unknown-host'}: {event.symptom}"
    )
    initial_status = _initial_status(decision)
    body = _format_body(event, decision, outcome=outcome)
    return KanbanCardDraft(
        title=title,
        body=body,
        assignee=decision.assignee or "sysadmin",
        idempotency_key=f"alert:{event.dedupe_key}",
        initial_status=initial_status,
    )


def _find_existing_task(conn, idempotency_key: str):
    return conn.execute(
        "SELECT id, status FROM tasks WHERE idempotency_key = ? "
        "AND status != 'archived' "
        "ORDER BY created_at DESC LIMIT 1",
        (idempotency_key,),
    ).fetchone()


def _initial_status(decision: RouteDecision) -> str:
    if decision.action == "approval_required":
        return "blocked"
    return decision.initial_status or "running"


def _format_body(event: AlertEvent, decision: RouteDecision, *, outcome: str | None) -> str:
    sections = [
        "## Detected alert",
        f"Source: {event.source}",
        f"Dedupe key: {event.dedupe_key}",
        f"Host: {event.host or 'unknown'}",
        f"Service: {event.service}",
        f"Severity: {event.severity}",
        f"Symptom: {event.symptom}",
    ]

    if event.first_seen or event.last_seen or event.count is not None:
        sections.extend(
            [
                "",
                "## Observation window",
                f"First seen: {event.first_seen or 'unknown'}",
                f"Last seen: {event.last_seen or 'unknown'}",
                f"Count: {event.count if event.count is not None else 'unknown'}",
            ]
        )

    sections.extend(
        [
            "",
            "## Router decision",
            f"Action decision: {decision.action}",
            f"Matched rule: {decision.matched_rule or 'none'}",
            f"Decision reason: {decision.reason}",
            f"Notify target: {decision.notify_target or 'none'}",
            f"Runbooks: {_join_or_none(decision.runbooks)}",
            f"Kanban on failure: {str(decision.kanban_on_failure).lower()}",
        ]
    )

    if decision.forbidden_without_approval:
        sections.append(
            f"Forbidden without approval: {_join_or_none(decision.forbidden_without_approval)}"
        )

    if decision.action == "approval_required":
        sections.extend(
            [
                "",
                "## Human approval required",
                "Suggested action requires approval before mutation.",
                "Before approving, collect active workload/job count, impact, rollback path, and expected downtime.",
            ]
        )

    sections.extend(["", "## Evidence", *_format_evidence(event)])
    sections.extend(["", "## Links", *_format_links(event)])
    sections.extend(["", "## Requested outcome", _requested_outcome(decision, outcome)])

    return "\n".join(sections).rstrip() + "\n"


def _format_evidence(event: AlertEvent) -> list[str]:
    if not event.evidence:
        return ["Evidence: none supplied"]
    lines = []
    for item in event.evidence:
        label = str(item.get("label") or item.get("type") or "evidence")
        value = str(item.get("value") or item.get("url") or item)
        lines.append(f"- {label}: {value}")
    return lines


def _format_links(event: AlertEvent) -> list[str]:
    if not event.links:
        return ["Links: none supplied"]
    lines = []
    for item in event.links:
        label = str(item.get("label") or "link")
        url = str(item.get("url") or item)
        lines.append(f"- {label}: {url}")
    return lines


def _requested_outcome(decision: RouteDecision, outcome: str | None) -> str:
    if decision.action == "approval_required":
        return "Obtain human approval or document why the proposed mutation is rejected."
    if outcome == "remediation_failed":
        return "Investigate the failed remediation, restore service or document why approval is required, then update the runbook if needed."
    if decision.action == "triage_readonly":
        return "Complete read-only triage, identify root cause or next safe action, and escalate if mutation is required."
    if decision.action == "auto_remediate":
        return "Verify remediation completed successfully or escalate with captured evidence."
    return "Review the alert, decide the next safe action, and close with verification evidence."


def _join_or_none(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def _truncate_title(title: str) -> str:
    if len(title) <= MAX_TITLE_LENGTH:
        return title
    return title[: MAX_TITLE_LENGTH - 1].rstrip() + "…"

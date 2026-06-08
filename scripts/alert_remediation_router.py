#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from alert_remediation.kanban import create_kanban_card, format_kanban_card
from alert_remediation.models import AlertEvent, AlertValidationError, RouteDecision
from alert_remediation.prompts import build_readonly_triage_prompt
from alert_remediation.router import route_event
from alert_remediation.status import format_operator_status


NOOP_ACTIONS = {"noop"}
KANBAN_ACTIONS = {"approval_required", "kanban_task", "critical_page"}
TRIAGE_ACTIONS = {"triage_readonly"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        event = AlertEvent.from_mapping(_read_stdin_json())
        policy = _read_policy(Path(args.policy))
        decision = route_event(event, policy)
        envelope = _build_envelope(
            event,
            decision,
            dry_run=args.dry_run,
            create_kanban=args.create_kanban,
            board=args.board,
        )
    except (AlertValidationError, ValueError, OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if decision.action in NOOP_ACTIONS and not args.emit_decision_json:
        return 0

    if args.emit_decision_json:
        print(json.dumps(envelope, indent=2, sort_keys=True))
    else:
        print(_format_plain_envelope(envelope))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Route one structured alert JSON object from stdin through an alert "
            "remediation policy for cron/script-first monitoring jobs."
        )
    )
    parser.add_argument("--policy", required=True, help="Path to remediation policy YAML")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the decision and drafts without creating Kanban cards or other side effects.",
    )
    parser.add_argument(
        "--emit-decision-json",
        action="store_true",
        help="Emit a machine-readable decision envelope instead of plain text/silence.",
    )
    parser.add_argument(
        "--create-kanban",
        action="store_true",
        help="Create/reuse a Kanban card for escalation actions. Ignored when --dry-run is set.",
    )
    parser.add_argument("--board", help="Optional Hermes Kanban board name")
    return parser


def _read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("stdin must contain one alert JSON object")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("alert JSON must be an object")
    return data


def _read_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    if not isinstance(policy, dict):
        raise ValueError("policy must be a YAML object")
    if policy.get("schema_version") != "alert-remediation-policy/v1":
        raise ValueError("policy schema_version must be 'alert-remediation-policy/v1'")
    return policy


def _build_envelope(
    event: AlertEvent,
    decision: RouteDecision,
    *,
    dry_run: bool,
    create_kanban: bool,
    board: str | None,
) -> dict[str, Any]:
    should_create_kanban = _should_create_kanban(decision)
    should_spawn_triage = decision.action in TRIAGE_ACTIONS
    envelope: dict[str, Any] = {
        "dry_run": dry_run,
        "event": _event_summary(event),
        "decision": asdict(decision),
        "action": decision.action,
        "matched_rule": decision.matched_rule,
        "should_create_kanban": should_create_kanban,
        "should_spawn_triage": should_spawn_triage,
    }

    if should_spawn_triage:
        prompt = build_readonly_triage_prompt(event, decision)
        envelope["triage_prompt"] = {
            "event_dedupe_key": prompt.event_dedupe_key,
            "action": prompt.action,
            "matched_rule": prompt.matched_rule,
            "assignee": prompt.assignee,
            "text": prompt.text,
        }

    if should_create_kanban:
        draft = format_kanban_card(event, decision)
        kanban: dict[str, Any] = {"draft": asdict(draft), "created": False}
        if create_kanban and not dry_run:
            result = create_kanban_card(draft, board=board)
            kanban.update(asdict(result))
        envelope["kanban"] = kanban

    envelope["operator_status"] = asdict(
        format_operator_status(
            event,
            decision,
            outcome=_operator_outcome(decision, dry_run=dry_run),
            root_cause=None,
            action_taken=_operator_action_taken(decision, dry_run=dry_run, create_kanban=create_kanban),
            verification=_operator_verification(envelope),
            next_step=_operator_next_step(decision, envelope, dry_run=dry_run),
            confidence="high",
        )
    )

    return envelope


def _should_create_kanban(decision: RouteDecision) -> bool:
    return decision.action in KANBAN_ACTIONS


def _event_summary(event: AlertEvent) -> dict[str, Any]:
    return {
        "dedupe_key": event.dedupe_key,
        "severity": event.severity,
        "service": event.service,
        "host": event.host,
        "source": event.source,
        "symptom": event.symptom,
    }


def _format_plain_envelope(envelope: dict[str, Any]) -> str:
    status = envelope.get("operator_status")
    if isinstance(status, dict) and status.get("text"):
        return str(status["text"])
    decision = envelope["decision"]
    lines = [
        f"action: {decision['action']}",
        f"severity: {decision['severity']}",
        f"matched_rule: {decision.get('matched_rule') or ''}",
        f"reason: {decision['reason']}",
        f"should_spawn_triage: {str(envelope['should_spawn_triage']).lower()}",
        f"should_create_kanban: {str(envelope['should_create_kanban']).lower()}",
    ]
    kanban = envelope.get("kanban")
    if isinstance(kanban, dict):
        if kanban.get("task_id"):
            lines.append(f"kanban_task_id: {kanban['task_id']}")
        elif kanban.get("draft"):
            lines.append(f"kanban_draft: {kanban['draft']['idempotency_key']}")
    return "\n".join(lines)


def _operator_outcome(decision: RouteDecision, *, dry_run: bool) -> str:
    if dry_run:
        return "dry-run ready"
    if decision.action == "approval_required":
        return "approval required"
    if decision.action in KANBAN_ACTIONS:
        return "escalated"
    if decision.action in TRIAGE_ACTIONS:
        return "triage queued"
    return "routed"


def _operator_action_taken(decision: RouteDecision, *, dry_run: bool, create_kanban: bool) -> str:
    if dry_run:
        return "No live mutation performed; policy and routing decision verified only."
    if decision.action == "approval_required":
        return "No live mutation performed; human approval is required by policy."
    if decision.action in TRIAGE_ACTIONS:
        return "Prepared read-only triage prompt; no host mutation performed by router wrapper."
    if decision.action in KANBAN_ACTIONS and create_kanban:
        return "Processed Kanban escalation path according to policy."
    return "Routed alert through policy; no remediation step executed by router wrapper."


def _operator_verification(envelope: dict[str, Any]) -> list[str]:
    decision = envelope["decision"]
    checks = [
        f"action={decision['action']}",
        f"matched_rule={envelope.get('matched_rule') or 'default'}",
        f"dry_run={envelope['dry_run']}",
        f"should_spawn_triage={envelope['should_spawn_triage']}",
        f"should_create_kanban={envelope['should_create_kanban']}",
    ]
    kanban = envelope.get("kanban")
    if isinstance(kanban, dict):
        if kanban.get("task_id"):
            checks.append(f"kanban_task_id={kanban['task_id']}")
        elif kanban.get("draft", {}).get("idempotency_key"):
            checks.append(f"kanban_draft={kanban['draft']['idempotency_key']}")
    return checks


def _operator_next_step(decision: RouteDecision, envelope: dict[str, Any], *, dry_run: bool) -> str:
    if dry_run:
        return "Review the routed decision, policy match, and drafts before enabling live side effects."
    if decision.action == "approval_required":
        return "Request human approval with workload, impact, rollback path, and downtime before mutating systems."
    if envelope.get("should_spawn_triage"):
        return "Run the read-only triage prompt and escalate to Kanban if evidence confirms impact or triage fails."
    if envelope.get("should_create_kanban"):
        return "Track the escalation in Kanban and update the operator thread with verified findings."
    return "Continue monitoring and re-alert only if the same dedupe key or severity reappears."


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

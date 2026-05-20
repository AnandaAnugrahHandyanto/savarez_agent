"""Read-only Hermes dogfood adapter prototype for ContextOps/ESE.

This module consumes Hermes-like serialized dictionaries only. It deliberately
imports no Hermes gateway/session/Kanban modules and performs no mutation,
send, wake, memory write, task creation, archive, block, or complete action.
All outputs are ContextOps/ESE v0 DTO dictionaries with opaque refs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from contextops_ese import (
    EvidenceBundle,
    Finding,
    MessageSummary,
    Recommendation,
    RuntimeEvent,
    SafetyDecision,
    TaskHandoffAckObservation,
    assert_ref_safe,
    assert_text_safe,
    safe_ref,
    scan_unsafe,
)

_POLICY = SafetyDecision(
    status="allow_suggestion",
    policy_mode="suggestion_only",
    read_only=True,
    mutation_allowed=False,
    dispatch_allowed=False,
    reason="read-only Hermes dogfood report; operator owns any action",
)

# Strict allowlists. The dogfood adapter only consumes the runtime event and
# task/handoff/action shapes it explicitly understands. Any unknown/unsupported
# event kind, task status, action type, delivery mode, or pair role fails closed
# via ``ValueError`` before any DTO or finding is produced -- the adapter never
# silently downgrades or maps an unrecognised type to a default.
_SUPPORTED_RUNTIME_EVENT_TYPES = frozenset(
    {
        "runtime_event",
        "kanban_created",
        "kanban_completed",
        "kanban_blocked",
        "kanban_archived",
        "task_handoff",
        "origin_ack",
        "wake",
        "session_message",
    }
)
_SUPPORTED_TASK_STATUSES = frozenset({"todo", "ready", "running", "blocked", "done", "archived", "unknown"})
_SUPPORTED_ACTION_TYPES = frozenset(
    {
        "create",
        "claim",
        "spawn",
        "complete",
        "block",
        "archive",
        "deliver",
        "ack",
        "fix",
        "review",
        "none",
    }
)
_SUPPORTED_DELIVERY_MODES = frozenset({"active", "passive", "unknown"})
_SUPPORTED_PAIR_ROLES = frozenset(
    {"fix", "review", "manager", "operator", "origin", "unknown"}
)


def _raw_ref(prefix: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        text = "missing"
    return assert_ref_safe(safe_ref(f"{prefix}:{text}"))


def _short_label(value: Any, default: str = "unknown") -> str:
    text = str(value or default).strip().replace("\n", " ")[:80]
    return assert_text_safe(text or default, "dogfood label")


def _bool(value: Any) -> bool:
    return bool(value) if isinstance(value, (bool, int)) else str(value).lower() in {"1", "true", "yes"}


def _evidence_refs(*refs: str | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ref for ref in refs if ref))


def _supported_runtime_event_type(row: dict[str, Any]) -> str:
    """Resolve and allowlist-check one runtime event type, failing closed."""

    event_type = _short_label(row.get("event_type") or row.get("kind") or "", "")
    if event_type not in _SUPPORTED_RUNTIME_EVENT_TYPES:
        raise ValueError(f"unsupported runtime event type: {event_type!r}")
    return event_type


def _supported_task_status(task: dict[str, Any]) -> None:
    status = task.get("status")
    if status is None:
        return
    status_label = _short_label(status)
    if status_label not in _SUPPORTED_TASK_STATUSES:
        raise ValueError(f"unsupported task status: {status_label!r}")


def _supported_task_action_type(task: dict[str, Any]) -> None:
    for key in ("action_type", "action", "task_action"):
        if task.get(key) is None:
            continue
        action_type = _short_label(task[key])
        if action_type not in _SUPPORTED_ACTION_TYPES:
            raise ValueError(f"unsupported task action type: {action_type!r}")


def _supported_delivery_mode(task: dict[str, Any]) -> str:
    """Resolve and allowlist-check one task delivery mode, failing closed."""

    delivery_mode = _short_label(task.get("delivery_mode") or task.get("deliver_mode") or "unknown")
    if delivery_mode not in _SUPPORTED_DELIVERY_MODES:
        raise ValueError(f"unsupported task delivery_mode: {delivery_mode!r}")
    return delivery_mode


def _supported_pair_role(task: dict[str, Any]) -> str:
    """Resolve and allowlist-check one task/handoff pair role, failing closed."""

    pair_role = _short_label(task.get("pair_role") or task.get("role") or "unknown")
    if pair_role not in _SUPPORTED_PAIR_ROLES:
        raise ValueError(f"unsupported task pair_role: {pair_role!r}")
    return pair_role


def _task_observation(task: dict[str, Any]) -> TaskHandoffAckObservation:
    _supported_task_status(task)
    _supported_task_action_type(task)
    task_ref = _raw_ref("task", task.get("id") or task.get("task_id") or task.get("ref"))
    origin = task.get("origin") or task.get("origin_channel")
    return_to = task.get("return_to") or task.get("return_channel")
    group = task.get("remediation_group") or task.get("duplicate_key") or task.get("pair_key")
    delivery_mode = _supported_delivery_mode(task)
    pair_role = _supported_pair_role(task)
    evidence = [task_ref]
    for item in task.get("evidence", ()) if isinstance(task.get("evidence", ()), (list, tuple)) else ():
        evidence.append(_raw_ref("evidence", item))
    return TaskHandoffAckObservation(
        task_ref=task_ref,
        origin_ref=_raw_ref("origin", origin) if origin else None,
        return_to_ref=_raw_ref("return_to", return_to) if return_to else None,
        delegated=_bool(task.get("delegated") or task.get("has_delegated_work")),
        completed=_bool(task.get("completed") or task.get("done") or task.get("status") == "done"),
        origin_ack_observed=_bool(task.get("origin_ack_observed") or task.get("ack_sent") or task.get("origin_ack_sent")),
        delivery_mode=delivery_mode,
        trigger_agent=_bool(task.get("trigger_agent")),
        operator_expected_active_wake=_bool(task.get("operator_expected_active_wake") or task.get("expected_active_wake")),
        remediation_group_ref=_raw_ref("remediation_group", group) if group else None,
        pair_role=pair_role,
        evidence_refs=_evidence_refs(*evidence),
    )


def export_hermes_dogfood_observations(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Map a Hermes-like serialized snapshot to read-only ContextOps DTOs.

    Input is never mutated. Raw ids/channels/session refs are digested into
    opaque refs; free-text payloads are reduced to caller-supplied summaries or
    safe labels only. Unsafe labels fail closed via ``ValueError``.
    """

    if not isinstance(snapshot, dict):
        raise TypeError("Hermes dogfood snapshot must be a mapping")

    runtime_events: list[dict[str, Any]] = []
    for row in snapshot.get("runtime_events", ()) or ():
        if not isinstance(row, dict):
            continue
        event_type = _supported_runtime_event_type(row)
        event_ref = _raw_ref("runtime_event", row.get("id") or row.get("event_id") or row.get("kind"))
        runtime_events.append(
            RuntimeEvent(
                event_ref=event_ref,
                event_type=event_type,
                source="hermes_dogfood_adapter",
                policy_mode="read_only",
                evidence_refs=(event_ref,),
            ).to_dict()
        )

    messages: list[dict[str, Any]] = []
    for row in snapshot.get("messages", ()) or snapshot.get("session_messages", ()) or ():
        if not isinstance(row, dict):
            continue
        msg_ref = _raw_ref("message", row.get("id") or row.get("message_id"))
        sess_ref = _raw_ref("session", row.get("session_id") or row.get("session") or "unknown")
        summary = row.get("summary") or row.get("safe_summary") or "message summary withheld"
        messages.append(
            MessageSummary(
                message_ref=msg_ref,
                session_ref=sess_ref,
                role=_short_label(row.get("role") or "unknown"),
                summary=_short_label(summary, "message summary withheld"),
                evidence_refs=(msg_ref, sess_ref),
            ).to_dict()
        )

    tasks = [_task_observation(row).to_dict() for row in snapshot.get("tasks", ()) or () if isinstance(row, dict)]
    return {"runtime_events": runtime_events, "messages": messages, "tasks": tasks}


def _finding(kind: str, title: str, evidence_refs: Iterable[str], action: str, confidence: float = 0.86) -> dict[str, Any]:
    refs = tuple(dict.fromkeys(evidence_refs))
    for ref in refs:
        assert_ref_safe(ref, "finding evidence ref")
    finding = Finding(
        finding_ref=_raw_ref("finding", f"{kind}:{':'.join(refs)}"),
        kind=kind,  # type: ignore[arg-type]
        title=assert_text_safe(title, "finding title"),
        confidence=max(0.0, min(1.0, float(confidence))),
        evidence=EvidenceBundle(
            evidence_refs=refs,
            summary=assert_text_safe("opaque refs support this suggestion", "evidence summary"),
        ),
        recommendation=Recommendation(
            routing_category="contextops_backlog",
            suggested_operator_action=assert_text_safe(action, "suggested operator action"),
            policy_mode="suggestion_only",
        ),
        safety_decision=_POLICY,
    ).to_dict()
    _assert_no_output_leaks(finding)
    return finding


def detect_dogfood_findings(observations: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Run adapter-local Hermes dogfood detectors over DTO dicts.

    Detectors are suggestion-only and portable core semantics are not assumed:
    missing ACK, passive-vs-active wake, and duplicate fix/review remediation
    loops are Hermes dogfood adapter findings routed to the ContextOps backlog.
    """

    tasks = observations.get("tasks", []) if isinstance(observations, dict) else []
    findings: list[dict[str, Any]] = []

    for task in tasks:
        if not isinstance(task, dict):
            continue
        refs = tuple(task.get("evidence_refs") or (task.get("task_ref"),))
        if task.get("delegated") and task.get("completed") and task.get("origin_ref") and not task.get("origin_ack_observed"):
            findings.append(
                _finding(
                    "missing_origin_ack",
                    "Missing origin ACK after delegated work",
                    refs,
                    "Route a final GO/BLOCK/NEED_MORE report to the origin manually",
                    0.9,
                )
            )
        if task.get("operator_expected_active_wake") and task.get("delivery_mode") == "passive" and not task.get("trigger_agent"):
            findings.append(
                _finding(
                    "passive_delivery_mistaken_for_active_wake",
                    "Passive delivery was treated as active wake",
                    refs,
                    "Clarify delivery mode or rerun with an explicit active wake boundary",
                    0.82,
                )
            )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        if isinstance(task, dict) and task.get("remediation_group_ref"):
            groups[str(task["remediation_group_ref"])].append(task)
    for group_ref, group_tasks in groups.items():
        roles = {str(t.get("pair_role", "unknown")) for t in group_tasks}
        if len(group_tasks) > 1 and ({"fix", "review"} <= roles or len(roles) > 1):
            refs = [group_ref]
            for t in group_tasks:
                refs.extend(t.get("evidence_refs") or (t.get("task_ref"),))
            findings.append(
                _finding(
                    "duplicate_remediation_loop",
                    "Duplicate remediation fix-review loop detected",
                    refs,
                    "Deduplicate the pair in ContextOps backlog before creating more work",
                    0.78,
                )
            )

    return findings


def run_hermes_dogfood(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Convenience read-only exporter + detector pass for fixtures."""

    observations = export_hermes_dogfood_observations(snapshot)
    findings = detect_dogfood_findings(observations)
    report = {"schema_version": "contextops.hermes_dogfood.v0", "observations": observations, "findings": findings}
    _assert_no_output_leaks(report)
    return report


def _assert_no_output_leaks(value: Any) -> None:
    if isinstance(value, dict):
        for v in value.values():
            _assert_no_output_leaks(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _assert_no_output_leaks(v)
    elif isinstance(value, str):
        if value.startswith("ref:"):
            assert_ref_safe(value)
        else:
            reason = scan_unsafe(value)
            if reason is not None:
                raise ValueError(f"dogfood output rejected by leak gate: {reason}")

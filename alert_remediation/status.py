from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from alert_remediation.models import AlertEvent, RouteDecision


@dataclass(frozen=True)
class OperatorStatusReport:
    """Operator-facing remediation status ready for Telegram or logs."""

    text: str
    destination: str | None
    dedupe_key: str
    outcome: str
    severity: str
    service: str
    host: str | None
    matched_rule: str | None


def format_operator_status(
    event: AlertEvent,
    decision: RouteDecision,
    *,
    outcome: str,
    action_taken: str,
    next_step: str,
    verification: Iterable[str] | None = None,
    root_cause: str | None = None,
    confidence: str | None = None,
) -> OperatorStatusReport:
    """Build a concise operator update for alert remediation outcomes.

    The formatter intentionally does not echo raw event evidence. Alert payloads
    are untrusted data and may contain prompt-injection or unsafe operator
    instructions; callers should summarize verified facts into the explicit
    fields instead.
    """

    safe_outcome = _clean(outcome) or "updated"
    safe_root_cause = _clean(root_cause) if root_cause else "Unknown yet"
    safe_action = _clean(action_taken) or "No action recorded."
    safe_next = _clean(next_step) or "Continue monitoring."
    checks = [_clean(item) for item in (verification or []) if _clean(item)]

    subject = _subject(event, decision, safe_outcome)
    lines = [
        f"**{subject}**",
        f"Root cause: {safe_root_cause}",
        f"Action: {safe_action}",
    ]

    if checks:
        lines.append("Verification:")
        lines.extend(f"- {check}" for check in checks)
    else:
        lines.append("Verification: not run")

    lines.append(f"Next: {safe_next}")

    if confidence:
        lines.append(f"Confidence: {_clean(confidence)}")

    if decision.matched_rule:
        lines.append(f"Matched rule: {_clean(decision.matched_rule)}")
    lines.append(f"Dedupe: `{_clean(event.dedupe_key)}`")

    return OperatorStatusReport(
        text="\n".join(lines),
        destination=decision.notify_target,
        dedupe_key=event.dedupe_key,
        outcome=safe_outcome,
        severity=decision.severity,
        service=event.service,
        host=event.host,
        matched_rule=decision.matched_rule,
    )


def _subject(event: AlertEvent, decision: RouteDecision, outcome: str) -> str:
    severity = _clean(decision.severity or event.severity)
    service = _clean(event.service)
    host = _clean(event.host) if event.host else "unknown-host"
    return f"[{severity}] {service} on {host} — {outcome}"


def _clean(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value).replace("|", "/")
    return " ".join(text.split())

from __future__ import annotations

from typing import Any, Mapping

from alert_remediation.models import AlertEvent, RouteDecision


DEFAULT_NOTIFY_ALIAS = "critical_alerts"


def route_event(event: AlertEvent, policy: Mapping[str, Any]) -> RouteDecision:
    """Return the policy decision for an alert without side effects."""

    rule_name, rule = _first_matching_rule(event, policy.get("rules", {}))
    defaults = _mapping(policy.get("defaults", {}))
    routes = _mapping(policy.get("routes", {}))

    if rule is None:
        base = defaults
        reason = "no policy rule matched; using defaults"
    else:
        base = {**defaults, **rule}
        reason = f"matched rule {rule_name}"

    action = str(base.get("action", defaults.get("action", "triage_readonly")))
    severity = str(base.get("severity", event.severity))
    notify_alias_or_target = base.get("notify", defaults.get("notify", DEFAULT_NOTIFY_ALIAS))
    notify_target = _resolve_route(notify_alias_or_target, routes)
    assignee = _optional_str(base.get("assignee", defaults.get("assignee")))
    runbooks = _runbooks_for_action(action, base)
    forbidden = [str(item) for item in base.get("forbidden_without_approval", [])]
    kanban_on_failure = bool(base.get("kanban_on_failure", False))

    dangerous_reason = _dangerous_suggested_action_reason(event, policy, forbidden)
    if dangerous_reason:
        action = "approval_required"
        kanban_on_failure = True
        runbooks = []
        reason = f"{reason}; {dangerous_reason} requires approval"

    return RouteDecision(
        action=action,
        severity=severity,
        notify_target=notify_target,
        assignee=assignee,
        runbooks=runbooks,
        kanban_on_failure=kanban_on_failure,
        reason=reason,
        matched_rule=rule_name,
        forbidden_without_approval=forbidden,
        initial_status=_optional_str(base.get("initial_status")),
    )


def _first_matching_rule(
    event: AlertEvent, rules: Mapping[str, Any]
) -> tuple[str | None, Mapping[str, Any] | None]:
    for name, raw_rule in rules.items():
        rule = _mapping(raw_rule)
        if _matches(event, _mapping(rule.get("match", {}))):
            return str(name), rule
    return None, None


def _matches(event: AlertEvent, match: Mapping[str, Any]) -> bool:
    for key, expected in match.items():
        if key == "source" and event.source != str(expected):
            return False
        if key == "service" and event.service != str(expected):
            return False
        if key == "host" and event.host != str(expected):
            return False
        if key == "severity" and event.severity != str(expected).lower():
            return False
        if key == "runbook" and event.runbook != str(expected):
            return False
        if key == "symptom_contains":
            if str(expected).lower() not in event.symptom.lower():
                return False
        if key == "tags_any":
            expected_tags = {str(tag) for tag in _as_list(expected)}
            if not expected_tags.intersection(event.tags):
                return False
        if key == "tags_all":
            expected_tags = {str(tag) for tag in _as_list(expected)}
            if not expected_tags.issubset(set(event.tags)):
                return False
    return True


def _runbooks_for_action(action: str, rule: Mapping[str, Any]) -> list[str]:
    if action == "auto_remediate":
        return [str(item) for item in rule.get("allowed_runbooks", [])]
    if action == "triage_readonly":
        return [str(item) for item in rule.get("readonly_runbooks", [])]
    return []


def _dangerous_suggested_action_reason(
    event: AlertEvent, policy: Mapping[str, Any], forbidden: list[str]
) -> str | None:
    suggested = event.suggested_action
    if not suggested:
        return None

    dangerous = _mapping(policy.get("dangerous_actions", {}))
    approval_required = {str(item) for item in dangerous.get("approval_required", [])}
    forbidden_set = set(forbidden)
    suggested_classes = {part.strip() for part in suggested.split(",") if part.strip()}

    overlap = suggested_classes.intersection(approval_required | forbidden_set)
    if not overlap:
        return None
    return ", ".join(sorted(overlap))


def _resolve_route(alias_or_target: Any, routes: Mapping[str, Any]) -> str | None:
    if alias_or_target is None:
        return None
    value = str(alias_or_target)
    return str(routes.get(value, value))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)

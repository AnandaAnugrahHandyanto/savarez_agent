from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

import yaml

from alert_remediation.models import AlertEvent, AlertValidationError, RouteDecision
from alert_remediation.router import route_event


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "route":
        return _route_command(args)

    parser.print_help(sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m alert_remediation.cli",
        description="Dry-run policy routing for structured alert remediation events.",
    )
    subcommands = parser.add_subparsers(dest="command")

    route = subcommands.add_parser(
        "route",
        help="Route one alert event through a remediation policy without side effects.",
    )
    route.add_argument("--policy", required=True, help="Path to remediation policy YAML")
    route.add_argument(
        "--event",
        required=True,
        help="Path to alert event JSON, or '-' to read JSON from stdin",
    )
    route.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    return parser


def _route_command(args: argparse.Namespace) -> int:
    try:
        policy = _read_policy(Path(args.policy))
        event = AlertEvent.from_mapping(_read_event(args.event))
        decision = route_event(event, policy)
    except (AlertValidationError, ValueError, OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(_decision_to_dict(decision), indent=2, sort_keys=True))
    else:
        print(_format_plain_decision(decision))
    return 0


def _read_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    if not isinstance(policy, dict):
        raise ValueError("policy must be a YAML object")
    if policy.get("schema_version") != "alert-remediation-policy/v1":
        raise ValueError("policy schema_version must be 'alert-remediation-policy/v1'")
    return policy


def _read_event(event_arg: str) -> dict[str, Any]:
    if event_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(event_arg).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("event JSON must be an object")
    return data


def _decision_to_dict(decision: RouteDecision) -> dict[str, Any]:
    return asdict(decision)


def _format_plain_decision(decision: RouteDecision) -> str:
    lines = [
        f"action: {decision.action}",
        f"severity: {decision.severity}",
        f"notify_target: {decision.notify_target or ''}",
        f"assignee: {decision.assignee or ''}",
        f"runbooks: {', '.join(decision.runbooks)}",
        f"kanban_on_failure: {str(decision.kanban_on_failure).lower()}",
        f"matched_rule: {decision.matched_rule or ''}",
        f"reason: {decision.reason}",
    ]
    if decision.forbidden_without_approval:
        lines.append(
            f"forbidden_without_approval: {', '.join(decision.forbidden_without_approval)}"
        )
    if decision.initial_status:
        lines.append(f"initial_status: {decision.initial_status}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

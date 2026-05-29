#!/usr/bin/env python3
"""Check two-VPS readiness by composing schema and tailnet validation.

This is a lightweight orchestration wrapper around:
- scripts/validate_memory_schema.py
- scripts/check_tailnet_health.py

It is intended for rollout checkpoints, not for long-running monitoring.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from agent.file_safety import get_node_execution_role

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VALIDATOR = ROOT / "scripts" / "validate_memory_schema.py"
TAILNET_CHECK = ROOT / "scripts" / "check_tailnet_health.py"
DEFAULT_SCHEMA = ROOT / "docs" / "architecture" / "memory-schema.sql"


class ValidationError(RuntimeError):
    pass


def run_step(label: str, cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if stdout:
        print(f"[{label}] {stdout}")
    if stderr:
        print(f"[{label}][stderr] {stderr}", file=sys.stderr)
    return proc.returncode, stdout, stderr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Path to the canonical schema SQL")
    parser.add_argument("--peer", default=os.environ.get("TAILNET_PEER", "hermes-vps-2.tailfdd900.ts.net"), help="Tailnet peer to probe")
    parser.add_argument("--ports", default=os.environ.get("SENSITIVE_PORTS", "3000,8642,9119"), help="Comma-separated sensitive ports")
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema validation")
    parser.add_argument("--skip-tailnet", action="store_true", help="Skip tailnet health validation")
    parser.add_argument(
        "--expect-role",
        choices=("canonical", "executor"),
        help="Require the current node execution role to match before reporting readiness",
    )
    return parser


def validate(args: argparse.Namespace) -> None:
    failures: list[str] = []

    if args.expect_role:
        role = get_node_execution_role()
        if role != args.expect_role:
            raise ValidationError(f"readiness check failed: role mismatch (expected {args.expect_role}, got {role or 'unset'})")

    if not args.skip_schema:
        code, _, _ = run_step(
            "schema",
            [sys.executable, str(SCHEMA_VALIDATOR), "--schema", str(args.schema)],
        )
        if code != 0:
            failures.append("schema")

    if not args.skip_tailnet:
        code, _, _ = run_step(
            "tailnet",
            [sys.executable, str(TAILNET_CHECK), "--peer", args.peer, "--ports", args.ports],
        )
        if code != 0:
            failures.append("tailnet")

    if failures:
        raise ValidationError(f"readiness check failed: {', '.join(failures)}")

    print("readiness healthy")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate(args)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

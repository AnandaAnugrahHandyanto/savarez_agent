#!/usr/bin/env python3
"""Render the unified Hermes governed runtime snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.governed_runtime_snapshot import build_governed_runtime_snapshot
from hermes_constants import get_hermes_home


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the unified Hermes governed runtime snapshot")
    parser.add_argument("--config", type=Path, default=get_hermes_home() / "config.yaml")
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--release-id")
    parser.add_argument("--activation-mode", choices=["shadow", "canary", "progressive", "broad_activation"], default="shadow")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_governed_runtime_snapshot(
        repo_root=args.repo_root,
        config_path=args.config,
        release_id=args.release_id,
        activation_mode=args.activation_mode,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Overall status: {payload['overall_status']}")
        print(f"Operator issues: {payload['summary']['operator_issue_count']}")
        print(f"Release blocks: {payload['summary']['release_block_count']}")
        print(f"Routing gaps: {payload['summary']['routing_policy_gap_count']}")
        print(f"Blocked queue tasks: {payload['summary']['blocked_queue_count']}")
        if payload.get("recommended_actions"):
            print("Recommended actions:")
            for item in payload["recommended_actions"]:
                print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

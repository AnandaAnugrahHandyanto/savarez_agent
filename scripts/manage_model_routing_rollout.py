#!/usr/bin/env python3
"""Inspect and manage Hermes model-routing rollout state."""

from __future__ import annotations

import argparse
import json

from agent.routing_governance import promote_route, read_rollout_state, rollback_route


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Hermes model-routing rollout state")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show current rollout state")

    promote = sub.add_parser("promote", help="Promote a provider/model into qualified rollout state")
    promote.add_argument("--provider", required=True)
    promote.add_argument("--model", required=True)
    promote.add_argument("--reason", required=True)
    promote.add_argument("--mode", choices=["manual", "canary", "disabled"], default=None)
    promote.add_argument("--max-percent", type=int, default=None)

    rollback = sub.add_parser("rollback", help="Rollback the current promoted route")
    rollback.add_argument("--reason", required=True)

    args = parser.parse_args()

    if args.command == "status":
        payload = read_rollout_state()
    elif args.command == "promote":
        rollout = {}
        if args.mode is not None:
            rollout["mode"] = args.mode
        if args.max_percent is not None:
            rollout["max_percent"] = args.max_percent
        payload = promote_route(
            provider=args.provider,
            model=args.model,
            reason=args.reason,
            rollout=rollout or None,
        )
    else:
        payload = rollback_route(reason=args.reason)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

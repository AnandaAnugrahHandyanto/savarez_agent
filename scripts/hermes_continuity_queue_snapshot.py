#!/usr/bin/env python3
"""Render the Hermes-native continuity queue snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.continuity_queue import build_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Hermes-native continuity queue snapshot")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_snapshot()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Ready: {payload['totals']['ready']}")
        print(f"Running: {payload['totals']['running']}")
        print(f"Blocked: {payload['totals']['blocked']}")
        print(f"Handoffs: {payload['totals']['handoffs']}")
        if payload['queue']['blocked']:
            print("Blocked tasks:")
            for item in payload['queue']['blocked']:
                print(f"- {item['task_id']}: {item.get('blocked_reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

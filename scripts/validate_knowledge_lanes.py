#!/usr/bin/env python3
"""Validate Hermes typed knowledge lane storage."""

from __future__ import annotations

import json

from agent.knowledge_lanes import KnowledgeLaneStore


def main() -> int:
    store = KnowledgeLaneStore()
    report = store.validation_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

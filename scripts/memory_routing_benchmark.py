#!/usr/bin/env python3
"""Score durable-memory routing predictions against the USER.md benchmark.

Usage:
    python scripts/memory_routing_benchmark.py predictions.jsonl
    python scripts/memory_routing_benchmark.py predictions.jsonl --fixtures custom.jsonl

Prediction JSONL shape:
    {"id": "fixture-id", "route": "user", "destination": "USER.md"}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.memory_routing_benchmark import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    load_fixtures,
    load_predictions,
    score_predictions,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path, help="JSONL predictions to score")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Fixture JSONL path (default: benchmarks/memory_routing/fixtures.jsonl)",
    )
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    predictions = load_predictions(args.predictions)
    report = score_predictions(fixtures, predictions)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    if report.missing_predictions or report.invalid_routes:
        return 2
    if report.domain_specific_user_false_positives:
        return 1
    return 0 if report.exact_matches == report.total else 1


if __name__ == "__main__":
    raise SystemExit(main())

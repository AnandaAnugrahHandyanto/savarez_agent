#!/usr/bin/env python3
"""Offline smoke test for Hermes/OpenClaw/Codex lane orchestration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_interop.lane_orchestrator import run_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path.home() / ".hermes" / "reports" / "agent_lane_smoke")
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()

    result = run_smoke(args.out, source_path=args.source)
    print(
        json.dumps(
            {
                "ok": result.status == "completed",
                "task_id": result.task_id,
                "lane": result.lane.value,
                "manifest": str(result.manifest_path),
                "report": str(result.report_path),
                "artifacts": [str(path) for path in result.output_artifacts],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

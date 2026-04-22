#!/usr/bin/env python3
"""Run rubric-backed proving-matrix checks and emit scorecards."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = ROOT / "EVALS"
RUBRIC_PATH = EVALS_DIR / "rubric.yaml"
SCORECARD_DIR = EVALS_DIR / "scorecards"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_rubric() -> dict[str, Any]:
    return yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8")) or {}


def _run_task(command: str, *, timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        shlex.split(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-2000:],
        "command": command,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True, help="Rubric skill/tool key to evaluate.")
    parser.add_argument("--dry-run", action="store_true", help="Emit a fake-green scorecard without running commands.")
    parser.add_argument("--timeout", type=int, default=300, help="Per-task timeout in seconds.")
    args = parser.parse_args()

    rubric = _load_rubric()
    skills = rubric.get("skills", {})
    skill = skills.get(args.skill)
    if not skill:
        raise SystemExit(f"Unknown proving-matrix skill: {args.skill}")

    threshold = float(skill.get("threshold", rubric.get("default_threshold", 0.6)))
    task_rows = []
    for task in skill.get("tasks", []):
        if args.dry_run:
            result = {
                "passed": True,
                "returncode": 0,
                "stdout": "dry-run",
                "stderr": "",
                "command": task.get("command", ""),
            }
        else:
            result = _run_task(str(task.get("command") or ""), timeout=max(1, args.timeout))
        task_rows.append(
            {
                "id": task.get("id"),
                "description": task.get("description"),
                **result,
            }
        )

    total = len(task_rows)
    passed = sum(1 for row in task_rows if row["passed"])
    rate = (passed / total) if total else 0.0
    scorecard = {
        "skill": args.skill,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "passed_tasks": passed,
        "total_tasks": total,
        "green_rate": rate,
        "approved": rate >= threshold,
        "tasks": task_rows,
        "dry_run": bool(args.dry_run),
    }

    SCORECARD_DIR.mkdir(parents=True, exist_ok=True)
    output = SCORECARD_DIR / f"{args.skill}_{_utc_stamp()}.json"
    output.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"approved": scorecard["approved"], "scorecard": str(output)}, indent=2))
    return 0 if scorecard["approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

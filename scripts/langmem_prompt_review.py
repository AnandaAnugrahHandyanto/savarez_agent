#!/usr/bin/env python3
"""Reviewed procedural-memory scaffold for Hermes LangMem.

Loads failed trajectories from JSON, prepares a review packet, and makes the
optimizer hook explicit without auto-patching any prompt.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = Path("tmp/langmem-prompt-review")


def _load_trajectories(input_path: str | None) -> list[dict[str, Any]]:
    if not input_path:
        return []
    path = Path(input_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("trajectories")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    raise ValueError(f"Unsupported trajectory payload shape in {path}")


def _failure_summary(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, int] = {}
    for item in trajectories:
        reason = str(item.get("failure_type") or item.get("category") or "uncategorized")
        categories[reason] = categories.get(reason, 0) + 1
    return {
        "total_trajectories": len(trajectories),
        "categories": categories,
    }


def _build_review_packet(trajectories: list[dict[str, Any]], input_path: str | None) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_path": input_path,
        "summary": _failure_summary(trajectories),
        "sample_trajectories": trajectories[:10],
        "optimizer_stub": {
            "status": "scaffold_only",
            "note": "This is where LangMem create_prompt_optimizer would run after human review prep.",
            "auto_apply_enabled": False,
            "todo": [
                "Load approved failure trajectories only",
                "Generate candidate prompt deltas for reviewer inspection",
                "Keep optimizer output separate from the live system prompt",
                "Require explicit human approval before any prompt patch lands",
            ],
        },
        "review_checklist": [
            "Is the failure actually prompt-worthy rather than a tool, retrieval, or environment issue?",
            "Would the proposed prompt delta generalize without overfitting to one conversation?",
            "Does the change avoid storing user-specific temporary task state as policy?",
            "Is a human reviewer explicitly approving or rejecting the change?",
        ],
    }


def write_review_packet(packet: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "latest.json"
    out_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a reviewed LangMem prompt-optimization packet without auto-patching prompts.",
    )
    parser.add_argument(
        "--input",
        help="Path to a JSON file containing failed trajectories or {\"trajectories\": [...]}.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for review packets (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args()

    trajectories = _load_trajectories(args.input)
    packet = _build_review_packet(trajectories, args.input)
    out_path = write_review_packet(packet, Path(args.output_dir))
    print(json.dumps({"result": "review packet written", "path": str(out_path), "count": len(trajectories)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

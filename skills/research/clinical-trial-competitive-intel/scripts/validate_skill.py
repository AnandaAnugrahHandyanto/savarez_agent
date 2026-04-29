#!/usr/bin/env python3
"""Static validator for the clinical-trial-competitive-intel skill.

This script intentionally checks only deterministic structure: frontmatter,
reference files, eval schema, and core instruction phrases. It does not grade
LLM output quality; use skill-creator eval runs for that.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
REQUIRED_REFERENCES = [
    "references/competitor-discovery.md",
    "references/source-workflows.md",
    "references/excel-schema-and-qc.md",
    "references/cde-normal-chrome.md",
]
REQUIRED_PHRASES = [
    "Do not produce a target-asset-only excerpt",
    "A competitive-intelligence workbook is failed if it only contains the user's target asset",
    "normal Google Chrome + Apple Events/JXA workflow",
    "Before final response, run an actual verification script with `openpyxl`",
    "For any CDE query/merge: read `references/cde-normal-chrome.md`",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        fail("SKILL.md missing YAML frontmatter")
    try:
        _, fm, _ = text.split("---", 2)
    except ValueError:
        fail("SKILL.md frontmatter is not delimited by ---")
    out: dict[str, str] = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip().strip('"')
    return out


def main() -> None:
    if not SKILL.exists():
        fail(f"missing {SKILL}")
    text = SKILL.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm.get("name") != "clinical-trial-competitive-intel":
        fail("frontmatter name mismatch")
    desc = fm.get("description", "")
    for token in ["competitive intelligence", "CDE", "Excel", "target asset"]:
        if token not in desc:
            fail(f"description missing trigger token: {token}")
    for ref in REQUIRED_REFERENCES:
        path = ROOT / ref
        if not path.exists():
            fail(f"missing reference file: {ref}")
        if ref not in text:
            fail(f"SKILL.md does not point to reference: {ref}")
    for phrase in REQUIRED_PHRASES:
        if phrase not in text:
            fail(f"missing core instruction phrase: {phrase}")
    eval_path = ROOT / "evals" / "evals.json"
    if not eval_path.exists():
        fail("missing evals/evals.json")
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    if data.get("skill_name") != "clinical-trial-competitive-intel":
        fail("evals.json skill_name mismatch")
    evals = data.get("evals")
    if not isinstance(evals, list) or len(evals) < 3:
        fail("evals.json must contain at least 3 evals")
    ids = set()
    for item in evals:
        if item.get("id") in ids:
            fail(f"duplicate eval id: {item.get('id')}")
        ids.add(item.get("id"))
        for field in ["prompt", "expected_output", "files", "expectations"]:
            if field not in item:
                fail(f"eval {item.get('id')} missing {field}")
        if len(item.get("expectations") or []) < 4:
            fail(f"eval {item.get('id')} has too few expectations")
    print("OK: clinical-trial-competitive-intel skill structure validated")


if __name__ == "__main__":
    main()

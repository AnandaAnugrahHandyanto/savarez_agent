#!/usr/bin/env python3
"""Install the Codex coding discipline block into an AGENTS.md file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


START = "<!-- BEGIN HERMES CODEX CODING DISCIPLINE -->"
END = "<!-- END HERMES CODEX CODING DISCIPLINE -->"


def _skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_block() -> str:
    path = _skill_dir() / "templates" / "AGENTS.md"
    return path.read_text(encoding="utf-8").strip() + "\n"


def apply_block(existing: str, block: str) -> tuple[str, str]:
    pattern = re.compile(
        rf"{re.escape(START)}.*?{re.escape(END)}\n?",
        flags=re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(block, existing), "updated"

    if not existing.strip():
        return block, "created"

    separator = "\n\n" if existing.endswith("\n") else "\n\n"
    return existing.rstrip() + separator + block, "appended"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install Hermes' Codex coding discipline into AGENTS.md."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="AGENTS.md",
        help="AGENTS.md path to update, default: ./AGENTS.md",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_block",
        help="Print the reusable AGENTS.md block instead of writing.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if the target already contains the managed block.",
    )
    args = parser.parse_args(argv)

    block = load_block()
    target = Path(args.target)

    if args.print_block:
        sys.stdout.write(block)
        return 0

    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if args.check:
        return 0 if START in existing and END in existing else 1

    new_text, action = apply_block(existing, block)
    target.write_text(new_text, encoding="utf-8")
    print(f"{action}: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Workspace → Shared Wiki sync (D direction).

OpenClaw's codex sandbox is `workspace-write`, which blocks direct writes to
`~/wiki/memory/`. Artifacts OpenClaw produces for M2 propagation land in
`~/.openclaw/workspace/memory/` and are invisible to Hermes until copied.

This script copies "publishable" files from workspace/memory → ~/wiki/memory/
and is intended to run inside `wiki-memory-sync.sh` (or on-demand).

Spec: ~/wiki/operations/failure-recipes/recipe-openclaw-sandbox-write-limit.md

Publishable criteria (ALL):
  1. Filename matches one of:
       - *_evolution_*.md
       - *_coaching-response_*.md
       - *_agent-bus_T-*.md
  2. Has YAML frontmatter (first line "---")
  3. Not already present in ~/wiki/memory/ with same-or-newer mtime

Safety:
  - Never overwrites a wiki file newer than the workspace source
  - Dry-run by default if no `--apply` flag
  - Logs copied files to stdout in one-line format for sync-bridge log capture
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

WORKSPACE_MEM = Path.home() / ".openclaw" / "workspace" / "memory"
WIKI_MEM = Path.home() / "wiki" / "memory"

PUBLISHABLE_PATTERNS = [
    "*_evolution_*.md",
    "*_coaching-response_*.md",
    "*_agent-bus_T-*.md",
]


def has_frontmatter(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return f.readline().startswith("---")
    except Exception:
        return False


def find_candidates() -> list[Path]:
    if not WORKSPACE_MEM.exists():
        return []
    out: list[Path] = []
    seen = set()
    for pat in PUBLISHABLE_PATTERNS:
        for p in WORKSPACE_MEM.glob(pat):
            if p in seen:
                continue
            if not p.is_file():
                continue
            if not has_frontmatter(p):
                continue
            seen.add(p)
            out.append(p)
    return out


def should_copy(src: Path) -> tuple[bool, str]:
    dst = WIKI_MEM / src.name
    if not dst.exists():
        return (True, "new")
    try:
        if src.stat().st_mtime > dst.stat().st_mtime:
            return (True, "newer in workspace")
    except OSError:
        return (False, "stat failed")
    return (False, "wiki has same-or-newer")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually copy (default is dry-run)")
    ap.add_argument("--quiet", action="store_true", help="Only print copies, suppress skips")
    args = ap.parse_args()

    WIKI_MEM.mkdir(parents=True, exist_ok=True)
    candidates = find_candidates()
    if not candidates:
        if not args.quiet:
            print("[workspace-sync] no candidate files")
        return 0

    copied = 0
    skipped = 0
    for src in candidates:
        do_copy, reason = should_copy(src)
        if not do_copy:
            if not args.quiet:
                print(f"[workspace-sync] SKIP {src.name} ({reason})")
            skipped += 1
            continue
        if args.apply:
            shutil.copy2(src, WIKI_MEM / src.name)
            print(f"[workspace-sync] COPY {src.name} ({reason})")
            copied += 1
        else:
            print(f"[workspace-sync] DRY-RUN would copy {src.name} ({reason})")
            copied += 1

    if not args.quiet or copied:
        print(f"[workspace-sync] summary: copied={copied} skipped={skipped} "
              f"apply={'yes' if args.apply else 'DRY-RUN'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

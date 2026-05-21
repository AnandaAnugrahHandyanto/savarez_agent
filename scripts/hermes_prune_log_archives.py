#!/usr/bin/env python3
"""Prune old Hermes log archives under ~/.hermes/logs/archive."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path


def _iter_archive_entries(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.iterdir(), key=lambda path: path.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", default=os.path.expanduser("~/.hermes/logs/archive"))
    parser.add_argument("--days", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    archive_dir = Path(args.archive_dir).expanduser()
    cutoff = time.time() - (args.days * 24 * 60 * 60)
    entries = _iter_archive_entries(archive_dir)
    old_entries = [entry for entry in entries if entry.stat().st_mtime < cutoff]

    action = "would prune" if args.dry_run else "pruned"
    if not old_entries:
        print(f"hermes-log-retention: PASS no archives older than {args.days:g} days")
        return 0

    for entry in old_entries:
        print(f"{action}: {entry}")
        if not args.dry_run:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    print(
        "hermes-log-retention: PASS "
        f"{'checked' if args.dry_run else 'removed'}={len(old_entries)} "
        f"archive_dir={archive_dir}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as exc:
        print(f"hermes-log-retention: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

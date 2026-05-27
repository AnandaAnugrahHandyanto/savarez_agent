#!/usr/bin/env python3
"""scripts/audit-mentions.py — fleet-wide Discord mention contamination scan.

Recursively scans a directory tree for malformed `<@…>` Discord mention
literals using the same classifier that gates cron / skill / Discord
write paths (`agent.mention_lint`). Use to find scar tissue left in
existing skills, MEMORY.md / SOUL.md files, cron prompts, cached docs,
or anywhere else the gateway-mention bug left a contaminated artifact.

Usage:
    python scripts/audit-mentions.py [PATH] [--ext .md,.py,.json,.txt,.yaml,.yml]
    python scripts/audit-mentions.py ~/AppData/Local/hermes/profiles
    python scripts/audit-mentions.py . --ext .md

Exit codes:
    0 → no findings (clean)
    1 → at least one malformed mention found (CI-friendly)
    2 → invocation / IO error

Output is plain text, one finding per line, suitable for grep / sort.

See agent/mention_lint.py and writer_ai#125.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


# Bootstrap import path so the script is runnable from anywhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.mention_lint import find_malformed_mentions  # noqa: E402


_DEFAULT_EXTS = (".md", ".py", ".json", ".txt", ".yaml", ".yml")
_DEFAULT_SKIP_DIRS = (
    ".git", "node_modules", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".next",
    # Log / session / cache directories are noisy and historically full
    # of the bug we already know about — exclude by default. Pass
    # --include-logs to scan them.
    "logs", "sessions", "cache", "audio_cache", "output", "cron",
)


def iter_files(root: Path, exts: Tuple[str, ...], include_logs: bool) -> Iterable[Path]:
    skip = set(_DEFAULT_SKIP_DIRS)
    if include_logs:
        skip -= {"logs", "sessions", "cache", "audio_cache", "output", "cron"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Skip excluded directories anywhere in the path.
        if any(part in skip for part in path.parts):
            continue
        if exts and path.suffix.lower() not in exts:
            continue
        yield path


def scan_file(path: Path, *, allow_roles: bool) -> List[Tuple[int, str, str]]:
    """Return [(line_no, raw_token, kind), …] for malformed mentions in `path`."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return []
    findings = find_malformed_mentions(text, allow_roles=allow_roles)
    if not findings:
        return []
    # Map character offsets to 1-indexed line numbers.
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)

    def offset_to_line(off: int) -> int:
        # Binary search.
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1
    return [(offset_to_line(f.start), f.raw, f.kind) for f in findings]


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("path", nargs="?", default=".", help="Root path to scan (default: cwd)")
    p.add_argument(
        "--ext", default=",".join(_DEFAULT_EXTS),
        help=f"Comma-separated file extensions to scan (default: {','.join(_DEFAULT_EXTS)})",
    )
    p.add_argument(
        "--allow-roles", action="store_true",
        help="Tolerate `<@&SNOWFLAKE>` role mentions (default: flag them)",
    )
    p.add_argument(
        "--include-logs", action="store_true",
        help="Also scan logs/, sessions/, cache/, output/, cron/ (noisy)",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-finding output; only print summary + exit code",
    )
    args = p.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"audit-mentions: path not found: {root}", file=sys.stderr)
        return 2

    exts = tuple(
        e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}"
        for e in args.ext.split(",") if e.strip()
    )

    total_findings = 0
    files_with_findings = 0
    files_scanned = 0
    for path in iter_files(root, exts, include_logs=args.include_logs):
        files_scanned += 1
        findings = scan_file(path, allow_roles=args.allow_roles)
        if not findings:
            continue
        files_with_findings += 1
        total_findings += len(findings)
        if not args.quiet:
            for line_no, raw, kind in findings:
                # grep-style: PATH:LINE:KIND:TOKEN
                print(f"{path}:{line_no}:{kind}:{raw}")

    print(
        f"\naudit-mentions: scanned {files_scanned} files under {root}; "
        f"{files_with_findings} contaminated, {total_findings} findings total.",
        file=sys.stderr,
    )
    return 1 if total_findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

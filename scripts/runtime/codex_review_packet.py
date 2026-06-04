#!/usr/bin/env python3
"""Build a bounded review packet for Codex read-only review.

The packet is intentionally lossy: Hermes controls what evidence Codex sees so
Codex does not run broad commands or flood stdout with source/diff output.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_git(workdir: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(workdir),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if proc.returncode != 0:
        return f"[git {' '.join(args)} failed: {proc.stderr.strip()}]"
    return proc.stdout


def _untracked_scope_files(workdir: Path, files: list[str]) -> list[str]:
    if not files:
        return []
    output = _run_git(workdir, ["ls-files", "--others", "--exclude-standard", "--", *files])
    if output.startswith("[git "):
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _bounded_untracked_previews(workdir: Path, files: list[str], limit: int) -> tuple[str, bool]:
    previews: list[str] = []
    truncated_any = False
    if not files:
        return "", False
    per_file_limit = max(200, limit // max(1, len(files)))
    root = workdir.resolve()
    for name in files:
        path = (workdir / name).resolve()
        if not path.is_file() or not str(path).startswith(str(root) + "/"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        clipped, truncated = _clip(text, per_file_limit)
        truncated_any = truncated_any or truncated
        previews.append(f"### {name}\n\n```text\n{clipped.rstrip()}\n```")
    return "\n\n".join(previews), truncated_any


def _clip(text: str, limit: int) -> tuple[str, bool]:
    if limit < 0 or len(text) <= limit:
        return text, False
    marker = f"\n[truncated {len(text) - limit} chars]\n"
    return text[: max(0, limit - len(marker))] + marker, True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build bounded Codex review packet from git diff evidence.")
    parser.add_argument("--workdir", default=".")
    parser.add_argument("--file", action="append", dest="files", default=[])
    parser.add_argument("--max-stat-chars", type=int, default=4_000)
    parser.add_argument("--max-name-chars", type=int, default=4_000)
    parser.add_argument("--max-diff-chars", type=int, default=30_000)
    parser.add_argument("--max-total-chars", type=int, default=40_000)
    return parser


def build_packet(
    *,
    workdir: Path,
    files: list[str],
    max_stat_chars: int,
    max_name_chars: int,
    max_diff_chars: int,
    max_total_chars: int,
) -> str:
    if not workdir.is_dir():
        raise SystemExit(f"workdir not found: {workdir}")

    pathspec = ["--", *files] if files else []
    stat, stat_truncated = _clip(_run_git(workdir, ["diff", "--stat", *pathspec]), max_stat_chars)
    names, names_truncated = _clip(_run_git(workdir, ["diff", "--name-only", *pathspec]), max_name_chars)
    diff, diff_truncated = _clip(_run_git(workdir, ["diff", "--unified=20", *pathspec]), max_diff_chars)
    untracked_files = _untracked_scope_files(workdir, files)
    untracked_preview, untracked_truncated = _bounded_untracked_previews(
        workdir,
        untracked_files,
        max(0, max_diff_chars - len(diff)),
    )

    parts = [
        "# Bounded Codex review packet",
        "",
        "Codex must review this packet only. Do not run shell commands. Do not request full source or full diffs.",
        "",
        "## Scope files",
        "",
        "\n".join(f"- `{name}`" for name in files) if files else "- all current git diff paths",
        "",
        "## git diff --stat",
        "",
        stat.rstrip() or "[no stat output]",
        "",
        "## git diff --name-only",
        "",
        names.rstrip() or "[no changed tracked files]",
        "",
        "## bounded git diff",
        "",
        diff.rstrip() or "[no diff output]",
        "",
    ]
    if untracked_preview:
        parts.extend([
            "## bounded untracked file previews",
            "",
            untracked_preview.rstrip(),
            "",
        ])
    parts.extend([
        "## Packet limits",
        "",
        f"- stat_truncated={stat_truncated}",
        f"- names_truncated={names_truncated}",
        f"- diff_truncated={diff_truncated}",
        f"- untracked_truncated={untracked_truncated}",
        f"- max_total_chars={max_total_chars}",
    ])
    packet = "\n".join(parts) + "\n"
    packet, total_truncated = _clip(packet, max_total_chars)
    if total_truncated and "[truncated" not in packet:
        packet += "\n[truncated by max_total_chars]\n"
    return packet


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    packet = build_packet(
        workdir=Path(args.workdir).resolve(),
        files=args.files,
        max_stat_chars=args.max_stat_chars,
        max_name_chars=args.max_name_chars,
        max_diff_chars=args.max_diff_chars,
        max_total_chars=args.max_total_chars,
    )
    sys.stdout.write(packet)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

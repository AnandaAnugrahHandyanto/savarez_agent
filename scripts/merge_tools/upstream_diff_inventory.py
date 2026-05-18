#!/usr/bin/env python3
"""Inventory upstream/custom touched paths and classify them with merge policy."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from upstream_merge_policy import classify_paths, dedupe_paths, filter_noise_paths, load_strategy

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STRATEGY_FILE = REPO_ROOT / "scripts" / "merge_tools" / "hermes-merge-conflict-strategies.json"


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def bucket_for(path: str) -> str:
    prefixes = (
        ("vendor/openclaw-mirror/", "openclaw_vendor"),
        ("brain/", "brain_identity"),
        ("gateway/", "gateway"),
        ("agent/", "agent_core"),
        ("tools/", "tools"),
        ("hermes_cli/", "hermes_cli"),
        ("tests/", "tests"),
        ("docs/", "docs"),
        ("_docs/", "docs"),
        ("scripts/", "scripts_ops"),
        ("optional-skills/", "optional_skills"),
        (".github/", "meta_repo"),
    )
    for prefix, bucket in prefixes:
        if path.startswith(prefix):
            return bucket
    if "/" not in path:
        return "root_files"
    return "other"


def parse_status_paths(status_output: str) -> list[str]:
    paths: list[str] = []
    for raw_line in status_output.splitlines():
        line = raw_line.rstrip()
        if len(line) < 4:
            continue
        payload = line[3:]
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        paths.append(payload)
    return dedupe_paths(paths)


def list_diff_paths(ref_a: str, ref_b: str) -> list[str]:
    output = run_git(["diff-tree", "-r", "--no-commit-id", "--name-only", ref_a, ref_b])
    return dedupe_paths(output.splitlines())


def build_inventory(current_ref: str, upstream_ref: str, strategy_file: Path) -> dict[str, object]:
    strategy = load_strategy(strategy_file)
    merge_base = run_git(["merge-base", current_ref, upstream_ref]).strip()
    upstream_paths = list_diff_paths(merge_base, upstream_ref)
    custom_committed_paths = list_diff_paths(merge_base, current_ref)
    dirty_status = run_git(["status", "--porcelain=v1", "--untracked-files=all"])
    dirty_paths = parse_status_paths(dirty_status)
    kept_dirty_paths, ignored_dirty_paths = filter_noise_paths(dirty_paths, strategy.dirty_tree_ignore)

    custom_baseline_paths = dedupe_paths(custom_committed_paths + kept_dirty_paths)
    touched_paths = dedupe_paths(upstream_paths + custom_baseline_paths)
    classifications = classify_paths(
        touched_paths,
        strategy,
        upstream_paths=upstream_paths,
        custom_paths=custom_baseline_paths,
    )
    counts_by_action = Counter(item.action for item in classifications)
    overlap_paths = len(set(upstream_paths) & set(custom_baseline_paths))

    grouped: dict[str, list[str]] = defaultdict(list)
    for classification in classifications:
        grouped[bucket_for(classification.path)].append(classification.path)
    for group_paths in grouped.values():
        group_paths.sort()

    return {
        "refs": {
            "current": current_ref,
            "upstream": upstream_ref,
            "merge_base": merge_base,
        },
        "counts": {
            "upstream_paths": len(upstream_paths),
            "custom_committed_paths": len(custom_committed_paths),
            "kept_dirty_paths": len(kept_dirty_paths),
            "ignored_dirty_paths": len(ignored_dirty_paths),
            "overlap_paths": overlap_paths,
            "touched_paths": len(touched_paths),
        },
        "action_counts": dict(sorted(counts_by_action.items())),
        "ignored_dirty_paths": ignored_dirty_paths,
        "custom_baseline_paths": custom_baseline_paths,
        "upstream_paths": upstream_paths,
        "classifications": [
            {
                "path": item.path,
                "action": item.action,
                "note": item.note,
                "pattern": item.pattern,
                "touched_upstream": item.touched_upstream,
                "touched_custom": item.touched_custom,
            }
            for item in classifications
        ],
        "groups": {name: paths for name, paths in sorted(grouped.items())},
    }


def write_report(payload: dict[str, object], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Upstream Diff Inventory",
        "",
        f"- Current ref: `{payload['refs']['current']}`",
        f"- Upstream ref: `{payload['refs']['upstream']}`",
        f"- Merge base: `{payload['refs']['merge_base']}`",
        f"- Upstream touched paths: `{payload['counts']['upstream_paths']}`",
        f"- Custom committed paths: `{payload['counts']['custom_committed_paths']}`",
        f"- Dirty baseline paths kept: `{payload['counts']['kept_dirty_paths']}`",
        f"- Paths touched on both sides: `{payload['counts']['overlap_paths']}`",
        f"- Total touched paths: `{payload['counts']['touched_paths']}`",
        "",
        "## Action Counts",
        "",
    ]
    for action, count in payload["action_counts"].items():
        lines.append(f"- `{action}`: `{count}`")

    lines.extend(["", "## Ignored Dirty Paths", ""])
    if payload["ignored_dirty_paths"]:
        lines.extend([f"- `{path}`" for path in payload["ignored_dirty_paths"]])
    else:
        lines.append("- none")

    for group_name, files in payload["groups"].items():
        lines.extend(["", f"## {group_name} ({len(files)})", ""])
        lines.extend([f"- `{path}`" for path in files])

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an upstream/custom diff inventory.")
    parser.add_argument("--current-ref", default="HEAD", help="Current ref to inspect.")
    parser.add_argument("--upstream-ref", default="upstream/main", help="Upstream ref to compare.")
    parser.add_argument(
        "--strategy-file",
        default=str(DEFAULT_STRATEGY_FILE),
        help="Path to the shared strategy JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    strategy_file = Path(args.strategy_file)
    if not strategy_file.is_absolute():
        strategy_file = (REPO_ROOT / strategy_file).resolve()

    payload = build_inventory(
        current_ref=args.current_ref,
        upstream_ref=args.upstream_ref,
        strategy_file=strategy_file,
    )

    out_json = REPO_ROOT / "_docs" / "upstream-main-diff-inventory.json"
    out_md = REPO_ROOT / "_docs" / "upstream-main-diff-inventory.md"
    write_report(payload, out_json, out_md)
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

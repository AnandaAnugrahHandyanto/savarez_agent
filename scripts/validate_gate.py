#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


HEAD_SHA_RE = re.compile(r"(?m)^\s*-\s*Head SHA:\s*(\S+)\s*$")
VERDICT_RE = re.compile(r"(?m)^\s*-\s*Verdict:\s*(\S+)\s*$")


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def ensure_repo_root() -> Path:
    return Path(git_output("rev-parse", "--show-toplevel"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate local gate artifacts for the current HEAD")
    p.add_argument("--gate-file", default=".hermes-gate/gate.json", help="Gate JSON path relative to repo root")
    return p.parse_args()


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _extract(pattern: re.Pattern[str], text: str, label: str, report_path: Path) -> Optional[str]:
    match = pattern.search(text)
    if not match:
        print(f"{label} missing in {report_path}", file=sys.stderr)
        return None
    return match.group(1)


def validate_report(report_path: Path, head_sha: str, section_name: str) -> int:
    if not report_path.exists():
        return fail(f"{section_name} report missing: {report_path}")

    text = report_path.read_text(encoding="utf-8")
    report_head_sha = _extract(HEAD_SHA_RE, text, "Head SHA", report_path)
    if report_head_sha is None:
        return 1
    if report_head_sha != head_sha:
        return fail(
            f"{section_name} report Head SHA mismatch: expected {head_sha}, got {report_head_sha}"
        )

    verdict = _extract(VERDICT_RE, text, "Verdict", report_path)
    if verdict is None:
        return 1
    if verdict != "PASS":
        return fail(f"{section_name} report Verdict is not PASS: {verdict}")

    return 0


def main() -> int:
    args = parse_args()
    repo_root = ensure_repo_root().resolve()
    head_sha = git_output("rev-parse", "HEAD")

    gate_path = Path(args.gate_file)
    if not gate_path.is_absolute():
        gate_path = repo_root / gate_path
    if not gate_path.exists():
        return fail(f"missing {gate_path}")

    try:
        data = json.loads(gate_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return fail(f"invalid gate file: {exc}")

    for key in ("head_sha", "review", "test"):
        if key not in data:
            return fail(f"gate.json missing top-level key: {key}")

    if data["head_sha"] != head_sha:
        return fail(f"gate.json head_sha mismatch: expected {head_sha}, got {data['head_sha']}")

    for section_name in ("review", "test"):
        section = data.get(section_name) or {}
        for key in ("status", "head_sha", "report_path"):
            if key not in section:
                return fail(f"gate.json {section_name} missing key: {key}")
        if section["status"] != "PASS":
            return fail(f"{section_name} status is not PASS: {section['status']}")
        if section["head_sha"] != head_sha:
            return fail(
                f"{section_name} head_sha mismatch: expected {head_sha}, got {section['head_sha']}"
            )

        report_path = Path(section["report_path"])
        if not report_path.is_absolute():
            report_path = repo_root / report_path
        report_path = report_path.resolve()
        try:
            report_path.relative_to(repo_root)
        except ValueError:
            return fail(f"{section_name} report is outside repo root: {report_path}")

        rc = validate_report(report_path, head_sha, section_name)
        if rc:
            return rc

    print(f"pre-push gate passed for {head_sha[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

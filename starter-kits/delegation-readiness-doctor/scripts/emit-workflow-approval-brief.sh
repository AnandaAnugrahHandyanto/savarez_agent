#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACT_DIR="$KIT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP="$(date +%Y-%m-%dT%H-%M-%S%z)"
REPORT_PATH="$ARTIFACT_DIR/workflow-approval-brief-$TIMESTAMP.md"
LATEST_PATH="$ARTIFACT_DIR/latest-workflow-approval-brief.md"

python - "$REPORT_PATH" "$LATEST_PATH" <<'PY'
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

report_path = Path(sys.argv[1])
latest_path = Path(sys.argv[2])
base = 'https://api.github.com/repos/NousResearch/hermes-agent'
headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'Hermes-Agent',
    'X-GitHub-Api-Version': '2022-11-28',
}

token = os.environ.get('GITHUB_TOKEN')
if not token:
    creds_path = Path.home() / '.git-credentials'
    if creds_path.exists():
        for line in creds_path.read_text().splitlines():
            if 'github.com' not in line or '@github.com' not in line or ':' not in line:
                continue
            token = line.split('://', 1)[1].rsplit('@github.com', 1)[0].split(':', 1)[1]
            break
if token:
    headers['Authorization'] = f'token {token}'

def get(url: str):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

pr = get(base + '/pulls/14297')
combined_status = get(base + f"/commits/{pr['head']['sha']}/status")
check_runs = get(base + f"/commits/{pr['head']['sha']}/check-runs")
check_suites = get(base + f"/commits/{pr['head']['sha']}/check-suites")

action_required_suites = [
    suite for suite in check_suites.get('check_suites', [])
    if suite.get('conclusion') == 'action_required'
]

suite_lines = '\n'.join(
    (
        f"- Suite `{suite['id']}` — {suite.get('status')} / {suite.get('conclusion') or 'pending'} | "
        f"created {suite.get('created_at')} | updated {suite.get('updated_at')}\n"
        f"  - API: {suite.get('url')}\n"
        f"  - Check runs API: {suite.get('check_runs_url')}\n"
        f"  - latest_check_runs_count: {suite.get('latest_check_runs_count', 0)} | rerequestable: {suite.get('rerequestable')}"
    )
    for suite in action_required_suites
) or '- none'

if action_required_suites and check_runs.get('total_count', 0) == 0:
    verdict = (
        'GitHub has created Actions check suites for the PR head commit, but no check runs have started. '
        'With every suite concluded as `action_required`, this is the fork-workflow approval gate, not a missing-test surface.'
    )
    next_move = (
        "A maintainer with repo permissions needs to approve and run the PR workflows for this forked branch/head commit. "
        "After approval, rerun `bash starter-kits/delegation-readiness-doctor/scripts/emit-pr-review-monitor.sh` and confirm the surface changes from `action_required` suites / `0` check runs to real check runs or status contexts."
    )
else:
    verdict = (
        'The workflow-approval signature is no longer the main blocker. Re-read the PR monitor and respond to the new live blocker instead of reusing this brief.'
    )
    next_move = (
        'Use `latest-pr-review-monitor.md` as the canonical live blocker surface and retire this brief if the suites are no longer action-required.'
    )

now = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
report = f"""# Delegation Readiness Doctor — Workflow Approval Brief

Generated: {now}
PR: {pr['html_url']}
Head SHA: `{pr['head']['sha']}`
Base SHA: `{pr['base']['sha']}`

## Live signature
- Combined status state: {combined_status.get('state')}
- Combined status contexts: {combined_status.get('total_count', 0)}
- Check runs: {check_runs.get('total_count', 0)}
- Check suites: {check_suites.get('total_count', 0)}
- Action-required suites: {len(action_required_suites)}

## Why this is the blocker
{verdict}

## Action-required suites
{suite_lines}

## Exact maintainer move
{next_move}

## Verification after approval
1. Refresh `latest-pr-review-monitor.md`.
2. Confirm at least one real check run or status context exists for head `{pr['head']['sha']}`.
3. If a failing run appears, answer that concrete failure from `latest-reviewer-handoff.md` instead of treating the PR as approval-blocked.

## Proof note
This brief is generated from the GitHub API (authenticated when a local token is available) and is meant to collapse a repeated blocker into one exact decision surface without tripping public rate limits.
"""
report_path.write_text(report, encoding='utf-8')
shutil.copyfile(report_path, latest_path)
print(report_path)
PY

chmod +x "$SCRIPT_DIR/emit-workflow-approval-brief.sh"
printf 'Wrote report: %s\n' "$REPORT_PATH"
printf 'Latest report: %s\n' "$LATEST_PATH"

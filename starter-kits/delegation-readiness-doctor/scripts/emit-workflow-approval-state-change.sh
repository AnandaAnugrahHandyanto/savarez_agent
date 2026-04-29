#!/usr/bin/env bash
# detect-workflow-approval-state-change.sh
# Emits latest-workflow-approval-state-change.md — the delta detector for the
# fork-workflow approval blocker on PR #14297.
#
# Unlike the approval-brief (snapshot) and approval-trigger (nudge packet), this
# script detects STATE TRANSITIONS in the GitHub Actions check suites and check
# runs. It is the automation that answers: "did the blocker just clear?"
#
# Exits 0 with BLOCKER_CLEARED when approval happened and CI is running.
# Exits 0 with BLOCKER_PERSISTS when action_required suites are still stuck.
# Exits 1 on API errors (fail-closed — do not assume approval on error).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACT_DIR="$KIT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP="$(date +%Y-%m-%dT%H-%M-%S%z)"
REPORT_PATH="$ARTIFACT_DIR/workflow-approval-state-change-$TIMESTAMP.md"
LATEST_PATH="$ARTIFACT_DIR/latest-workflow-approval-state-change.md"

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
artifacts_dir = latest_path.parent  # derived: artifacts_dir is the parent of latest_path
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
sha = pr['head']['sha']
combined_status = get(base + f'/commits/{sha}/status')
check_runs = get(base + f'/commits/{sha}/check-runs')
check_suites = get(base + f'/commits/{sha}/check-suites')
issue_comments = get(base + '/issues/14297/comments?per_page=100')

already_posted_nudge = any(
    (comment.get('user') or {}).get('login') == 'NplusM420'
    and 'Maintainer unblock request for PR #14297' in (comment.get('body') or '')
    for comment in issue_comments
)

action_required_suites = [
    suite for suite in check_suites.get('check_suites', [])
    if suite.get('conclusion') == 'action_required'
]

# Key signals we track
action_required_count = len(action_required_suites)
check_runs_total = check_runs.get('total_count', 0)
combined_state = combined_status.get('state', 'unknown')
completed_suites = [
    s for s in check_suites.get('check_suites', [])
    if s.get('conclusion') not in (None, 'action_required')
]

# Read the previous run's *current* state from the latest artifact if it exists.
# That file is the last emitted snapshot, so its current-state section is the right
# baseline for transition detection on the next run.
prev_action_required = None
prev_check_runs = None
prev_sha = None
prev_base_sha = None

if latest_path.exists():
    import re

    content = latest_path.read_text(encoding='utf-8')
    for raw_line in content.splitlines():
        line = raw_line.lstrip('- ').strip()
        if line.startswith('Head SHA:'):
            prev_sha = line.split(':', 1)[1].strip().strip('*`')
        elif line.startswith('Action_required suites:'):
            match = re.search(r'(\d+)', line)
            if match:
                prev_action_required = int(match.group(1))
        elif line.startswith('Check runs:'):
            match = re.search(r'(\d+)', line)
            if match:
                prev_check_runs = int(match.group(1))
        elif line.startswith('Base SHA:'):
            prev_base_sha = line.split(':', 1)[1].strip().strip('*`')

# Also read the last known base SHA from the branch-refresh artifact so we can
# detect drift even when the state-change file has never recorded a base SHA.
import re as re2
last_refresh_base = None
refresh_artifact = artifacts_dir / 'latest-reviewer-handoff.md'
if refresh_artifact.exists():
    for raw_line in refresh_artifact.read_text(encoding='utf-8').splitlines():
        line = raw_line.lstrip('- ').strip()
        if 'Current PR base SHA:' in line or line.startswith('Base SHA:'):
            last_refresh_base = line.split(':', 1)[1].strip().strip('*`')
            break

current_base_sha = pr.get('base', {}).get('sha') or pr.get('base', {}).get('ref', '')
# Use the more-precise baseline: refresh artifact > state-change previous run
baseline_base_sha = last_refresh_base or prev_base_sha
base_branch_advanced = (
    baseline_base_sha is not None
    and current_base_sha != baseline_base_sha
)

# Determine state change
blocker_cleared = (
    action_required_count == 0
    and check_runs_total > 0
    and prev_action_required is not None
    and prev_action_required > 0
)
blocker_persists = action_required_count > 0

# Transitions
approval_transition = (
    prev_action_required is not None
    and prev_action_required > 0
    and action_required_count == 0
)
ci_started_transition = (
    prev_check_runs is not None
    and prev_check_runs == 0
    and check_runs_total > 0
)
base_branch_drift_transition = base_branch_advanced

# Status text
if base_branch_drift_transition:
    verdict = '**BASE_BRANCH_ADVANCED**'
    verdict_detail = (
        f'origin/main has advanced past the base SHA recorded at last refresh ({baseline_base_sha[:8]}… → {current_base_sha[:8]}…). '
        'While the PR head is unchanged, the base is now stale. '
        'If maintainer approval eventually comes through with a stale base, the PR will be non-mergeable. '
        'Rerun the branch-refresh operation before re-triggering CI.'
    )
elif blocker_cleared:
    verdict = '**BLOCKER_CLEARED**'
    verdict_detail = (
        'Maintainer approved the fork PR workflows. '
        f'{check_runs_total} check run(s) now exist and action_required suites are gone.'
    )
elif approval_transition and check_runs_total == 0:
    verdict = '**APPROVAL_BUT_CI_NOT_STARTED**'
    verdict_detail = (
        f'Maintainer cleared the {prev_action_required} action_required suite(s), '
        'but no check runs have appeared yet. Re-run emit-pr-review-monitor.sh '
        'and emit-ci-result-interpreter.sh to track CI startup.'
    )
elif ci_started_transition:
    verdict = '**CI_STARTED**'
    verdict_detail = (
        f'Check runs appeared: {prev_check_runs} → {check_runs_total}. '
        'The blocker shifted from approval to CI interpretation. '
        'Rerun emit-ci-result-interpreter.sh to get the first-CI decision surface.'
    )
elif blocker_persists:
    verdict = '**BLOCKER_PERSISTS**'
    verdict_detail = (
        f'{action_required_count} action_required suite(s) still present. '
        'Maintainer approval is still the blocker. '
        'No state change since last run.'
    )
else:
    verdict = '**NO_CHANGE**'
    verdict_detail = (
        'No relevant state change detected. '
        f'Action_required suites: {action_required_count}, check runs: {check_runs_total}.'
    )

now = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
report = f"""# Delegation Readiness Doctor — Workflow Approval State Change

Generated: {now}
PR: https://github.com/NousResearch/hermes-agent/pull/14297
Head SHA: `{sha}`

## Verdict
{verdict}

{verdict_detail}

---

## Current state
- Action_required suites: **{action_required_count}**
- Check runs: **{check_runs_total}**
- Combined status state: **{combined_state}**
- Completed suites (non-action_required): **{len(completed_suites)}**
- Base SHA: **`{current_base_sha}`**

## Previous state (from last run)
- Previous head SHA: `{prev_sha or 'unknown'}`
- Previous action_required suites: `{prev_action_required if prev_action_required is not None else 'unknown'}`
- Previous check runs: `{prev_check_runs if prev_check_runs is not None else 'unknown'}`
- Previous base SHA: `{prev_base_sha or ('unknown — check latest-reviewer-handoff.md for baseline')}`

## Detected transitions
- Approval transition (action_required → cleared): **{'YES' if approval_transition else 'no'}**
- CI started transition (0 check runs → >0): **{'YES' if ci_started_transition else 'no'}**
- Base branch drift (origin/main advanced since last refresh): **{'YES — RERUN BRANCH REFRESH' if base_branch_drift_transition else 'no'}**

## Exact next move
{"Rerun the branch-refresh script before re-triggering CI — origin/main has advanced since the last recorded base SHA. See latest-pr-branch-refresh.md for the refresh procedure." if base_branch_drift_transition else "Run `bash starter-kits/delegation-readiness-doctor/scripts/emit-pr-review-monitor.sh` and `bash starter-kits/delegation-readiness-doctor/scripts/emit-ci-result-interpreter.sh` to get the post-approval CI surface." if blocker_cleared or approval_transition else "Maintainer workflow approval is still the blocker. The maintainer unblock request is already posted, so do not repost it unless the blocker signature changes materially; wait for a detector-visible approval, review, or check-run start and then refresh the PR/CI packet immediately." if already_posted_nudge else "Maintainer workflow approval is still the blocker. Use `latest-workflow-approval-trigger.md` for the ready-to-post nudge."}

## Check run details
{chr(10).join(f"- {c['name']} — {c['status']} / {c.get('conclusion') or 'pending'}" for c in check_runs.get('check_runs', [])) or '- none yet'}

## Suite details
{chr(10).join(f"- Suite {s['id']} — {s.get('status')} / {s.get('conclusion') or 'pending'}" for s in check_suites.get('check_suites', [])) or '- none'}

---

*This artifact is the state-change detector for the fork-workflow approval blocker. It compares current GitHub Actions state against the previous run to surface transitions, so the automation system knows when the blocker has cleared without manual snapshot comparison.*
"""
report_path.write_text(report, encoding='utf-8')
shutil.copyfile(report_path, latest_path)
print(report_path)
print(verdict)
PY

chmod +x "$SCRIPT_DIR/emit-workflow-approval-state-change.sh"
printf 'Wrote report: %s\n' "$REPORT_PATH"
printf 'Latest report: %s\n' "$LATEST_PATH"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACT_DIR="$KIT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP="$(date +%Y-%m-%dT%H-%M-%S%z)"
REPORT_PATH="$ARTIFACT_DIR/pr-review-monitor-$TIMESTAMP.md"
LATEST_PATH="$ARTIFACT_DIR/latest-pr-review-monitor.md"

python - "$REPORT_PATH" "$LATEST_PATH" <<'PY'
import json
import os
import re
import shutil
import sys
import time
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


def get_pr_with_mergeability(max_attempts: int = 6, delay_seconds: int = 2):
    pr = get(base + '/pulls/14297')
    attempts = 1
    while attempts < max_attempts and pr.get('mergeable') is None:
        time.sleep(delay_seconds)
        pr = get(base + '/pulls/14297')
        attempts += 1
    return pr, attempts


pr, mergeability_attempts = get_pr_with_mergeability()
issue = get(base + '/issues/14297')
reviews = get(base + '/pulls/14297/reviews')
comments = get(base + '/issues/14297/comments')
statuses = get(pr['statuses_url'])
combined_status = get(base + f"/commits/{pr['head']['sha']}/status")
check_runs = get(base + f"/commits/{pr['head']['sha']}/check-runs")
check_suites = get(base + f"/commits/{pr['head']['sha']}/check-suites")

action_required_suites = [
    suite
    for suite in check_suites.get('check_suites', [])
    if suite.get('conclusion') == 'action_required'
]

review_lines = '\n'.join(
    f"- {review['user']['login']} — {review['state']} at {review['submitted_at']}"
    for review in reviews
) or '- none yet'

comment_lines = '\n'.join(
    f"- {comment['user']['login']} at {comment['created_at']}: {comment['body'].strip()[:160] or '(empty)'}"
    for comment in comments
) or '- none yet'

status_lines = '\n'.join(
    f"- {status['context'] or '(no context)'} — {status['state']} ({status.get('description') or 'no description'})"
    for status in statuses
) or '- none yet'

check_lines = '\n'.join(
    f"- {check['name']} — {check['status']} / {check['conclusion'] or 'pending'}"
    for check in check_runs.get('check_runs', [])
) or '- none yet'

suite_lines = '\n'.join(
    f"- {suite.get('app', {}).get('name', 'GitHub Actions')} — {suite['status']} / {suite.get('conclusion') or 'pending'}"
    for suite in check_suites.get('check_suites', [])
) or '- none yet'

if pr['state'] != 'open':
    blocker = f"PR is no longer open (`state={pr['state']}`); handoff status must be re-evaluated from live GitHub state."
elif pr.get('mergeable') is False:
    blocker = 'GitHub now reports the PR as not mergeable; the next move is resolving the merge conflict or policy failure from live review state.'
elif pr.get('mergeable') is None:
    blocker = (
        'GitHub has not finished computing mergeability yet; upstream attention is still absent, '
        'but the monitor should be treated as pending until mergeability resolves from live API state.'
    )
elif action_required_suites:
    blocker = (
        f"{len(action_required_suites)} GitHub Actions check suite(s) are present but stuck at `action_required`; "
        'the true blocker is still maintainer workflow approval or equivalent maintainer intervention, even if a nudge comment already exists.'
    )
elif reviews:
    blocker = 'Maintainer review activity exists; the blocker is now responding precisely to review feedback, not waiting for first review.'
elif check_runs.get('total_count', 0) > 0:
    blocker = 'Real CI movement exists; the blocker is now interpreting the first check-run result precisely instead of waiting for approval.'
elif comments:
    blocker = 'A PR comment exists, but there are still no real reviews or check runs; the blocker remains external maintainer attention.'
else:
    blocker = 'No upstream reviews, issue comments, commit statuses, check runs, or action-required check suites exist yet; the blocker is external maintainer attention, not missing local proof.'

next_move = (
    'If the action-required suites remain, get the fork PR workflows approved or otherwise nudged by a maintainer; '
    'once automation can run or a review appears, answer the first upstream signal with exact proof references from the starter-kit artifacts.'
)

now = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
report = f"""# Delegation Readiness Doctor — PR Review Monitor

Generated: {now}

## PR identity
- Title: {pr['title']}
- URL: {pr['html_url']}
- State: {pr['state']}
- Draft: {pr['draft']}
- Mergeable: {pr.get('mergeable')}
- Mergeable state: {pr.get('mergeable_state')}
- Mergeability poll attempts: {mergeability_attempts}
- Base ← Head: `{pr['base']['ref']} <- {pr['head']['label']}`
- Head SHA: `{pr['head']['sha']}`
- Base SHA: `{pr['base']['sha']}`
- Commits / files: `{pr['commits']} commit`, `{pr['changed_files']} files`
- Additions / deletions: `{pr['additions']} / {pr['deletions']}`
- Created: {pr['created_at']}
- Updated: {pr['updated_at']}

## Review surface
- Review count: {len(reviews)}
- Issue comment count: {issue['comments']}
- Review comment count: {pr['review_comments']}

### Reviews
{review_lines}

### Issue comments
{comment_lines}

## Automation surface
- Combined statuses: {len(statuses)}
- Combined status state: {combined_status.get('state')}
- Check runs: {check_runs.get('total_count', 0)}
- Check suites: {check_suites.get('total_count', 0)}
- Action-required suites: {len(action_required_suites)}

### Status contexts
{status_lines}

### Check runs
{check_lines}

### Check suites
{suite_lines}

## Live blocker
{blocker}

## Exact next move
{next_move}

## Proof note
This report was emitted from the GitHub API (authenticated when a local token is available) so the repo-durability blocker is grounded in live PR state without depending on the lower public rate limit.
"""
report_path.write_text(report, encoding='utf-8')
shutil.copyfile(report_path, latest_path)
print(report_path)
PY

chmod +x "$SCRIPT_DIR/emit-pr-review-monitor.sh"
printf 'Wrote report: %s\n' "$REPORT_PATH"
printf 'Latest report: %s\n' "$LATEST_PATH"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACT_DIR="$KIT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

TIMESTAMP="$(date +%Y-%m-%dT%H-%M-%S%z)"
REPORT_PATH="$ARTIFACT_DIR/ci-result-interpreter-$TIMESTAMP.md"
LATEST_PATH="$ARTIFACT_DIR/latest-ci-result-interpreter.md"

python - "$REPORT_PATH" "$LATEST_PATH" "$KIT_DIR" <<'PY'
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
kit_dir = Path(sys.argv[3])
artifacts_dir = kit_dir / 'artifacts'
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

def extract_clean_suite_summary() -> tuple[str, str]:
    path = artifacts_dir / 'latest-clean-commit-surface.md'
    if not path.exists():
        return ('unknown', f'Missing proof artifact: {path}')
    text = path.read_text(encoding='utf-8')
    match = re.search(r'(?m)^(\d+ passed, .*?)$', text)
    summary = match.group(1) if match else 'Focused proof suite result not parsed'
    return (summary, 'starter-kits/delegation-readiness-doctor/artifacts/latest-clean-commit-surface.md')

pr = get(base + '/pulls/14297')
head_sha = pr['head']['sha']
base_sha = pr['base']['sha']
check_runs = get(base + f'/commits/{head_sha}/check-runs')
check_suites = get(base + f'/commits/{head_sha}/check-suites')
combined_status = get(base + f'/commits/{head_sha}/status')

runs = check_runs.get('check_runs', [])
action_required_suites = [
    suite for suite in check_suites.get('check_suites', [])
    if suite.get('conclusion') == 'action_required'
]
completed = [run for run in runs if run.get('status') == 'completed']
failures = [
    run for run in completed
    if (run.get('conclusion') or '').lower() not in {'success', 'neutral', 'skipped'}
]
pending = [run for run in runs if run.get('status') != 'completed']

proof_summary, proof_path = extract_clean_suite_summary()

if action_required_suites and not runs:
    verdict = 'WAITING_FOR_WORKFLOW_APPROVAL'
    blocker = (
        f"{len(action_required_suites)} GitHub Actions suite(s) are still `action_required` and there are 0 real check runs. "
        'The first upstream CI result does not exist yet; maintainer workflow approval remains the blocker.'
    )
    next_move = (
        'Get the fork PR workflows approved by a maintainer, then rerun this interpreter as soon as the first real check run appears.'
    )
elif pending:
    verdict = 'WAITING_FOR_CI_COMPLETION'
    blocker = (
        f"{len(pending)} check run(s) exist but are not complete yet. The blocker has shifted from approval to waiting for the first completed CI result."
    )
    next_move = 'Rerun this interpreter when the first check run completes so the result can be mapped back to the clean proof line.'
elif failures:
    verdict = 'CI_FAILURE_REQUIRES_TRIAGE'
    blocker = (
        f"{len(failures)} completed check run(s) failed. The blocker is now concrete CI triage, not workflow approval."
    )
    next_move = (
        'Compare the failed check names below with the local clean proof suite, rerun the focused proof command, and answer the exact failing signal on the PR with the matching artifact path.'
    )
elif completed:
    verdict = 'UPSTREAM_CI_GREEN'
    blocker = 'No CI blocker remains in the first completed run set; the next blocker is maintainer review / merge.'
    next_move = 'Rerun the PR review monitor and move the handoff from workflow approval to review/merge follow-through.'
else:
    verdict = 'NO_CI_SIGNAL_DETECTED'
    blocker = 'No check runs were found yet. Reconfirm workflow approval / GitHub Actions visibility from the PR monitor.'
    next_move = 'Rerun the PR review monitor, then rerun this interpreter once real check runs exist.'

routing_rules = [
    ('doctor', 'Doctor output/regression surface → `python -m hermes_cli.main doctor`, `starter-kits/delegation-readiness-doctor/artifacts/latest-readiness-proof.md`'),
    ('delegate', 'Delegation readiness helper/tests → `pytest -q -n0 tests/tools/test_delegate.py tests/tools/test_delegate_credentials.py`, `starter-kits/delegation-readiness-doctor/artifacts/latest-clean-commit-surface.md`'),
    ('credential', 'Credential resolution / readiness logic → `tests/tools/test_delegate_credentials.py`, `starter-kits/delegation-readiness-doctor/artifacts/latest-broken-state-roundtrip.md`'),
]

def route_failure(name: str) -> str:
    lower = name.lower()
    for needle, route in routing_rules:
        if needle in lower:
            return route
    return ('Unclassified CI failure → rerun the focused clean proof suite and compare against '
            '`starter-kits/delegation-readiness-doctor/artifacts/latest-clean-commit-surface.md`.')

check_lines = '\n'.join(
    f"- {run['name']} — {run.get('status')} / {run.get('conclusion') or 'pending'}"
    for run in runs
) or '- none yet'

failure_lines = '\n'.join(
    f"- {run['name']} — {run.get('conclusion') or 'unknown'} | route: {route_failure(run['name'])}"
    for run in failures
) or '- none'

suite_lines = '\n'.join(
    f"- {suite.get('app', {}).get('name', 'GitHub Actions')} — {suite.get('status')} / {suite.get('conclusion') or 'pending'}"
    for suite in check_suites.get('check_suites', [])
) or '- none yet'

now = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
report = f"""# Delegation Readiness Doctor — CI Result Interpreter

Generated: {now}
PR: {pr['html_url']}
Head SHA: `{head_sha}`
Base SHA: `{base_sha}`
Verdict: **{verdict}**

## Current CI surface
- Combined status state: {combined_status.get('state')}
- Check runs: {check_runs.get('total_count', 0)}
- Completed check runs: {len(completed)}
- Pending check runs: {len(pending)}
- Failed check runs: {len(failures)}
- Check suites: {check_suites.get('total_count', 0)}
- Action-required suites: {len(action_required_suites)}

### Check runs
{check_lines}

### Check suites
{suite_lines}

## Clean local proof anchor
- Focused suite summary: `{proof_summary}`
- Proof artifact: `{proof_path}`
- Companion roundtrip proof: `starter-kits/delegation-readiness-doctor/artifacts/latest-broken-state-roundtrip.md`
- Reviewer handoff: `starter-kits/delegation-readiness-doctor/artifacts/latest-reviewer-handoff.md`

## Live blocker
{blocker}

## Exact next move
{next_move}

## Failure routing
{failure_lines}

## Proof note
This interpreter is generated from the GitHub API (authenticated when a local token is available) and should be refreshed immediately when the live CI/review signal changes.
"""
report_path.write_text(report, encoding='utf-8')
shutil.copyfile(report_path, latest_path)
print(report_path)
PY

chmod +x "$SCRIPT_DIR/emit-ci-result-interpreter.sh"
printf 'Wrote report: %s\n' "$REPORT_PATH"
printf 'Latest report: %s\n' "$LATEST_PATH"

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRY_RUN_DIR = ROOT / 'examples' / 'v2.6.0' / 'dry-run-two-worker'
DEFAULT_POSITIVE_SUMMARY = ROOT / 'examples' / 'v2.6.0' / 'evidence-validation-summary.json'
DEFAULT_NEGATIVE_SUMMARY = ROOT / 'examples' / 'v2.6.0' / 'negative-validation-summary.json'
DEFAULT_VERIFY_SUMMARY = ROOT / 'examples' / 'v2.6.0' / 'verify-chain-summary.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def run_step(name: str, cmd: list[str], cwd: Path) -> dict[str, Any]:
    started = time.time()
    cp = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    elapsed_ms = int((time.time() - started) * 1000)
    stdout_tail = cp.stdout[-4000:]
    stderr_tail = cp.stderr[-4000:]
    return {
        'name': name,
        'command': cmd,
        'returncode': cp.returncode,
        'ok': cp.returncode == 0,
        'elapsed_ms': elapsed_ms,
        'stdout_tail': stdout_tail,
        'stderr_tail': stderr_tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run A2A v2.6.3 local verify chain without new live A2A calls.')
    parser.add_argument('--dry-run-dir', default=str(DEFAULT_DRY_RUN_DIR))
    parser.add_argument('--positive-summary', default=str(DEFAULT_POSITIVE_SUMMARY))
    parser.add_argument('--negative-summary', default=str(DEFAULT_NEGATIVE_SUMMARY))
    parser.add_argument('--write-summary', default=str(DEFAULT_VERIFY_SUMMARY))
    parser.add_argument('--skip-dry-run-runner', action='store_true', help='Only validate existing evidence; do not regenerate dry-run evidence.')
    args = parser.parse_args()

    dry_run_dir = Path(args.dry_run_dir)
    positive_summary = Path(args.positive_summary)
    negative_summary = Path(args.negative_summary)
    verify_summary = Path(args.write_summary)

    steps: list[dict[str, Any]] = []
    if not args.skip_dry_run_runner:
        steps.append(run_step('v260_dry_run_two_worker_runner', [
            sys.executable,
            'scripts/hermes_openclaw_v260_two_worker.py',
            '--dry-run',
            '--out-dir',
            str(dry_run_dir),
        ], ROOT))

    steps.append(run_step('v261_positive_evidence_validator', [
        sys.executable,
        'scripts/validate_a2a_v260_evidence.py',
        '--dry-run-dir',
        str(dry_run_dir),
        '--write-summary',
        str(positive_summary),
    ], ROOT))

    steps.append(run_step('v262_negative_failure_path_validator', [
        sys.executable,
        'scripts/validate_a2a_v260_negative.py',
        '--positive-summary',
        str(positive_summary),
        '--write-summary',
        str(negative_summary),
    ], ROOT))

    positive = load_json(positive_summary) if positive_summary.exists() else {'ok': False, 'missing': str(positive_summary)}
    negative = load_json(negative_summary) if negative_summary.exists() else {'ok': False, 'missing': str(negative_summary)}
    dry_summary_path = dry_run_dir / 'execution-summary.json'
    dry_summary = load_json(dry_summary_path) if dry_summary_path.exists() else {'ok': False, 'missing': str(dry_summary_path)}

    side_effects = {
        'new_live_a2a_call': False,
        'gateway_restart': False,
        'openclaw_restart': False,
        'cron_enabled': False,
        'daemon_enabled': False,
        'webhook_enabled': False,
        'platform_send': False,
        'reverse_loop_enabled': False,
    }

    out = {
        'schema_version': 'a2a-v263-verify-chain-v1',
        'created_at': now_iso(),
        'ok': all(step['ok'] for step in steps) and positive.get('ok') is True and negative.get('ok') is True and dry_summary.get('ok') is True,
        'result': 'PASS' if all(step['ok'] for step in steps) and positive.get('ok') is True and negative.get('ok') is True and dry_summary.get('ok') is True else 'FAIL',
        'steps': steps,
        'artifacts': {
            'dry_run_dir': str(dry_run_dir),
            'dry_run_execution_summary': str(dry_summary_path),
            'positive_summary': str(positive_summary),
            'negative_summary': str(negative_summary),
            'verify_summary': str(verify_summary),
        },
        'checks': {
            'dry_run_runner_ok': dry_summary.get('ok') is True,
            'positive_evidence_ok': positive.get('ok') is True,
            'negative_validation_ok': negative.get('ok') is True,
            'step_exit_codes_ok': all(step['ok'] for step in steps),
        },
        'side_effects': side_effects,
        'boundary': 'Local dry-run + existing live evidence validation only; no new live A2A call, no cron/daemon/webhook, no service restart, no platform send.',
    }
    verify_summary.parent.mkdir(parents=True, exist_ok=True)
    verify_summary.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

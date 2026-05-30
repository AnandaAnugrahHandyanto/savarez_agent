#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FORBIDDEN_PATTERNS = [
    re.compile(r'Authorization\s*:', re.I),
    re.compile(r'Bearer\s+\S+', re.I),
    re.compile(r'api[_-]?key\s*[:=]', re.I),
    re.compile(r'password\s*[:=]', re.I),
    re.compile(r'secret\s*[:=]', re.I),
]

ALLOWED_OVERALL = {'accepted', 'accepted_with_boundary', 'rejected', 'blocked', 'unsafe'}


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:  # noqa: BLE001
        errors.append(f'{path}: json parse failed: {exc}')
        return {}
    if not isinstance(data, dict):
        errors.append(f'{path}: root must be object')
        return {}
    return data


def scan_forbidden(base: Path) -> list[str]:
    hits: list[str] = []
    if not base.exists():
        return [f'{base}: missing for scan']
    for path in sorted(base.rglob('*')):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                hits.append(f'{path}:{pattern.pattern}')
    return hits


def validate_receipt(receipt_path: Path, errors: list[str]) -> dict[str, Any]:
    r = load_json(receipt_path, errors)
    for key in ['schema_version', 'ok', 'task_id', 'source_agent', 'target_agent', 'protocol', 'http_status', 'remote_task_id', 'remote_context_id', 'state', 'marker', 'artifact_text_preview', 'evidence_path', 'auth']:
        if key not in r:
            errors.append(f'{receipt_path}: missing {key}')
    if r.get('schema_version') != 'a2a-worker-receipt-v1':
        errors.append(f'{receipt_path}: invalid schema_version')
    if r.get('source_agent') != 'hermes':
        errors.append(f'{receipt_path}: source_agent must be hermes')
    if r.get('ok') is not True:
        errors.append(f'{receipt_path}: ok must be true')
    if r.get('http_status') != 200:
        errors.append(f'{receipt_path}: http_status must be 200')
    if r.get('state') != 'completed':
        errors.append(f'{receipt_path}: state must be completed')
    if not isinstance(r.get('auth'), dict) or r.get('auth', {}).get('token_recorded') is not False:
        errors.append(f'{receipt_path}: auth.token_recorded must be false')
    evidence = Path(str(r.get('evidence_path', '')))
    if not evidence.exists():
        errors.append(f'{receipt_path}: evidence missing {evidence}')
    else:
        text = evidence.read_text(encoding='utf-8', errors='replace')
        if r.get('marker') not in text:
            errors.append(f'{receipt_path}: marker not found in evidence')
    return r


def validate_acceptance(path: Path, errors: list[str]) -> dict[str, Any]:
    acc = load_json(path, errors)
    for key in ['schema_version', 'run_id', 'overall', 'items', 'secret_scan', 'external_side_effects']:
        if key not in acc:
            errors.append(f'{path}: missing {key}')
    if acc.get('schema_version') != 'a2a-acceptance-report-v1':
        errors.append(f'{path}: invalid schema_version')
    if acc.get('overall') not in ALLOWED_OVERALL:
        errors.append(f'{path}: invalid overall')
    if not isinstance(acc.get('items'), list) or not acc.get('items'):
        errors.append(f'{path}: items must be non-empty list')
    secret_scan = acc.get('secret_scan') if isinstance(acc.get('secret_scan'), dict) else {}
    if secret_scan.get('ok') is not True:
        errors.append(f'{path}: secret_scan.ok must be true')
    if secret_scan.get('token_recorded') is not False:
        errors.append(f'{path}: secret_scan.token_recorded must be false')
    return acc


def validate_mock_dir(base: Path) -> dict[str, Any]:
    errors: list[str] = []
    required = [
        'dispatch-worker-readiness.json', 'dispatch-worker-review.json',
        'receipt-worker-readiness.json', 'receipt-worker-review.json',
        'acceptance-report.json', 'validation-summary.json',
    ]
    for name in required:
        if not (base / name).is_file():
            errors.append(f'{base/name}: missing')
    summary = load_json(base / 'validation-summary.json', errors) if (base / 'validation-summary.json').exists() else {}
    if summary.get('ok') is not True:
        errors.append(f'{base}/validation-summary.json: ok must be true')
    acc = validate_acceptance(base / 'acceptance-report.json', errors) if (base / 'acceptance-report.json').exists() else {}
    receipts = []
    for name in ['receipt-worker-readiness.json', 'receipt-worker-review.json']:
        if (base / name).exists():
            receipts.append(validate_receipt(base / name, errors))
    forbidden = scan_forbidden(base)
    errors.extend(forbidden)
    return {
        'kind': 'mock-fixtures',
        'path': str(base),
        'ok': not errors,
        'receipt_count': len([r for r in receipts if r]),
        'accepted_count': len(acc.get('items', [])) if isinstance(acc.get('items'), list) else 0,
        'overall': acc.get('overall'),
        'errors': errors,
    }


def validate_run_dir(base: Path, expect_live: bool | None) -> dict[str, Any]:
    errors: list[str] = []
    for name in ['readiness.json', 'acceptance-report.json', 'execution-summary.json', 'compact-summary.md']:
        if not (base / name).is_file():
            errors.append(f'{base/name}: missing')
    readiness = load_json(base / 'readiness.json', errors) if (base / 'readiness.json').exists() else {}
    acc = validate_acceptance(base / 'acceptance-report.json', errors) if (base / 'acceptance-report.json').exists() else {}
    summary = load_json(base / 'execution-summary.json', errors) if (base / 'execution-summary.json').exists() else {}
    if summary.get('ok') is not True:
        errors.append(f'{base}/execution-summary.json: ok must be true')
    if summary.get('receipt_count') != 2:
        errors.append(f'{base}/execution-summary.json: receipt_count must be 2')
    if summary.get('accepted_count') != 2:
        errors.append(f'{base}/execution-summary.json: accepted_count must be 2')
    if acc.get('overall') != 'accepted_with_boundary':
        errors.append(f'{base}/acceptance-report.json: overall must be accepted_with_boundary')
    side = acc.get('external_side_effects') if isinstance(acc.get('external_side_effects'), dict) else {}
    if expect_live is not None:
        if side.get('live_a2a_call') is not expect_live:
            errors.append(f'{base}/acceptance-report.json: live_a2a_call must be {expect_live}')
        if readiness.get('dry_run') is expect_live:
            errors.append(f'{base}/readiness.json: dry_run/live expectation mismatch')
    for key in ['gateway_restart', 'openclaw_restart', 'cron_enabled', 'platform_send']:
        if side.get(key) is not False:
            errors.append(f'{base}/acceptance-report.json: external_side_effects.{key} must be false')
    receipts = []
    for rp in sorted(base.glob('*-receipt.json')):
        receipts.append(validate_receipt(rp, errors))
    if len(receipts) != 2:
        errors.append(f'{base}: expected 2 receipt files, got {len(receipts)}')
    forbidden = scan_forbidden(base)
    errors.extend(forbidden)
    return {
        'kind': 'two-worker-run',
        'path': str(base),
        'expected_live': expect_live,
        'ok': not errors,
        'run_id': acc.get('run_id') or summary.get('run_id'),
        'receipt_count': len(receipts),
        'accepted_count': summary.get('accepted_count'),
        'overall': acc.get('overall'),
        'errors': errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mock-dir', default='examples/v2.6.0/mock-fixtures')
    ap.add_argument('--dry-run-dir', default='examples/v2.6.0/dry-run-two-worker')
    ap.add_argument('--live-dir', default='examples/v2.6.0/live-two-worker')
    ap.add_argument('--write-summary', default='examples/v2.6.0/evidence-validation-summary.json')
    args = ap.parse_args()

    results = [
        validate_mock_dir(Path(args.mock_dir)),
        validate_run_dir(Path(args.dry_run_dir), expect_live=False),
        validate_run_dir(Path(args.live_dir), expect_live=True),
    ]
    out = {
        'schema_version': 'a2a-v260-evidence-validation-v1',
        'ok': all(r['ok'] for r in results),
        'results': results,
        'side_effects': {
            'new_live_a2a_call': False,
            'gateway_restart': False,
            'openclaw_restart': False,
            'cron_enabled': False,
            'platform_send': False,
        },
    }
    Path(args.write_summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.write_summary).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

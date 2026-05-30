#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

FORBIDDEN_PATTERNS = [
    ('authorization_header', re.compile(r'Authorization\s*:', re.I)),
    ('bearer_literal', re.compile(r'Bearer\s+\S+', re.I)),
    ('api_key_literal', re.compile(r'api[_-]?key\s*[:=]', re.I)),
    ('password_literal', re.compile(r'password\s*[:=]', re.I)),
    ('secret_literal', re.compile(r'secret\s*[:=]', re.I)),
]

EXPECTED_FAILURES = {
    'marker_missing',
    'token_recorded_true',
    'forbidden_literal',
    'evidence_missing',
    'unexpected_side_effect',
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def detect_failures(receipt: dict[str, Any], base: Path) -> list[str]:
    failures: list[str] = []
    if receipt.get('auth', {}).get('token_recorded') is not False:
        failures.append('token_recorded_true')
    evidence_path = Path(str(receipt.get('evidence_path', '')))
    if not evidence_path.exists():
        failures.append('evidence_missing')
        evidence_text = ''
    else:
        evidence_text = evidence_path.read_text(encoding='utf-8', errors='replace')
        marker = str(receipt.get('marker', ''))
        if marker and marker not in evidence_text:
            failures.append('marker_missing')
    scan_text = json.dumps(receipt, ensure_ascii=False) + '\n' + evidence_text
    if any(p.search(scan_text) for _, p in FORBIDDEN_PATTERNS):
        failures.append('forbidden_literal')
    effects = receipt.get('external_side_effects') if isinstance(receipt.get('external_side_effects'), dict) else {}
    for key in ['gateway_restart', 'openclaw_restart', 'cron_enabled', 'platform_send']:
        if effects.get(key) is not None and effects.get(key) is not False:
            failures.append('unexpected_side_effect')
            break
    return sorted(set(failures))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture-dir', default='examples/v2.6.0/negative-fixtures')
    ap.add_argument('--positive-summary', default='examples/v2.6.0/evidence-validation-summary.json')
    ap.add_argument('--write-summary', default='examples/v2.6.0/negative-validation-summary.json')
    args = ap.parse_args()

    base = Path(args.fixture_dir)
    manifest = load_json(base / 'manifest.json')
    positive = load_json(Path(args.positive_summary)) if Path(args.positive_summary).exists() else {'ok': False}
    case_results = []
    errors: list[str] = []
    for case in manifest.get('cases', []):
        path = base / case['file']
        expected = case['expected_failure']
        if expected not in EXPECTED_FAILURES:
            errors.append(f'{path}: unsupported expected_failure {expected}')
            continue
        receipt = load_json(path)
        failures = detect_failures(receipt, base)
        matched = expected in failures
        if not matched:
            errors.append(f'{path}: expected {expected}, got {failures}')
        case_results.append({'file': str(path), 'expected_failure': expected, 'detected_failures': failures, 'matched': matched})
    side = manifest.get('side_effects', {}) if isinstance(manifest.get('side_effects'), dict) else {}
    side_ok = all(side.get(k) is False for k in ['new_live_a2a_call', 'gateway_restart', 'openclaw_restart', 'cron_enabled', 'platform_send'])
    if not side_ok:
        errors.append('manifest side effects are not all false')
    if positive.get('ok') is not True:
        errors.append('positive evidence validator regression is not ok')
    out = {
        'schema_version': 'a2a-v262-negative-validation-v1',
        'ok': not errors and len(case_results) >= 5 and all(c['matched'] for c in case_results),
        'case_count': len(case_results),
        'matched_count': sum(1 for c in case_results if c['matched']),
        'cases': case_results,
        'positive_regression_ok': positive.get('ok') is True,
        'side_effects': {
            'new_live_a2a_call': False,
            'gateway_restart': False,
            'openclaw_restart': False,
            'cron_enabled': False,
            'platform_send': False,
        },
        'errors': errors,
    }
    Path(args.write_summary).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

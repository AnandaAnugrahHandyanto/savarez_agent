#!/usr/bin/env python3
"""Detect whether today's synced QMT daily report changed materially."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def normalize_report(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('- 数据源：'):
            continue
        line = re.sub(r'20\d{6}', '<DATE>', line)
        line = re.sub(r'\s+', ' ', line)
        lines.append(line)
    return '\n'.join(lines)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_state(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def build_state(today: str, report_path: Path, normalized_hash: str) -> dict:
    return {
        'date': today,
        'report_path': str(report_path),
        'normalized_hash': normalized_hash,
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }


def detect_status(report_path: Path, state_path: Path) -> tuple[str, str, dict]:
    if not report_path.exists():
        return 'MISSING', '', {}

    report_text = report_path.read_text(encoding='utf-8', errors='replace')
    normalized = normalize_report(report_text)
    current_hash = digest(normalized)
    prev = load_state(state_path)
    changed = current_hash != prev.get('normalized_hash')
    status = 'CHANGED' if changed else 'UNCHANGED'
    return status, current_hash, build_state(datetime.now().strftime('%Y%m%d'), report_path, current_hash)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', action='store_true', help='Persist the current normalized hash as the delivered state')
    args = parser.parse_args()

    today = datetime.now().strftime('%Y%m%d')
    report_path = Path('qmt_sync/reports') / today / 'daily_report.txt'
    state_path = Path('qmt_sync/reports') / '.last_feishu_daily_report_state.json'

    status, current_hash, state = detect_status(report_path, state_path)
    if status == 'MISSING':
        print(f'STATUS=MISSING')
        print(f'REPORT_PATH={report_path}')
        return 0

    if args.commit:
        write_state(state_path, state)
        print('STATE_COMMITTED=1')
    else:
        print('STATE_COMMITTED=0')

    print(f'STATUS={status}')
    print(f'REPORT_PATH={report_path}')
    print(f'STATE_PATH={state_path}')
    print(f'NORMALIZED_SHA256={current_hash}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

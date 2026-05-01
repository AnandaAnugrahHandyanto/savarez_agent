#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate local QMT intraday sync bundle after pulling reports from VM.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


REQUIRED_ROOT_FILES = [
    'intraday_refresh_last.json',
    'status_panel.txt',
]

REQUIRED_REPORT_FILES = [
    'intraday_refresh_report.txt',
    'intraday_timeline_report.txt',
    'intraday_state_matrix_report.txt',
]


def validate_sync_bundle(*, sync_root: Path, date: str) -> dict:
    sync_root = Path(sync_root)
    report_dir = sync_root / 'reports' / date
    missing: list[str] = []

    for name in REQUIRED_ROOT_FILES:
        if not (sync_root / name).exists():
            missing.append(name)
    for name in REQUIRED_REPORT_FILES:
        if not (report_dir / name).exists():
            missing.append(f'reports/{date}/{name}')

    status_path = sync_root / 'intraday_refresh_last.json'
    intraday_status_ok = False
    tag = None
    if status_path.exists():
        data = json.loads(status_path.read_text(encoding='utf-8-sig', errors='replace'))
        intraday_status_ok = bool(data.get('ok', False))
        tag = data.get('tag')

    status_panel_path = sync_root / 'status_panel.txt'
    status_panel_present = status_panel_path.exists() and status_panel_path.stat().st_size > 0

    ok = not missing and intraday_status_ok and status_panel_present
    return {
        'ok': ok,
        'date': date,
        'sync_root': str(sync_root),
        'report_dir': str(report_dir),
        'missing': missing,
        'intraday_status_ok': intraday_status_ok,
        'status_panel_present': status_panel_present,
        'tag': tag,
    }


def render_validation(result: dict) -> str:
    lines = ['# QMT 盘中同步验收', '']
    lines.append(f"- 日期：{result['date']}")
    lines.append(f"- 总体结论：{'PASS' if result['ok'] else 'FAIL'}")
    lines.append(f"- intraday_refresh_last.json：{'OK' if result['intraday_status_ok'] else 'FAIL'}")
    lines.append(f"- status_panel.txt：{'OK' if result['status_panel_present'] else 'FAIL'}")
    if result.get('tag'):
        lines.append(f"- 最新标签：{result['tag']}")
    if result['missing']:
        lines.append('- 缺失文件：' + '；'.join(result['missing']))
    else:
        lines.append('- 缺失文件：无')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now().strftime('%Y%m%d'))
    parser.add_argument('--sync-root', default=str(Path('qmt_sync').resolve()))
    parser.add_argument('--out')
    args = parser.parse_args()

    result = validate_sync_bundle(sync_root=Path(args.sync_root), date=args.date)
    text = render_validation(result)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()

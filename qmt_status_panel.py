#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总 QMT 各自动任务最近状态，输出一个统一状态面板。
"""

import argparse
import json
from pathlib import Path

STATUS_FILES = [
    'auction_export_last.json',
    'daily_report_last.json',
    'intraday_refresh_last.json',
    'end_of_day_timeline_last.json',
]


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8-sig', errors='replace'))


def summarize(base_dir: Path) -> str:
    lines = ['# QMT 自动化状态面板', '']
    for name in STATUS_FILES:
        data = load_json(base_dir / name)
        if not data:
            lines.append(f'- {name}: missing')
            continue
        status = 'OK' if data.get('ok', False) else 'FAIL'
        ts = data.get('ts', '-')
        extra = []
        if 'tag' in data:
            extra.append(f"tag={data['tag']}")
        if 'report_dir' in data:
            extra.append(f"report_dir={data['report_dir']}")
        if 'error' in data:
            extra.append(f"error={data['error']}")
        lines.append(f"- {name}: {status} @ {ts}" + (f" | {' ; '.join(extra)}" if extra else ''))
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('base_dir')
    parser.add_argument('--out')
    args = parser.parse_args()

    text = summarize(Path(args.base_dir))
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()

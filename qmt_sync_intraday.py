#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync QMT intraday reports and status files from Windows VM to local Hermes workspace.
"""

import argparse
import hashlib
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable


RunFn = Callable[[list[str]], None]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scp_file(*, host: str, user: str, password: str, remote_path: str, local_path: Path, run_fn: RunFn) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    run_fn([
        'sshpass', '-p', password, 'scp', '-o', 'StrictHostKeyChecking=no',
        f'{user}@{host}:{remote_path}', str(local_path),
    ])


def sync_intraday_bundle(
    *,
    host: str,
    user: str,
    password: str,
    date: str,
    out_dir: Path,
    sync_root: Path,
    run_fn: RunFn = run,
    sync_snapshots: bool = True,
) -> dict:
    out_dir = Path(out_dir)
    sync_root = Path(sync_root)
    report_dir = out_dir / date
    report_dir.mkdir(parents=True, exist_ok=True)
    sync_root.mkdir(parents=True, exist_ok=True)

    remote_base = f"/{'C:'}/Users/{user}/Desktop/qmt_runtime"
    
    # 先同步盘中快照文件（从 exports 目录）。测试可显式关闭通配 scp，
    # 避免用 run_fn 身份判断真实/模拟执行导致包装 runner 被误判。
    remote_export_dir = f'{remote_base}/exports/{date}'
    try:
        if sync_snapshots:
            run_fn([
                'sshpass', '-p', password, 'scp', '-o', 'StrictHostKeyChecking=no',
                f'{user}@{host}:{remote_export_dir}/auction_candidates_main_board_non_st_*.json',
                str(report_dir) + '/',
            ])
    except subprocess.CalledProcessError:
        pass  # 快照文件可能还不存在，不阻塞后续同步
    
    plan = [
        {
            'key': 'intraday_status',
            'remote_candidates': [f'{remote_base}/intraday_refresh_last.json'],
            'local': sync_root / 'intraday_refresh_last.json',
        },
        {
            'key': 'status_panel',
            'remote_candidates': [f'{remote_base}/reports/status_panel.txt'],
            'local': sync_root / 'status_panel.txt',
        },
        {
            'key': 'intraday_refresh_report',
            'remote_candidates': [f'{remote_base}/reports/{date}/intraday_refresh_report.txt'],
            'local': report_dir / 'intraday_refresh_report.txt',
        },
        {
            'key': 'intraday_timeline_report',
            'remote_candidates': [f'{remote_base}/reports/{date}/intraday_timeline_report.txt'],
            'local': report_dir / 'intraday_timeline_report.txt',
        },
        {
            'key': 'intraday_state_matrix_report',
            'remote_candidates': [
                f'{remote_base}/reports/{date}/intraday_state_matrix_report.txt',
                f'{remote_base}/reports/{date}/intraday_state_matrix.txt',
            ],
            'local': report_dir / 'intraday_state_matrix_report.txt',
        },
    ]

    result = {
        'date': date,
        'sync_root': str(sync_root),
        'report_dir': str(report_dir),
    }
    for item in plan:
        old_hash = sha256_text(item['local']) if item['local'].exists() else None
        last_error = None
        for remote_path in item['remote_candidates']:
            try:
                scp_file(
                    host=host,
                    user=user,
                    password=password,
                    remote_path=remote_path,
                    local_path=item['local'],
                    run_fn=run_fn,
                )
                result[f"{item['key']}_remote"] = remote_path
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
        else:
            raise last_error or RuntimeError(f"failed to sync {item['key']}")
        new_hash = sha256_text(item['local'])
        result[f"{item['key']}_path"] = str(item['local'])
        result[item['key']] = str(item['local'])
        result[f"{item['key']}_changed"] = old_hash != new_hash
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.2.251')
    parser.add_argument('--user', default='mac')
    parser.add_argument('--password', default=os.environ.get('QMT_VM_PASSWORD'))
    parser.add_argument('--date', default=datetime.now().strftime('%Y%m%d'))
    parser.add_argument('--out-dir', default=str(Path('qmt_sync/reports').resolve()))
    parser.add_argument('--sync-root', default=str(Path('qmt_sync').resolve()))
    args = parser.parse_args()

    if not args.password:
        parser.error('missing --password or QMT_VM_PASSWORD environment variable')

    result = sync_intraday_bundle(
        host=args.host,
        user=args.user,
        password=args.password,
        date=args.date,
        out_dir=Path(args.out_dir),
        sync_root=Path(args.sync_root),
    )
    for key, value in result.items():
        print(f'{key.upper()}={value}')


if __name__ == '__main__':
    main()

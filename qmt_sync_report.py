#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync daily QMT report from Windows VM to local Hermes workspace.
"""

import argparse
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.2.251')
    parser.add_argument('--user', default='mac')
    parser.add_argument('--password', default='123456')
    parser.add_argument('--date', default=datetime.now().strftime('%Y%m%d'))
    parser.add_argument('--out-dir', default=str(Path('qmt_sync/reports').resolve()))
    args = parser.parse_args()

    out_dir = Path(args.out_dir) / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    remote_report = f"/{'C:'}/Users/{args.user}/Desktop/qmt_runtime/reports/{args.date}/daily_report.txt"
    remote_status = f"/{'C:'}/Users/{args.user}/Desktop/qmt_runtime/daily_report_last.json"
    local_report = out_dir / 'daily_report.txt'
    local_status = out_dir / 'daily_report_last.json'

    old_report_hash = sha256_text(local_report) if local_report.exists() else None
    old_status_hash = sha256_text(local_status) if local_status.exists() else None

    run([
        'sshpass', '-p', args.password, 'scp', '-o', 'StrictHostKeyChecking=no',
        f"{args.user}@{args.host}:{remote_report}", str(local_report)
    ])
    run([
        'sshpass', '-p', args.password, 'scp', '-o', 'StrictHostKeyChecking=no',
        f"{args.user}@{args.host}:{remote_status}", str(local_status)
    ])

    new_report_hash = sha256_text(local_report)
    new_status_hash = sha256_text(local_status)
    report_changed = old_report_hash != new_report_hash
    status_changed = old_status_hash != new_status_hash

    print(str(local_report))
    print(str(local_status))
    print(f"REPORT_SHA256={new_report_hash}")
    print(f"STATUS_SHA256={new_status_hash}")
    print(f"REPORT_CHANGED={'1' if report_changed else '0'}")
    print(f"STATUS_CHANGED={'1' if status_changed else '0'}")


if __name__ == '__main__':
    main()

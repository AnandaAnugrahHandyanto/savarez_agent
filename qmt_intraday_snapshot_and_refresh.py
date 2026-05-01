#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成按当前时间戳命名的 QMT 候选池快照，并自动刷新盘中报告。

流程：
1. 复制当日主快照 auction_candidates_main_board_non_st.json
2. 落盘成 auction_candidates_main_board_non_st_HHMM.json
3. 若目录内已有至少两版快照，则生成 intraday_refresh_report.txt
4. 同时生成 intraday_timeline_report.txt / intraday_state_matrix_report.txt
5. 写入 intraday_refresh_last.json 供状态面板读取
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
import shutil
import subprocess


SNAPSHOT_GLOB = 'auction_candidates_main_board_non_st_*.json'


def find_latest_pair(directory: Path):
    files = sorted(directory.glob(SNAPSHOT_GLOB), key=lambda p: p.stat().st_mtime)
    if len(files) < 2:
        return None
    return files[-2], files[-1]


def infer_status_json(export_dir: Path) -> Path:
    return export_dir.parent.parent / 'intraday_refresh_last.json'


def write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def run_script(python_bin: str, script: Path, *args: str) -> None:
    subprocess.run([python_bin, str(script), *args], check=True)


def run_pipeline(export_dir: Path, report_dir: Path, python_bin: str = 'python', tag: str | None = None) -> dict:
    export_dir = Path(export_dir)
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    tag = tag or datetime.now().strftime('%H%M')
    status_json = infer_status_json(export_dir)
    status = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'ok': False,
        'tag': tag,
        'export_dir': str(export_dir),
        'report_dir': str(report_dir),
    }

    try:
        source = export_dir / 'auction_candidates_main_board_non_st.json'
        if not source.exists():
            raise FileNotFoundError(f'missing source snapshot: {source}')

        tagged = export_dir / f'auction_candidates_main_board_non_st_{tag}.json'
        shutil.copy2(source, tagged)
        status['snapshot_path'] = str(tagged)

        pair = find_latest_pair(export_dir)
        if not pair:
            status['ok'] = True
            status['refresh_skipped'] = 'not_enough_snapshots'
            write_status(status_json, status)
            return status

        prev_path, curr_path = pair
        status['latest_pair'] = [str(prev_path), str(curr_path)]

        base = Path(__file__).resolve().parent
        refresh_out = report_dir / 'intraday_refresh_report.txt'
        timeline_out = report_dir / 'intraday_timeline_report.txt'
        matrix_out = report_dir / 'intraday_state_matrix_report.txt'

        run_script(python_bin, base / 'qmt_intraday_refresh.py', str(prev_path), str(curr_path), '--out', str(refresh_out))
        run_script(python_bin, base / 'qmt_intraday_timeline.py', str(export_dir), '--out', str(timeline_out))
        run_script(python_bin, base / 'qmt_intraday_state_matrix.py', str(export_dir), '--out', str(matrix_out))

        status.update({
            'ok': True,
            'refresh_report': str(refresh_out),
            'timeline_report': str(timeline_out),
            'matrix_report': str(matrix_out),
        })
        write_status(status_json, status)
        return status
    except Exception as exc:
        status['error'] = str(exc)
        write_status(status_json, status)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('export_dir')
    parser.add_argument('report_dir')
    parser.add_argument('--python-bin', default='python')
    parser.add_argument('--tag', default=datetime.now().strftime('%H%M'))
    args = parser.parse_args()

    status = run_pipeline(Path(args.export_dir), Path(args.report_dir), python_bin=args.python_bin, tag=args.tag)
    print(f"snapshot={status['snapshot_path']}")
    if status.get('refresh_skipped'):
        print(f"intraday=skipped:{status['refresh_skipped']}")
        return
    print(f"intraday={status['refresh_report']}")
    print(f"timeline={status['timeline_report']}")
    print(f"matrix={status['matrix_report']}")


if __name__ == '__main__':
    main()

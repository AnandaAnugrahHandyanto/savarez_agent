#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动比较同一目录下最新两版 QMT 候选池 JSON，生成盘中刷新报告。
"""

import argparse
from pathlib import Path

from qmt_intraday_refresh import load_payload, render_intraday
from qmt_candidate_ranker import score_payload


def find_latest_pair(directory: Path) -> tuple[Path, Path]:
    files = sorted(directory.glob("auction_candidates_main_board_non_st*.json"), key=lambda p: p.stat().st_mtime)
    if len(files) < 2:
        raise SystemExit(f"not enough snapshots in {directory}")
    return files[-2], files[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot_dir")
    parser.add_argument("--out")
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    prev_path, curr_path = find_latest_pair(snapshot_dir)
    prev_result = score_payload(load_payload(prev_path))
    curr_result = score_payload(load_payload(curr_path))
    report = render_intraday(prev_result, curr_result, str(prev_path), str(curr_path))

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

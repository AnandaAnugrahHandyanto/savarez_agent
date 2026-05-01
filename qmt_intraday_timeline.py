#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总同一目录下所有盘中快照，输出全日轨迹报告。
"""

import argparse
import json
import re
from pathlib import Path

from qmt_candidate_ranker import score_payload

SNAPSHOT_RE = re.compile(r"auction_candidates_main_board_non_st_(\d{4})\.json$")


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8', errors='replace'))


def collect_snapshots(directory: Path):
    items = []
    for path in sorted(directory.glob('auction_candidates_main_board_non_st_*.json')):
        m = SNAPSHOT_RE.search(path.name)
        if not m:
            continue
        tag = m.group(1)
        result = score_payload(load_payload(path))
        items.append((tag, path, result))
    return items


def best_label(result: dict) -> str:
    if result['primary']:
        x = result['primary'][0]
        return f"主攻 {x['code']} {x['name']} / {x['semantics']['trade_theme']}"
    if result['backup']:
        x = result['backup'][0]
        return f"备选 {x['code']} {x['name']} / {x['semantics']['trade_theme']}"
    if result['avoid']:
        x = result['avoid'][0]
        return f"回避 {x['code']} {x['name']} / {x['semantics']['trade_theme']}"
    return '无有效候选'


def build_timeline_metrics(items) -> dict:
    labels = [best_label(result) for _, _, result in items]
    switch_count = 0
    prev = None
    for label in labels:
        if prev is not None and label != prev:
            switch_count += 1
        prev = label
    leader_codes = []
    for _, _, result in items:
        codes = (result.get('intraday_dynamics') or {}).get('leader_codes') or []
        leader_codes.append(tuple(codes[:1]))
    leader_switch_count = 0
    prev_code = None
    for code_tuple in leader_codes:
        current = code_tuple[0] if code_tuple else None
        if prev_code is not None and current != prev_code:
            leader_switch_count += 1
        prev_code = current
    stable_focus = len(set(code for code_tuple in leader_codes for code in code_tuple if code)) == 1 if leader_codes else False
    stability_score = max(0.0, round(1.0 - leader_switch_count / max(len(items) - 1, 1), 4)) if items else 0.0
    return {
        'best_label_switch_count': switch_count,
        'leader_switch_count': leader_switch_count,
        'stable_focus': stable_focus,
        'stability_score': stability_score,
    }


def render_timeline(items) -> str:
    lines = ['# QMT 全日盘中轨迹汇总', '']
    metrics = build_timeline_metrics(items)
    lines.append(f'- 快照数量：{len(items)}')
    lines.append(f"- 主轴稳定性：{metrics['stability_score']:.2f} / 最强切换={metrics['best_label_switch_count']}次 / 焦点切换={metrics['leader_switch_count']}次")
    lines.append('')
    lines.append('## 一、时间轴')
    for tag, path, result in items:
        lines.append(f'- {tag} | 环境={result["environment"]} | {best_label(result)}')
    lines.append('')

    lines.append('## 二、最强候选演变')
    prev_best = None
    for tag, path, result in items:
        current = best_label(result)
        if current != prev_best:
            lines.append(f'- {tag}：{current}')
        prev_best = current
    lines.append('')

    lines.append('## 三、尾盘结论')
    final = items[-1][2]
    lines.append(f'- 尾盘环境：{final["environment"]}')
    lines.append(f'- 尾盘最强：{best_label(final)}')
    if final['backup']:
        top = final['backup'][0]
        lines.append(f'- 尾盘动作建议：继续备选观察，关注 {top["code"]} {top["name"]} 承接变化。')
    elif final['primary']:
        top = final['primary'][0]
        lines.append(f'- 尾盘动作建议：维持唯一主攻 {top["code"]} {top["name"]}。')
    else:
        lines.append('- 尾盘动作建议：继续回避/空仓。')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot_dir')
    parser.add_argument('--out')
    args = parser.parse_args()

    items = collect_snapshots(Path(args.snapshot_dir))
    if not items:
        raise SystemExit('no intraday snapshots found')
    report = render_timeline(items)
    if args.out:
        Path(args.out).write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()

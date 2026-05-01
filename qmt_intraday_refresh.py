#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘中二次刷新版 QMT 选股报告。
"""

import argparse
import json
from pathlib import Path

from qmt_candidate_ranker import score_payload, summarize_reason_tags
from qmt_intraday_state_matrix import (
    build_latest_focus_line,
    build_minimal_summary,
    build_transition_window,
    count_flow_events,
    result_row_map,
)


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def best_entry(result: dict):
    if result["primary"]:
        return result["primary"][0]
    if result["backup"]:
        return result["backup"][0]
    if result["observe"]:
        return result["observe"][0]
    if result["avoid"]:
        return result["avoid"][0]
    return None


def summarize_changes(prev: dict, curr: dict) -> list[str]:
    lines: list[str] = []
    prev_map = {x["code"]: x for group in ("primary", "backup", "observe", "avoid") for x in prev[group]}
    curr_map = {x["code"]: x for group in ("primary", "backup", "observe", "avoid") for x in curr[group]}
    interesting = sorted(set(prev_map) | set(curr_map))
    for code in interesting:
        p = prev_map.get(code)
        c = curr_map.get(code)
        if not p or not c:
            continue
        if p["final_action"] != c["final_action"] or p["semantics"]["chain_role"] != c["semantics"]["chain_role"]:
            lines.append(f"- {code} {c['name']}：{p['final_action']}/{p['semantics']['chain_role']} → {c['final_action']}/{c['semantics']['chain_role']}")
        elif p["total_score"] != c["total_score"]:
            lines.append(f"- {code} {c['name']}：总分 {p['total_score']} → {c['total_score']}")
    return lines


def intraday_action_text(curr_result: dict, curr_best: dict | None) -> str:
    actionable = curr_result.get('actionable_buckets', {})
    if actionable.get('actionable_primary'):
        return '当前可执行主攻'
    if curr_result['primary']:
        return '当前盘面最强，但不默认可买'
    if curr_result['backup'] and curr_best:
        return '当前无主攻，最强备选'
    return '当前无主攻，继续回避/空仓'


def intraday_best_text(curr_best: dict | None) -> str:
    if not curr_best:
        return '无'
    return f"{curr_best.get('code')} {curr_best.get('name')} / {curr_best.get('final_action') or curr_best.get('action_label') or '未知'}"


def append_theme_diagnosis(lines: list[str], row: dict, prefix: str = "- ") -> None:
    context = row.get("stock_theme_context") or {}
    semantics = row.get("semantics") or {}
    industry_anchor = context.get("industry_signal_themes") or []
    primary_themes = context.get("primary_signal_themes") or []
    theme_hits = semantics.get("theme_hits") or []
    trade_theme = semantics.get("trade_theme") or row.get("theme") or "待补"
    source_label = semantics.get("theme_source_label") or "未知来源"
    trade_theme_reason = semantics.get("trade_theme_reason") or "待补"

    if industry_anchor:
        lines.append(f"{prefix}行业题材锚点：{'、'.join(industry_anchor[:6])}")
    if primary_themes:
        lines.append(f"{prefix}本地题材库主线：{'、'.join(primary_themes[:6])}")
    lines.append(
        f"{prefix}最终交易题材判定：{trade_theme}（优先依据={source_label}；命中链路={('、'.join(theme_hits[:6]) or '无')}；原因={trade_theme_reason}）"
    )


def format_action_template(item: dict) -> str:
    tag_text = summarize_reason_tags(item.get('action_reason_tags'))
    return (
        f"{item.get('code')} {item.get('name')}（标签={tag_text}；原因={item.get('action_reason') or '待补'}；"
        f"计划={item.get('action_plan') or '待补'}）"
    )


def render_intraday(prev_result: dict, curr_result: dict, prev_path: str, curr_path: str) -> str:
    lines: list[str] = []
    lines.append("# QMT 盘中二次刷新报告")
    lines.append("")
    lines.append(f"- 上一版：{prev_path}")
    lines.append(f"- 当前版：{curr_path}")
    lines.append(f"- 当前环境：{curr_result['environment']}")
    lines.append("")

    curr_best = best_entry(curr_result)
    actionable = curr_result.get('actionable_buckets', {})
    qmt_realtime = curr_result.get('qmt_realtime_context') or curr_result.get('market_map', {}).get('qmt_realtime') or {}
    intraday_dynamics = curr_result.get('intraday_dynamics') or curr_result.get('market_map', {}).get('intraday_dynamics') or {}
    changes = summarize_changes(prev_result, curr_result)
    transition_events, _ = build_transition_window(result_row_map(prev_result), result_row_map(curr_result), 'latest')
    lines.extend(
        build_minimal_summary(
            '## 零、最新窗口变化',
            intraday_action_text(curr_result, curr_best),
            intraday_best_text(curr_best),
            count_flow_events(transition_events),
            build_latest_focus_line(transition_events, fallback=changes),
        )
    )
    lines.append("")
    if actionable.get('actionable_primary'):
        best = actionable['actionable_primary'][0]
        lines.append(f"> 当前可执行主攻：{best['code']} {best['name']}（{best.get('theme')}）")
    elif curr_result["primary"]:
        lines.append(f"> 当前盘面最强：{curr_result['primary'][0]['code']} {curr_result['primary'][0]['name']}，但不默认可买。")
    elif curr_result["backup"]:
        lines.append(f"> 当前无主攻，最强备选：{curr_best['code']} {curr_best['name']}（{curr_best['semantics']['trade_theme']}）")
    else:
        lines.append("> 当前无主攻，继续回避/空仓。")
    lines.append("")

    lines.append("## 一、变化")
    lines.extend(changes or ["- 关键候选无显著升级/降级变化"])
    lines.append("")

    lines.append("## 二、当前最强候选")
    if qmt_realtime:
        lines.append(
            f"- QMT实时结构：候选={qmt_realtime.get('candidate_snapshot_count', 0)}只，"
            f"竞价承接达标={qmt_realtime.get('auction_strength_count', 0)}只，"
            f"炸板={qmt_realtime.get('blowup_count', 0)}只，"
            f"最高板={qmt_realtime.get('highest_board', 0)}板"
        )
    if intraday_dynamics.get('leader_codes'):
        lines.append("- 主轴焦点：" + "、".join(intraday_dynamics['leader_codes']))
    if intraday_dynamics.get('upgrade_watch'):
        lines.append("- 升级观察：" + "；".join(f"{x['code']} {x['name']}" for x in intraday_dynamics['upgrade_watch']))
    if intraday_dynamics.get('downgrade_watch'):
        lines.append("- 降级观察：" + "；".join(f"{x['code']} {x['name']}" for x in intraday_dynamics['downgrade_watch']))
    if curr_best:
        lines.append(f"- {curr_best.get('code')} {curr_best.get('name')}：动作={curr_best.get('final_action') or curr_best.get('action_label') or '未知'}，角色={curr_best.get('semantics', {}).get('chain_role', '待补')}，题材={curr_best.get('semantics', {}).get('trade_theme', curr_best.get('theme', '待补'))}，总分={curr_best.get('total_score', 0)}")
        lines.append(f"- 指标：开盘={curr_best['metrics']['open_pct']}%，现涨幅={curr_best['metrics']['pct']}%，成交额={curr_best['metrics']['amount']}，买卖比={curr_best['metrics']['bid_ask_ratio']}")
        append_theme_diagnosis(lines, curr_best)
        if curr_best['vetoes']:
            lines.append(f"- 风险：{'、'.join(curr_best['vetoes'])}")
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 三、可执行性分层")
    lines.append("- 可执行主攻：" + ("；".join(format_action_template(x) for x in actionable.get('actionable_primary', [])) or "无"))
    lines.append("- 低吸观察：" + ("；".join(format_action_template(x) for x in actionable.get('low_absorb_watch', [])) or "无"))
    lines.append("- 禁追：" + ("；".join(format_action_template(x) for x in actionable.get('do_not_chase', [])) or "无"))
    lines.append("")

    lines.append("## 四、动作建议")
    if actionable.get('actionable_primary'):
        best_action = actionable['actionable_primary'][0]
        lines.append(f"- {best_action.get('action_plan') or '只对可执行主攻做二次观察，承接走弱立即降级。'}")
    elif actionable.get('low_absorb_watch'):
        watch = actionable['low_absorb_watch'][0]
        lines.append(f"- {watch.get('action_plan') or '当前无主攻，只保留低吸观察，不追已经封死的前排。'}")
    else:
        lines.append("- 当前继续回避，不勉强开仓。")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prev_json")
    parser.add_argument("curr_json")
    parser.add_argument("--out")
    args = parser.parse_args()

    prev_payload = load_payload(Path(args.prev_json))
    curr_payload = load_payload(Path(args.curr_json))
    prev_result = score_payload(prev_payload)
    curr_result = score_payload(curr_payload)
    report = render_intraday(prev_result, curr_result, args.prev_json, args.curr_json)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

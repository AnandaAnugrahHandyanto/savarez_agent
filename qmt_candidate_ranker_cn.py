#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a Chinese decision-oriented report from QMT-exported candidate JSON.

Output style follows the user's strategy:
- 先给判断
- 再给依据
- 明确主攻 / 备选 / 回避
"""

import argparse
import json
from pathlib import Path

from qmt_candidate_ranker import score_payload


def fmt_amount(v: float) -> str:
    if v >= 100000000:
        return f"{v / 100000000:.2f}亿"
    if v >= 10000:
        return f"{v / 10000:.2f}万"
    return str(v)


def render_report(result: dict) -> str:
    lines = []
    lines.append("状态：已完成 QMT 候选池读取、题材语义增强与打分")
    lines.append(f"结论：今日环境判定为【{result['environment']}】。")

    primary = result["primary"]
    backup = result["backup"]
    observe = result["observe"]
    avoid = result["avoid"]

    if primary:
        p = primary[0]
        lines.append(
            f"主攻：{p['code']} {p['name']}（总分{p['total_score']}，角色={p['semantics']['chain_role']}，题材={p['semantics']['trade_theme']}）"
        )
    else:
        lines.append("主攻：无")

    if backup:
        lines.append("备选：" + "；".join(
            f"{x['code']} {x['name']}（{x['total_score']}分，{x['semantics']['chain_role']}，{x['semantics']['trade_theme']}）" for x in backup
        ))
    else:
        lines.append("备选：无")

    if observe:
        lines.append("禁追观察：" + "；".join(
            f"{x['code']} {x['name']}（{x['total_score']}分，{x['semantics']['trade_theme']}）" for x in observe
        ))
    else:
        lines.append("禁追观察：无")

    lines.append("依据：")
    lines.append(f"- 涨停池数量：{result['limit_up_count']}，据此粗分为{result['environment']}")
    if result['top_trade_themes_by_amount']:
        theme_text = "；".join(f"{name}={fmt_amount(amount)}" for name, amount in result['top_trade_themes_by_amount'][:3])
        lines.append(f"- 候选池题材热度：{theme_text}")
    if result.get('market_map', {}).get('theme_cluster_heat'):
        cluster_text = "；".join(f"{name}={score:.2f}" for name, score in result['market_map']['theme_cluster_heat'][:3])
        lines.append(f"- 动态题材簇强度：{cluster_text}")
    if result.get('market_map', {}).get('theme_strength'):
        strength_text = "；".join(f"{name}={score:.2f}" for name, score in result['market_map']['theme_strength'][:3])
        lines.append(f"- IFIND代理题材强度：{strength_text}")
    if result.get('market_map', {}).get('theme_money'):
        money_text = "；".join(f"{name}={score:.2f}" for name, score in result['market_map']['theme_money'][:3])
        lines.append(f"- IFIND代理题材资金：{money_text}")
    if result.get('market_map', {}).get('theme_breadth'):
        breadth_text = "；".join(f"{name}={score:.2f}" for name, score in result['market_map']['theme_breadth'][:3])
        lines.append(f"- IFIND代理题材广度：{breadth_text}")

    intraday_best = (result.get('intraday_strongest') or [None])[0]
    thematic_best = (result.get('thematic_strongest') or [None])[0]
    best = (result.get('actionable_strongest') or [None])[0]
    if intraday_best:
        lines.append(
            f"- 盘中最强：{intraday_best['code']} {intraday_best['name']}，题材={intraday_best['semantics']['trade_theme']}，角色={intraday_best['semantics']['chain_role']}，当前动作={intraday_best['final_action']}。"
        )
    if thematic_best:
        lines.append(
            f"- 题材最强：{thematic_best['code']} {thematic_best['name']}，题材={thematic_best['semantics']['trade_theme']}，动态题材簇分={thematic_best.get('cluster_score', 0):.2f}，角色={thematic_best['semantics']['chain_role']}。"
        )
    if best:
        lines.append(
            f"- 可执行最强：{best['code']} {best['name']}，角色={best['semantics']['chain_role']}，交易题材={best['semantics']['trade_theme']}，原始标签={best['semantics']['primary_sector']}，板块内排名第{best['semantics']['sector_rank']}。"
        )
        lines.append(
            f"- 四维评分：金额={best['grades']['amount']} / 高开={best['grades']['open']} / 承接={best['grades']['bidask']} / 排序={best['grades'].get('rank', best['grades'].get('theme_rank', '-'))}；开盘{best['metrics']['open_pct']}%，现涨幅{best['metrics']['pct']}%，成交额{fmt_amount(best['metrics']['amount'])}。"
        )
        lines.append(
            f"- 题材增强：强度={best['grades'].get('theme_strength', 0):.2f} / 资金={best['grades'].get('theme_money', 0):.2f} / 广度={best['grades'].get('theme_breadth', 0):.2f}。"
        )
        if best['semantics'].get('theme_hits'):
            lines.append(f"- 题材映射依据：{'、'.join(best['semantics']['theme_hits'])}")
        if best.get('entry_reasons'):
            lines.append(f"- 入池依据：{'、'.join(best['entry_reasons'])}")
        if best.get('downgrade_reasons'):
            lines.append(f"- 未成主攻原因：{'、'.join(best['downgrade_reasons'])}")
        if best['vetoes']:
            lines.append(f"- 风险点：{'、'.join(best['vetoes'])}")
    else:
        if result.get('no_primary_reason'):
            lines.append(f"- 未出主攻原因：{result['no_primary_reason']}")

    if avoid:
        lines.append("- 回避样本：" + "；".join(
            f"{x['code']} {x['name']}（{x['semantics']['chain_role']}，题材={x['semantics']['trade_theme']}，原因：{('、'.join(x['vetoes']) or '龙头三问不足')}）" for x in avoid[:3]
        ))

    lines.append("下一步：")
    if primary:
        lines.append("- 维持唯一主攻口径，不扩散到低质量备选。")
    elif backup:
        lines.append("- 当前只保留备选观察，不给主攻仓位；若盘中承接继续增强且题材强度保持，再二次审查。")
    else:
        lines.append("- 当前无有效主攻，按回避/空仓处理。")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path")
    parser.add_argument("--json", action="store_true", help="also print raw result json")
    args = parser.parse_args()

    payload = json.loads(Path(args.json_path).read_text(encoding="utf-8", errors="replace"))
    result = score_payload(payload, payload_path=str(Path(args.json_path)))
    print(render_report(result))
    if args.json:
        print("\n--- RAW_JSON ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

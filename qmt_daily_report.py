#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a daily final report from QMT-exported candidate JSON.
"""

import argparse
import json
from pathlib import Path

from qmt_candidate_ranker import score_payload, summarize_reason_tags


def fmt_amount(v: float) -> str:
    if v >= 100000000:
        return f"{v / 100000000:.2f}亿"
    if v >= 10000:
        return f"{v / 10000:.2f}万"
    return str(v)


def fmt_optional(value, suffix: str = "") -> str:
    if value in (None, ""):
        return f"待补{suffix}" if suffix else "待补"
    return f"{value}{suffix}"


def fmt_text(value: str | None, fallback: str = "待补") -> str:
    text = str(value or "").strip()
    return text or fallback


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


def format_action_template(item: dict, *, include_theme: bool = True, include_role: bool = False, include_board: bool = False) -> str:
    bits = []
    if include_theme:
        bits.append(str(item.get('theme') or '待补'))
    if include_role and item.get('role'):
        bits.append(str(item.get('role')))
    if include_board:
        bits.append(fmt_optional(item.get('board_count'), '板'))
    prefix = '，'.join(bits)
    tag_text = summarize_reason_tags(item.get('action_reason_tags'))
    detail = f"标签={tag_text}；原因={item.get('action_reason') or '待补'}；计划={item.get('action_plan') or '待补'}"
    if prefix:
        return f"{item.get('code')} {item.get('name')}（{prefix}，{detail}）"
    return f"{item.get('code')} {item.get('name')}（{detail}）"


def render_daily(result: dict, source_path: str) -> str:
    primary = result['primary']
    backup = result['backup']
    observe = result['observe']
    avoid = result['avoid']
    market_map = result.get('market_map', {})
    sector_profiles = result.get('sector_profiles', [])
    actionable = result.get('actionable_buckets', {})
    ifind_board = result.get('ifind_board_context', {})
    qmt_realtime = result.get('qmt_realtime_context') or market_map.get('qmt_realtime') or {}
    intraday_dynamics = result.get('intraday_dynamics') or market_map.get('intraday_dynamics') or {}
    qmt_timeline_score = result.get('qmt_timeline_score') or market_map.get('qmt_timeline_score') or {}

    lines = []
    lines.append("# QMT 选股日报")
    lines.append("")
    lines.append(f"- 数据源：{source_path}")
    lines.append(f"- 市场环境：{result['environment']}")
    lines.append(f"- 涨停池数量：{result['limit_up_count']}")
    lines.append("")
    lines.append("## 一、结论")
    if actionable.get('actionable_primary'):
        best = actionable['actionable_primary'][0]
        lines.append(f"> 今日有可执行主攻：{best['code']} {best['name']}（{best.get('theme')} / {best.get('role')}）。")
    elif primary:
        p = primary[0]
        lines.append(f"> 今日盘面最强为 {p['code']} {p['name']}，但需再看可执行性，不默认可买。")
    elif backup:
        b = backup[0]
        lines.append(f"> 今日无主攻，仅保留备选观察：{b['code']} {b['name']}（{b['semantics']['trade_theme']}）。")
    elif actionable.get('low_absorb_watch'):
        obs = actionable['low_absorb_watch'][0]
        lines.append(f"> 今日无主攻，仅保留低吸观察：{obs['code']} {obs['name']}（{obs.get('theme')}）。")
    else:
        lines.append("> 今日无有效主攻，回避/空仓为标准答案。")
    lines.append("")

    lines.append("## 二、市场地图")
    if market_map.get('environment_summary'):
        lines.append(f"- 环境摘要：{market_map['environment_summary']}")

    lines.append("### 1) QMT本地竞价口径")
    if qmt_realtime:
        lines.append(
            "- QMT实时结构："
            f"快照候选={qmt_realtime.get('candidate_snapshot_count', 0)}只；"
            f"竞价承接达标={qmt_realtime.get('auction_strength_count', 0)}只；"
            f"涨停={qmt_realtime.get('limit_up_count', 0)}只；"
            f"首板={fmt_optional(qmt_realtime.get('first_board_count'), '只')}；"
            f"连板={fmt_optional(qmt_realtime.get('multi_board_count'), '只')}；"
            f"炸板={qmt_realtime.get('blowup_count', 0)}只；"
            f"封死={qmt_realtime.get('sealed_limit_up_count', 0)}只；"
            f"最高板={fmt_optional(qmt_realtime.get('highest_board'), '板')}；"
            f"可执行候选={qmt_realtime.get('actionable_candidate_count', 0)}只"
        )
    if intraday_dynamics:
        if intraday_dynamics.get('leader_codes'):
            lines.append("- QMT主轴焦点：" + "、".join(intraday_dynamics['leader_codes']))
        if intraday_dynamics.get('upgrade_watch'):
            lines.append("- 升级观察：" + "；".join(f"{x['code']} {x['name']}（{x.get('action','')}）" for x in intraday_dynamics['upgrade_watch']))
        if intraday_dynamics.get('downgrade_watch'):
            lines.append("- 降级观察：" + "；".join(f"{x['code']} {x['name']}（{x.get('action','')}）" for x in intraday_dynamics['downgrade_watch']))
    if market_map.get('top_trade_themes'):
        lines.append("- QMT候选题材热度：" + "；".join(f"{name}={fmt_amount(amount)}" for name, amount in market_map['top_trade_themes'][:5]))
    if market_map.get('top_limit_up_themes'):
        lines.append("- QMT涨停题材分布：" + "；".join(f"{name}={count}只" for name, count in market_map['top_limit_up_themes'][:5]))
    if market_map.get('top_sectors'):
        lines.append("- QMT候选池题材聚合：" + "；".join(f"{name}={fmt_amount(amount)}" for name, amount in market_map['top_sectors'][:5]))
    if qmt_timeline_score:
        lines.append(
            f"- QMT时间轴评分：{qmt_timeline_score.get('score', 0)} / 焦点数={qmt_timeline_score.get('focus_count', 0)} / 升级={qmt_timeline_score.get('upgrade_count', 0)} / 降级={qmt_timeline_score.get('downgrade_count', 0)}"
        )
    if market_map.get('reason_tag_counts'):
        lines.append("- QMT动作原因标签：" + "；".join(f"{name}={count}次" for name, count in market_map['reason_tag_counts'] if count))

    lines.append("### 2) 外部全市场口径")
    theme_leaderboard = ifind_board.get('theme_leaderboard') or {}
    if theme_leaderboard:
        first_theme = next(iter(theme_leaderboard.keys()), '')
        rows = theme_leaderboard.get(first_theme) or []
        if rows:
            lines.append("- IFIND题材前排：" + "；".join(f"{x.get('code','')} {x.get('name','')}" for x in rows[:3]))
    scope_preview = ifind_board.get('market_scope') or []
    if scope_preview:
        lines.append(f"- IFIND市场范围：已确认可获取“上证板块”成分，样本数={len(scope_preview)}")
    if ifind_board.get('industry_leads'):
        lines.append("- IFIND行业主线：" + "；".join(f"{x['industry']}={x['count']}只" for x in ifind_board['industry_leads'][:5]))
    if market_map.get('theme_strength'):
        lines.append("- IFIND代理题材强度：" + "；".join(f"{name}={score:.2f}" for name, score in market_map['theme_strength'][:5]))
    if market_map.get('theme_money'):
        lines.append("- IFIND代理题材资金：" + "；".join(f"{name}={score:.2f}" for name, score in market_map['theme_money'][:5]))
    if market_map.get('theme_breadth'):
        lines.append("- IFIND代理题材广度：" + "；".join(f"{name}={score:.2f}" for name, score in market_map['theme_breadth'][:5]))
    tushare_theme = market_map.get('tushare_theme') or {}
    if tushare_theme.get('theme_money_rank'):
        lines.append("- Tushare题材资金榜：" + "；".join(
            f"{x['theme']}={x['net_amount']:.2f}亿/龙头{x.get('lead_stock','')}" for x in tushare_theme['theme_money_rank'][:5]
        ))
    if tushare_theme.get('theme_strength_rank'):
        lines.append("- Tushare题材强度榜：" + "；".join(
            f"{x['theme']}={x['strength_score']:.2f}/龙头{x.get('lead_stock','')}" for x in tushare_theme['theme_strength_rank'][:5]
        ))
    if tushare_theme.get('hot_theme_rank'):
        lines.append("- Tushare热门题材榜：" + "；".join(
            f"{x['theme']}={x['hot_count']}次/代表{x.get('lead_stock','')}" for x in tushare_theme['hot_theme_rank'][:5]
        ))
    if tushare_theme.get('canonical_hot_theme_rank'):
        lines.append("- Tushare交叉题材热榜：" + "；".join(
            f"{x['theme']}={x['hot_count']}次/代表{x.get('lead_stock','')}" for x in tushare_theme['canonical_hot_theme_rank'][:5]
        ))
    market_sentiment = tushare_theme.get('market_sentiment') or {}
    if market_sentiment:
        lines.append(
            "- Tushare情绪结构："
            f"涨停={market_sentiment.get('limit_up_count', 0)}只；"
            f"首板={market_sentiment.get('first_board_count', 0)}只；"
            f"连板={market_sentiment.get('multi_board_count', 0)}只；"
            f"最高板={market_sentiment.get('highest_board', 0)}板"
        )
    strongest_limit_stocks = tushare_theme.get('strongest_limit_stocks') or []
    if strongest_limit_stocks:
        lines.append("- Tushare涨停焦点：" + "；".join(
            f"{x.get('name','')}({x.get('open_num', 0)}板/{x.get('lu_desc','') or '-'})" for x in strongest_limit_stocks[:3]
        ))
    lhb_focus = tushare_theme.get('lhb_focus') or []
    if lhb_focus:
        lines.append("- Tushare龙虎榜焦点：" + "；".join(
            f"{(x.get('name') or x.get('ts_code') or '未知')}=净买{x.get('net_buy', 0):.2f}" for x in lhb_focus[:3]
        ))
    stock_moneyflow_focus = tushare_theme.get('stock_moneyflow_focus') or []
    if stock_moneyflow_focus:
        lines.append("- Tushare个股资金焦点：" + "；".join(
            f"{x.get('ts_code','')}=净额{x.get('net_mf_amount', 0):.2f}" for x in stock_moneyflow_focus[:3]
        ))
    if qmt_realtime or market_sentiment:
        lines.append("- 口径提示：QMT实时结构/候选池来自本地竞价快照；Tushare情绪结构/涨停焦点来自外部全市场快照，两者不是同一口径，不能直接逐项对表。")
    lines.append("")

    lines.append("## 三、板块画像")
    if sector_profiles:
        for profile in sector_profiles[:5]:
            leader = f"{profile['leader_code']} {profile['leader_name']}" if profile['leader_code'] else "无"
            fronts = "；".join(
                f"{x['code']} {x['name']}({fmt_optional(x.get('board_count'), '板')}/{fmt_text(x.get('streak'))}/{fmt_text(x.get('limit_up_type'), '-')}/{fmt_text(x.get('limit_up_time'), '-')})"
                for x in profile['front_rows'][:3]
            ) or "无"
            blowups = "；".join(
                f"{x['code']} {x['name']}({x.get('limit_up_type', '')}/{x.get('pct', 0)}%)"
                for x in profile['blowups'][:3]
            ) or "无"
            lines.append(f"- {profile['theme']}：强度={profile['strength']}，成员={profile['member_count']}，涨停={profile['limit_up_count']}，最高板={fmt_optional(profile['highest_board'], '板')}，龙头={leader}，题材强度分={profile.get('strength_score', 0):.2f}，题材资金分={profile.get('money_score', 0):.2f}，题材广度分={profile.get('breadth_score', 0):.2f}")
            candidate_meta = (ifind_board.get('theme_candidates') or {}).get(profile['theme'], {})
            if candidate_meta:
                lines.append(f"  IFIND题材确认：success={candidate_meta.get('success')}，命中成分={candidate_meta.get('member_count', 0)}")
            leaderboard = profile.get('ifind_leaderboard') or []
            if leaderboard:
                lines.append("  IFIND前排：" + "；".join(f"{x.get('code','')} {x.get('name','')}" for x in leaderboard[:3]))
            lines.append(f"  前排：{fronts}")
            lines.append(f"  炸板/掉队：{blowups}")
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 四、个股执行分层")
    lines.append("- 主攻：" + ("；".join(f"{x['code']} {x['name']}（{x['total_score']}分，{x['semantics']['chain_role']}，{x['semantics']['trade_theme']}，{fmt_optional(x.get('board_count'), '板')}，{x.get('action_plan', '按主攻节奏执行')}）" for x in primary) if primary else "无"))
    lines.append("- 备选：" + ("；".join(f"{x['code']} {x['name']}（{x['total_score']}分，{x['semantics']['chain_role']}，{x['semantics']['trade_theme']}，{fmt_optional(x.get('board_count'), '板')}，{x.get('action_plan', '继续确认')}）" for x in backup) if backup else "无"))
    lines.append("- 低吸观察：" + ("；".join(format_action_template(x, include_theme=True, include_role=True) for x in actionable.get('low_absorb_watch', [])) or "无"))
    lines.append("- 禁追：" + ("；".join(format_action_template(x, include_theme=True, include_board=True) for x in actionable.get('do_not_chase', [])) or "无"))
    lines.append("- 回避样本：" + ("；".join(f"{x['code']} {x['name']}（{x['semantics']['chain_role']}，{x['semantics']['trade_theme']}，{x.get('action_plan', '直接回避')}）" for x in avoid[:3]) if avoid else "无"))
    lines.append("")

    lines.append("## 五、依据")
    best = primary[0] if primary else (backup[0] if backup else (observe[0] if observe else (avoid[0] if avoid else None)))
    if best:
        lines.append(f"- 当前最强候选：{best['code']} {best['name']}，交易题材={best['semantics']['trade_theme']}，角色={best['semantics']['chain_role']}，原始标签={best['semantics']['primary_sector']}，板块内排名第{best['semantics']['sector_rank']}。")
        lines.append(f"- 四维评分：金额={best['grades']['amount']} / 高开={best['grades']['open']} / 承接={best['grades']['bidask']} / 排序={best['grades'].get('rank', best['grades'].get('theme_rank', '-'))}；开盘 {best['metrics']['open_pct']}%，现涨幅 {best['metrics']['pct']}%，成交额 {fmt_amount(best['metrics']['amount'])}。")
        lines.append(f"- 题材增强：强度={best['grades'].get('theme_strength', 0):.2f} / 资金={best['grades'].get('theme_money', 0):.2f} / 广度={best['grades'].get('theme_breadth', 0):.2f}。")
        lines.append(f"- IFIND板块一致性：分数={best['grades'].get('board_alignment', 0):.2f} / 行业={best['semantics'].get('ifind_industry_name', '') or '未知'} / 上证范围={'是' if best['semantics'].get('ifind_is_sse_scope') else '否'} / 题材命中={'是' if best['semantics'].get('ifind_theme_match') else '否'}。")
        lines.append(f"- 连板/形态：{fmt_optional(best.get('board_count'), '板')}，{fmt_text(best.get('streak'))}，{fmt_text(best.get('limit_up_type'), '待补')}，时间={fmt_text(best.get('limit_up_time'), '-')}")
        if best['semantics'].get('theme_hits'):
            lines.append(f"- 题材映射依据：{'、'.join(best['semantics']['theme_hits'])}")
        append_theme_diagnosis(lines, best)
        if best.get('stock_theme_tags'):
            lines.append(f"- 本地题材库高置信候选：{'、'.join(best['stock_theme_tags'][:6])}")
        if best['vetoes']:
            lines.append(f"- 风险点：{'、'.join(best['vetoes'])}")
    if avoid:
        lines.append("- 回避理由样本：" + "；".join(f"{x['code']} {x['name']}（题材={x['semantics']['trade_theme']}；原因={x.get('action_reason') or ('、'.join(x['vetoes']) or '龙头三问不足')}；计划={x.get('action_plan') or '直接回避'}）" for x in avoid[:3]))
    missing_core = ifind_board.get('missing_core_candidates') or []
    if missing_core:
        lines.append("- IFIND候选遗漏提示：" + "；".join(
            f"{x['code']} {x['name']}（题材={x['theme']}，可对照成分样本：" + ", ".join(f"{m.get('股票代码','')} {m.get('股票简称','')}" for m in x.get('hint_members', [])[:2]) + "）"
            for x in missing_core[:3]
        ))
    lines.append("")

    lines.append("## 六、次日观察池")
    next_watch = actionable.get('low_absorb_watch', [])[:3] + actionable.get('do_not_chase', [])[:2]
    if next_watch:
        lines.append("- " + "；".join(f"{x['code']} {x['name']}（{x.get('theme')}，{fmt_optional(x.get('board_count'), '板')}，{fmt_text(x.get('limit_up_type'), '待补')}）" for x in next_watch))
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 七、风控提醒")
    lines.append("- 没有可执行主攻，就没有重仓资格。")
    lines.append("- 盘面最强不等于当前可买，封死涨停默认进禁追。")
    lines.append("- 若只是因为怕错过想出手，直接降级处理。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('json_path')
    parser.add_argument('--out')
    args = parser.parse_args()

    path = Path(args.json_path)
    payload = json.loads(path.read_text(encoding='utf-8', errors='replace'))
    result = score_payload(payload, payload_path=str(path))
    report = render_daily(result, str(path))

    if args.out:
        Path(args.out).write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()

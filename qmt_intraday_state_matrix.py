#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于同日多快照，输出核心票全天状态迁移表，并给出自动动作决策。
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from qmt_candidate_ranker import score_payload, summarize_reason_tags

SNAPSHOT_RE = re.compile(r"auction_candidates_main_board_non_st_(\d{4})\.json$")
ACTION_RANK = {"回避": 0, "禁追观察": 1, "备选": 2, "主攻": 3}
FLOW_RANK = {"承接转弱": 0, "承接转强": 1, "炸板": 2, "封单": 3, "回封": 4}


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
        rows = {x['code']: x for group in ('primary', 'backup', 'observe', 'avoid') for x in result[group]}
        items.append((tag, rows))
    return items


def row_sort_key(row: dict):
    return (
        ACTION_RANK.get(row.get('final_action', '回避'), -1),
        float(row.get('total_score', 0) or 0),
        float(row.get('cluster_score', 0) or 0),
        int(row.get('dragon_yes_count', 0) or 0),
    )


def best_row(rows: dict):
    if not rows:
        return None
    return max(rows.values(), key=row_sort_key)


def action_name(rank: int) -> str:
    for name, value in ACTION_RANK.items():
        if value == rank:
            return name
    return '回避'


def normalize_snapshot_items(items) -> list[dict]:
    normalized = []
    for item in items:
        if isinstance(item, dict):
            tag = item.get('tag', '')
            rows = item.get('rows') or item.get('scored_rows') or item.get('scored') or {}
        else:
            tag, rows = item
        normalized.append({'tag': tag, 'rows': rows or {}})
    return normalized


def metric_value(row: dict | None, key: str, default: float = 0.0) -> float:
    if not row:
        return default
    metrics = row.get('metrics', {}) or {}
    value = metrics.get(key, row.get(key, default))
    if value in (None, ''):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def row_pct(row: dict | None) -> float:
    return metric_value(row, 'pct', 0.0)


def row_ratio(row: dict | None) -> float:
    return metric_value(row, 'bid_ask_ratio', 0.0)


def row_ask1_vol(row: dict | None) -> float:
    return metric_value(row, 'ask1_vol', 0.0)


def is_sealed_limit(row: dict | None) -> bool:
    return bool(row) and row_pct(row) >= 9.8 and row_ask1_vol(row) == 0


def is_blowup(row: dict | None) -> bool:
    if not row:
        return False
    return str(row.get('limit_up_type', '')).strip() == '炸板'


def support_strengthened(prev_row: dict | None, curr_row: dict | None) -> bool:
    if not prev_row or not curr_row or is_sealed_limit(curr_row):
        return False
    prev_ratio = row_ratio(prev_row)
    curr_ratio = row_ratio(curr_row)
    return curr_ratio >= 1.8 and (prev_ratio < 1.1 or curr_ratio - prev_ratio >= 1.0)


def support_weakened(prev_row: dict | None, curr_row: dict | None) -> bool:
    if not prev_row or not curr_row or is_sealed_limit(curr_row):
        return False
    prev_ratio = row_ratio(prev_row)
    curr_ratio = row_ratio(curr_row)
    return prev_ratio >= 1.8 and (curr_ratio < 1.0 or prev_ratio - curr_ratio >= 1.0)


def flow_event(event_type: str, tag: str, row: dict, prev_row: dict | None = None) -> dict:
    return {
        'type': event_type,
        'tag': tag,
        'code': row.get('code', ''),
        'name': row.get('name', ''),
        'action': row.get('final_action', '回避'),
        'theme': row.get('semantics', {}).get('trade_theme', ''),
        'score': float(row.get('total_score', 0) or 0),
        'pct': row_pct(row),
        'prev_pct': row_pct(prev_row) if prev_row else None,
        'ratio': row_ratio(row),
        'prev_ratio': row_ratio(prev_row) if prev_row else None,
        'limit_up_time': row.get('limit_up_time', ''),
    }


def event_sort_key(event: dict):
    return (
        FLOW_RANK.get(event.get('type', ''), -1),
        ACTION_RANK.get(event.get('action', '回避'), -1),
        float(event.get('score', 0) or 0),
        float(event.get('pct', 0) or 0),
        float(event.get('ratio', 0) or 0),
    )


def blank_flow_counts() -> dict:
    return {'封单': 0, '回封': 0, '炸板': 0, '承接转强': 0, '承接转弱': 0}


def count_flow_events(events: list[dict]) -> dict:
    counts = blank_flow_counts()
    for event in events:
        if event.get('type') in counts:
            counts[event['type']] += 1
    return counts


def result_row_map(result: dict) -> dict:
    rows = result.get('strategy_candidate_pool') or []
    if rows:
        return {row.get('code'): row for row in rows if row.get('code')}
    mapped = {}
    for group in ('primary', 'backup', 'observe', 'avoid'):
        for row in result.get(group, []) or []:
            code = row.get('code')
            if code:
                mapped[code] = row
    return mapped


def build_transition_window(prev_rows: dict, curr_rows: dict, tag: str, seen_sealed: dict | None = None) -> tuple[list[dict], dict]:
    seen_sealed = dict(seen_sealed or {})
    transition_events: list[dict] = []
    for code in sorted(set(prev_rows) | set(curr_rows)):
        prev_row = prev_rows.get(code)
        curr_row = curr_rows.get(code)
        if not curr_row:
            continue
        prev_sealed = is_sealed_limit(prev_row)
        curr_sealed = is_sealed_limit(curr_row)
        prev_blowup = is_blowup(prev_row)
        curr_blowup = is_blowup(curr_row) or (prev_sealed and not curr_sealed and row_pct(curr_row) < 9.8)
        had_sealed = seen_sealed.get(code, prev_sealed)

        if curr_sealed and not prev_sealed:
            event_type = '回封' if had_sealed or prev_blowup else '封单'
            transition_events.append(flow_event(event_type, tag, curr_row, prev_row))
        if curr_blowup and (prev_sealed or not prev_blowup):
            transition_events.append(flow_event('炸板', tag, curr_row, prev_row))
        if not curr_blowup and not curr_sealed:
            if support_strengthened(prev_row, curr_row):
                transition_events.append(flow_event('承接转强', tag, curr_row, prev_row))
            elif support_weakened(prev_row, curr_row):
                transition_events.append(flow_event('承接转弱', tag, curr_row, prev_row))

        seen_sealed[code] = had_sealed or curr_sealed

    transition_events.sort(key=event_sort_key, reverse=True)
    return transition_events, seen_sealed


def build_flow_summary(items) -> dict:
    normalized_items = normalize_snapshot_items(items)
    if len(normalized_items) < 2:
        return {
            'latest_tag': normalized_items[-1]['tag'] if normalized_items else '',
            'latest_events': [],
            'latest_counts': blank_flow_counts(),
            'total_counts': blank_flow_counts(),
        }

    seen_sealed = {
        code: is_sealed_limit(row)
        for code, row in normalized_items[0]['rows'].items()
    }
    all_events: list[dict] = []
    latest_events: list[dict] = []

    for idx in range(1, len(normalized_items)):
        prev_rows = normalized_items[idx - 1]['rows']
        curr_rows = normalized_items[idx]['rows']
        curr_tag = normalized_items[idx]['tag']
        transition_events, seen_sealed = build_transition_window(prev_rows, curr_rows, curr_tag, seen_sealed)
        all_events.extend(transition_events)
        latest_events = transition_events

    return {
        'latest_tag': normalized_items[-1]['tag'],
        'latest_events': latest_events,
        'latest_counts': count_flow_events(latest_events),
        'total_counts': count_flow_events(all_events),
    }


def fmt_event_number(value) -> str:
    if value in (None, ''):
        return '-'
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f'{value:.2f}'.rstrip('0').rstrip('.')


def format_event_brief(event: dict) -> str:
    prefix = f"{event['code']} {event['name']} {event['type']}"
    if event['type'] in {'封单', '回封'}:
        extras = [f"涨幅 {fmt_event_number(event.get('pct'))}%", f"承接比 {fmt_event_number(event.get('ratio'))}"]
        if event.get('limit_up_time'):
            extras.append(f"封板时间 {event['limit_up_time']}")
        return prefix + '（' + '，'.join(extras) + '）'
    if event['type'] == '炸板':
        return prefix + '（' + f"涨幅 {fmt_event_number(event.get('prev_pct'))}%→{fmt_event_number(event.get('pct'))}%，承接比 {fmt_event_number(event.get('prev_ratio'))}→{fmt_event_number(event.get('ratio'))}" + '）'
    return prefix + '（' + f"承接比 {fmt_event_number(event.get('prev_ratio'))}→{fmt_event_number(event.get('ratio'))}，涨幅 {fmt_event_number(event.get('prev_pct'))}%→{fmt_event_number(event.get('pct'))}%" + '）'


def format_flow_counts_line(counts: dict) -> str:
    counts = counts or blank_flow_counts()
    return (
        f"封单={counts['封单']}；回封={counts['回封']}；炸板={counts['炸板']}；"
        f"承接转强={counts['承接转强']}；承接转弱={counts['承接转弱']}"
    )


def build_latest_focus_line(events: list[dict], fallback: list[str] | None = None, limit: int = 3) -> str:
    if events:
        return '；'.join(format_event_brief(event) for event in events[:limit])
    fallback = [line.lstrip('- ').strip() for line in (fallback or []) if line.strip()]
    if fallback:
        return '；'.join(fallback[:limit])
    return '无新增封单/回封/炸板/承接异动'


def build_minimal_summary(title: str, action_text: str, best_text: str, flow_counts: dict, focus_line: str) -> list[str]:
    return [
        title,
        f'- 自动动作：{action_text}',
        f'- 当前最强：{best_text}',
        f'- 最新盘中流：{format_flow_counts_line(flow_counts)}',
        f'- 最新焦点：{focus_line}',
    ]


def build_theme_diagnosis_line(row: dict | None) -> str:
    if not row:
        return '无'
    semantics = row.get('semantics', {}) or {}
    context = row.get('stock_theme_context', {}) or {}
    theme = semantics.get('trade_theme') or row.get('theme') or '待补'
    source_label = semantics.get('theme_source_label') or '未知来源'
    industry_anchor = '、'.join((context.get('industry_signal_themes') or [])[:4]) or '无'
    theme_hits = '、'.join((semantics.get('theme_hits') or [])[:4]) or '无'
    return f"{theme}（优先依据={source_label}；行业锚点={industry_anchor}；命中链路={theme_hits}）"


def build_action_template_line(row: dict | None) -> str:
    if not row:
        return '无'
    action_label = row.get('action_label') or row.get('final_action') or '未知'
    action_reason = row.get('action_reason') or '待补'
    action_plan = row.get('action_plan') or '待补'
    tag_text = summarize_reason_tags(row.get('action_reason_tags'))
    return f"{action_label}（标签={tag_text}；原因={action_reason}；计划={action_plan}）"


def build_im_summary(items, engine: dict, flow_summary: dict) -> list[str]:
    normalized_items = normalize_snapshot_items(items)
    latest_counts = flow_summary['latest_counts']
    latest_rows = normalized_items[-1]['rows'] if normalized_items else {}
    latest_best = best_row(latest_rows)
    best_text = '无'
    if engine['decision']['latest_best_code']:
        best_text = (
            f"{engine['decision']['latest_best_code']} {engine['decision']['latest_best_name']} / "
            f"{engine['decision']['latest_best_state']}"
        )
    focus_line = build_latest_focus_line(flow_summary['latest_events'])
    lines = build_minimal_summary('## IM 极简摘要', engine['decision']['action'], best_text, latest_counts, focus_line)
    if latest_best:
        lines.append(f"- 题材判定：{build_theme_diagnosis_line(latest_best)}")
        lines.append(f"- 动作模板：{build_action_template_line(latest_best)}")
    lines.append(f"- 最新快照：{normalized_items[-1]['tag'] if normalized_items else '-'} / 快照总数={len(normalized_items)}")
    return lines


def build_timeline_metrics(items) -> dict:
    labels = []
    leader_codes = []
    for _, rows in items:
        best = best_row(rows)
        if best:
            labels.append(f"{best['final_action']} {best['code']}")
            leader_codes.append(best['code'])
        else:
            labels.append('无有效候选')
            leader_codes.append(None)
    best_label_switch_count = sum(1 for i in range(1, len(labels)) if labels[i] != labels[i-1])
    leader_switch_count = sum(1 for i in range(1, len(leader_codes)) if leader_codes[i] != leader_codes[i-1])
    stability_score = max(0.0, round(1.0 - leader_switch_count / max(len(items) - 1, 1), 4)) if items else 0.0
    return {
        'best_label_switch_count': best_label_switch_count,
        'leader_switch_count': leader_switch_count,
        'stability_score': stability_score,
    }


def classify_delta(prev_row: dict, curr_row: dict) -> str:
    prev_rank = ACTION_RANK.get(prev_row.get('final_action', '回避'), 0)
    curr_rank = ACTION_RANK.get(curr_row.get('final_action', '回避'), 0)
    if curr_rank > prev_rank:
        return '升级'
    if curr_rank < prev_rank:
        return '降级'
    if curr_row.get('semantics', {}).get('chain_role') != prev_row.get('semantics', {}).get('chain_role'):
        return '重排'
    if float(curr_row.get('total_score', 0) or 0) != float(prev_row.get('total_score', 0) or 0):
        return '重评'
    return '稳定'


def describe_triggers(prev_row: dict, curr_row: dict) -> list[str]:
    triggers = []
    if prev_row.get('final_action') != curr_row.get('final_action'):
        triggers.append(f"动作 {prev_row.get('final_action')} → {curr_row.get('final_action')}")
    prev_role = prev_row.get('semantics', {}).get('chain_role', '')
    curr_role = curr_row.get('semantics', {}).get('chain_role', '')
    if prev_role != curr_role:
        triggers.append(f"角色 {prev_role} → {curr_role}")
    prev_score = float(prev_row.get('total_score', 0) or 0)
    curr_score = float(curr_row.get('total_score', 0) or 0)
    if curr_score != prev_score:
        triggers.append(f"总分 {prev_score:g} → {curr_score:g}")
    prev_dragon = int(prev_row.get('dragon_yes_count', 0) or 0)
    curr_dragon = int(curr_row.get('dragon_yes_count', 0) or 0)
    if curr_dragon != prev_dragon:
        triggers.append(f"龙头三问 {prev_dragon}/3 → {curr_dragon}/3")
    prev_veto = len(prev_row.get('vetoes', []) or [])
    curr_veto = len(curr_row.get('vetoes', []) or [])
    if curr_veto != prev_veto:
        triggers.append(f"veto {prev_veto} → {curr_veto}")
    prev_pct = float(prev_row.get('metrics', {}).get('pct', prev_row.get('pct', 0)) or 0)
    curr_pct = float(curr_row.get('metrics', {}).get('pct', curr_row.get('pct', 0)) or 0)
    if curr_pct != prev_pct:
        triggers.append(f"涨幅 {prev_pct:g}% → {curr_pct:g}%")
    return triggers or ['关键字段无变化']


def build_state_engine(items) -> dict:
    normalized_items = normalize_snapshot_items(items)
    timeline_items = [(item['tag'], item['rows']) for item in normalized_items]
    track = defaultdict(list)
    for tag, rows in timeline_items:
        for code, row in rows.items():
            if row.get('final_action') in ('主攻', '备选') or float(row.get('total_score', 0) or 0) >= 9:
                track[code].append((tag, row))

    per_code = []
    for code, events in sorted(track.items(), key=lambda kv: (-max(float(e[1].get('total_score', 0) or 0) for e in kv[1]), kv[0])):
        first_tag, first_row = events[0]
        last_tag, last_row = events[-1]
        changes = []
        upgrade_count = 0
        downgrade_count = 0
        reeval_count = 0
        for idx in range(1, len(events)):
            prev_tag, prev_row = events[idx - 1]
            curr_tag, curr_row = events[idx]
            delta = classify_delta(prev_row, curr_row)
            if delta == '升级':
                upgrade_count += 1
            elif delta == '降级':
                downgrade_count += 1
            elif delta in {'重排', '重评'}:
                reeval_count += 1
            changes.append({
                'from_tag': prev_tag,
                'to_tag': curr_tag,
                'delta': delta,
                'triggers': describe_triggers(prev_row, curr_row),
                'from_state': prev_row.get('final_action', '回避'),
                'to_state': curr_row.get('final_action', '回避'),
            })
        max_rank = max(ACTION_RANK.get(row.get('final_action', '回避'), 0) for _, row in events)
        summary_delta = '稳定'
        start_rank = ACTION_RANK.get(first_row.get('final_action', '回避'), 0)
        end_rank = ACTION_RANK.get(last_row.get('final_action', '回避'), 0)
        if end_rank > start_rank:
            summary_delta = '净升级'
        elif end_rank < start_rank:
            summary_delta = '净降级'
        elif upgrade_count or downgrade_count or reeval_count:
            summary_delta = '中途波动'
        per_code.append({
            'code': code,
            'name': first_row.get('name', ''),
            'start_state': first_row.get('final_action', '回避'),
            'end_state': last_row.get('final_action', '回避'),
            'max_state': action_name(max_rank),
            'summary_delta': summary_delta,
            'first_tag': first_tag,
            'last_tag': last_tag,
            'upgrade_count': upgrade_count,
            'downgrade_count': downgrade_count,
            'reeval_count': reeval_count,
            'score_delta': round(float(last_row.get('total_score', 0) or 0) - float(first_row.get('total_score', 0) or 0), 2),
            'last_theme': last_row.get('semantics', {}).get('trade_theme', ''),
            'last_role': last_row.get('semantics', {}).get('chain_role', ''),
            'changes': changes,
        })

    metrics = build_timeline_metrics(timeline_items)
    latest_rows = timeline_items[-1][1] if timeline_items else {}
    prev_rows = timeline_items[-2][1] if len(timeline_items) >= 2 else {}
    latest_best = best_row(latest_rows)
    prev_best = best_row(prev_rows)

    action = '全部回避'
    reasons = []
    if latest_best:
        current_action = latest_best.get('final_action', '回避')
        if current_action == '主攻':
            if prev_best and latest_best.get('code') == prev_best.get('code') and prev_best.get('final_action') == '主攻':
                action = '继续主攻'
                reasons.append('当前主攻未变，主轴保持一致')
            else:
                action = '重写主攻'
                reasons.append('最新快照出现新的主攻或主轴切换')
        elif current_action == '备选':
            action = '仅留备选'
            reasons.append('当前无唯一主攻，只保留备选等待确认')
        elif current_action == '禁追观察':
            action = '仅观察'
            reasons.append('当前最强样本仍未达可执行级别')
        else:
            action = '全部回避'
            reasons.append('当前最强样本也处于回避级')
    else:
        reasons.append('当前无有效候选')

    if metrics['leader_switch_count'] >= 2:
        reasons.append(f"主轴切换次数较多（{metrics['leader_switch_count']}次），不宜激进升级")
    if per_code:
        latest_upgrades = [x for x in per_code if x['changes'] and x['changes'][-1]['delta'] == '升级']
        latest_downgrades = [x for x in per_code if x['changes'] and x['changes'][-1]['delta'] == '降级']
    else:
        latest_upgrades = []
        latest_downgrades = []

    return {
        'metrics': metrics,
        'decision': {
            'action': action,
            'reasons': reasons,
            'latest_best_code': latest_best.get('code') if latest_best else None,
            'latest_best_name': latest_best.get('name') if latest_best else None,
            'latest_best_state': latest_best.get('final_action') if latest_best else None,
        },
        'latest_upgrades': latest_upgrades,
        'latest_downgrades': latest_downgrades,
        'per_code': per_code,
    }


def render_matrix(items) -> str:
    normalized_items = normalize_snapshot_items(items)
    engine = build_state_engine(normalized_items)
    flow_summary = build_flow_summary(normalized_items)
    lines = ['# QMT 自动状态迁移决策引擎', '']
    lines.extend(build_im_summary(normalized_items, engine, flow_summary))
    lines.append('')
    lines.append('## 完整报告')
    lines.append(f"- 快照数量：{len(items)}")
    lines.append(f"- 主轴稳定性：{engine['metrics']['stability_score']:.2f} / 最强切换={engine['metrics']['best_label_switch_count']}次 / 焦点切换={engine['metrics']['leader_switch_count']}次")
    lines.append(f"- 自动动作：{engine['decision']['action']}")
    if engine['decision']['latest_best_code']:
        lines.append(f"- 当前最强：{engine['decision']['latest_best_code']} {engine['decision']['latest_best_name']} / {engine['decision']['latest_best_state']}")
    lines.append('')

    lines.append('### 1) 自动决策依据')
    for reason in engine['decision']['reasons']:
        lines.append(f'- {reason}')
    if engine['latest_upgrades']:
        lines.append('- 最新升级焦点：' + '；'.join(f"{x['code']} {x['name']}" for x in engine['latest_upgrades'][:3]))
    if engine['latest_downgrades']:
        lines.append('- 最新降级焦点：' + '；'.join(f"{x['code']} {x['name']}" for x in engine['latest_downgrades'][:3]))
    lines.append('')

    lines.append('### 2) 核心票状态迁移')
    if not engine['per_code']:
        lines.append('- 无符合阈值的核心票')
    for item in engine['per_code']:
        lines.append(f"### {item['code']} {item['name']}")
        lines.append(f"- 起点={item['first_tag']} {item['start_state']} | 终点={item['last_tag']} {item['end_state']} | 最大状态={item['max_state']} | 判断={item['summary_delta']}")
        lines.append(f"- 最后角色={item['last_role']} | 最后题材={item['last_theme']} | 总分变化={item['score_delta']:+g}")
        for change in item['changes']:
            lines.append(f"- {change['from_tag']} → {change['to_tag']} | {change['delta']} | {'；'.join(change['triggers'])}")
        lines.append('')

    lines.append('### 3) 全日累计盘中流')
    lines.append(f"- 全日累计：{format_flow_counts_line(flow_summary['total_counts'])}")
    lines.append('')

    lines.append('### 4) 最终动作')
    lines.append(f"> {engine['decision']['action']}")
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot_dir')
    parser.add_argument('--out')
    args = parser.parse_args()

    items = collect_snapshots(Path(args.snapshot_dir))
    if not items:
        raise SystemExit('no intraday snapshots found')
    report = render_matrix(items)
    if args.out:
        Path(args.out).write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()

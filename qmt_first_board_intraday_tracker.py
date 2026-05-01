#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首板盘中跟踪器 - 只跟踪早盘首板候选的盘中表现
"""

import argparse
import json
from pathlib import Path
from typing import Any, Optional


def load_first_board_baseline(trade_date: str, reports_root: Path) -> dict[str, dict]:
    """加载早盘首板候选作为跟踪基线"""
    baseline_path = reports_root / trade_date / 'tushare_auction_0927_candidates.json'
    if not baseline_path.exists():
        return {}
    
    try:
        data = json.loads(baseline_path.read_text(encoding='utf-8', errors='replace'))
        rows = data.get('rows', []) or []
        # 只跟踪 action 不是 '回避' 的首板
        return {
            row['ts_code']: {
                'code': row['ts_code'],
                'name': row['name'],
                'theme': row.get('primary_theme', ''),
                'open_pct': row.get('open_pct', 0),
                'auction_amount': row.get('auction_amount', 0),
                'volume_ratio': row.get('volume_ratio', 0),
                'action': row.get('action', ''),
                'priority': row.get('priority', 0),
            }
            for row in rows
            if row.get('action') != '回避'
        }
    except Exception:
        return {}


def load_qmt_snapshot(snapshot_path: Path) -> dict[str, dict]:
    """加载 QMT 快照数据"""
    if not snapshot_path.exists():
        return {}
    
    try:
        data = json.loads(snapshot_path.read_text(encoding='utf-8', errors='replace'))
        candidates = data.get('candidates', [])
        return {
            row['code']: {
                'code': row['code'],
                'name': row['name'],
                'pct': float(row.get('pct', 0) or 0),
                'amount': float(row.get('amount', 0) or 0),
                'ask1_vol': float(row.get('ask1_vol', 0) or 0),
                'bid_ask_ratio': float(row.get('bid_ask_ratio', 0) or 0),
            }
            for row in candidates
        }
    except Exception:
        return {}


def classify_first_board_status(baseline: dict, current: Optional[dict]) -> str:
    """判定首板当前状态"""
    if not current:
        return '快照缺失'
    
    pct = current['pct']
    ask1_vol = current['ask1_vol']
    
    # 封死涨停
    if pct >= 9.8 and ask1_vol == 0:
        return '封死'
    
    # 涨停但未封死（换手板）
    if pct >= 9.8:
        return '换手涨停'
    
    # 炸板（曾涨停但回落）
    if 4.0 <= pct < 9.8:
        return '炸板'
    
    # 弱势（低于4%）
    if pct < 4.0:
        return '弱势'
    
    return '未知'


def detect_status_change(prev_status: str, curr_status: str) -> Optional[str]:
    """检测状态变化事件"""
    if prev_status == curr_status:
        return None
    
    # 关键事件
    if curr_status == '封死':
        return '封板'
    
    if prev_status == '封死' and curr_status in ('换手涨停', '炸板'):
        return '炸板'
    
    if prev_status in ('炸板', '换手涨停') and curr_status == '封死':
        return '回封'
    
    if curr_status == '弱势':
        return '转弱'
    
    return None


def build_first_board_intraday_report(
    trade_date: str,
    reports_root: Path,
    out_path: Optional[Path] = None,
) -> dict[str, Any]:
    """构建首板盘中跟踪报告"""
    
    # 加载首板基线
    baseline_path = reports_root / trade_date / 'tushare_auction_0927_candidates.json'
    baseline = load_first_board_baseline(trade_date, reports_root)
    if not baseline:
        if baseline_path.exists():
            return {
                'status': 'EMPTY_BASELINE',
                'message': f'{trade_date} 首板候选基线为空（candidate_count=0），无需跟踪',
            }
        return {
            'status': 'NO_BASELINE',
            'message': f'未找到 {trade_date} 的首板候选基线',
        }
    
    # 收集盘中快照
    day_dir = reports_root / trade_date
    snapshots = []
    for path in sorted(day_dir.glob('auction_candidates_main_board_non_st_*.json')):
        time_tag = path.stem.split('_')[-1]
        if not time_tag.isdigit() or len(time_tag) != 4:
            continue
        qmt_data = load_qmt_snapshot(path)
        snapshots.append((time_tag, qmt_data))
    
    if not snapshots:
        return {
            'status': 'NO_SNAPSHOTS',
            'message': f'{trade_date} 无盘中快照',
        }
    
    # 跟踪每只首板的状态迁移
    tracking: dict[str, list[dict]] = {}
    for code, base_info in baseline.items():
        tracking[code] = []
        prev_status = None
        
        for time_tag, qmt_data in snapshots:
            # 直接使用 ts_code 格式查找（基线和快照都是 ts_code 格式）
            current = qmt_data.get(code)
            
            curr_status = classify_first_board_status(base_info, current)
            event = detect_status_change(prev_status, curr_status) if prev_status else None
            
            tracking[code].append({
                'time': time_tag,
                'status': curr_status,
                'event': event,
                'pct': current['pct'] if current else 0,
                'amount': current['amount'] if current else 0,
            })
            
            prev_status = curr_status
    
    # 生成报告
    lines = ['# 首板盘中跟踪', '']
    lines.append(f'交易日：{trade_date}')
    lines.append(f'跟踪数：{len(baseline)} 只')
    
    # 统计数据覆盖率
    covered_count = sum(1 for code in baseline if any(
        qmt_data.get(code) for _, qmt_data in snapshots
    ))
    coverage_pct = round(covered_count / len(baseline) * 100, 1) if baseline else 0
    lines.append(f'数据覆盖：{covered_count}/{len(baseline)} 只 ({coverage_pct}%)')
    
    if coverage_pct < 50:
        lines.append('')
        lines.append('⚠️ **数据覆盖率不足**：QMT 快照只包含 300 只主板非 ST 股票，大部分首板候选不在快照中。')
    
    lines.append('')
    
    # 统计关键事件
    events_summary = {'封板': [], '炸板': [], '回封': [], '转弱': []}
    for code, history in tracking.items():
        base_info = baseline[code]
        for record in history:
            if record['event']:
                events_summary[record['event']].append({
                    'code': code,
                    'name': base_info['name'],
                    'theme': base_info['theme'],
                    'time': record['time'],
                    'pct': record['pct'],
                })
    
    # 极简摘要
    lines.append('## 极简摘要')
    lines.append('')
    
    if events_summary['封板']:
        lines.append(f"**封板 {len(events_summary['封板'])} 只**")
        for item in events_summary['封板'][:3]:
            lines.append(f"- {item['code']} {item['name']}（{item['theme']}）{item['time'][:2]}:{item['time'][2:]} 封板")
        lines.append('')
    
    if events_summary['炸板']:
        lines.append(f"**炸板 {len(events_summary['炸板'])} 只**")
        for item in events_summary['炸板'][:3]:
            lines.append(f"- {item['code']} {item['name']}（{item['theme']}）{item['time'][:2]}:{item['time'][2:]} 炸板")
        lines.append('')
    
    if events_summary['回封']:
        lines.append(f"**回封 {len(events_summary['回封'])} 只**")
        for item in events_summary['回封'][:3]:
            lines.append(f"- {item['code']} {item['name']}（{item['theme']}）{item['time'][:2]}:{item['time'][2:]} 回封")
        lines.append('')
    
    if not any(events_summary.values()):
        lines.append('暂无关键事件')
        lines.append('')
    
    # 完整跟踪表
    lines.append('## 完整跟踪')
    lines.append('')
    
    for code, history in sorted(tracking.items(), key=lambda x: baseline[x[0]]['priority'], reverse=True):
        base_info = baseline[code]
        lines.append(f"### {code} {base_info['name']} - {base_info['theme']}")
        lines.append(f"早盘：开盘 {base_info['open_pct']:.2f}% | 竞价额 {base_info['auction_amount']/1e7:.2f}千万 | 量比 {base_info['volume_ratio']:.2f}")
        lines.append('')
        
        # 检查是否所有时间点都是"快照缺失"
        all_missing = all(record['status'] == '快照缺失' for record in history)
        if all_missing:
            lines.append('- ⚠️ 该股票不在 QMT 快照数据中，无法跟踪盘中表现')
        else:
            for record in history:
                if record['status'] == '快照缺失':
                    continue  # 跳过缺失的时间点
                event_tag = f" [{record['event']}]" if record['event'] else ""
                lines.append(f"- {record['time'][:2]}:{record['time'][2:]}: {record['status']}{event_tag} | 涨幅 {record['pct']:.2f}% | 成交额 {record['amount']/1e8:.2f}亿")
        
        lines.append('')
    
    report_text = '\n'.join(lines)
    
    if out_path:
        out_path.write_text(report_text, encoding='utf-8')
    
    return {
        'status': 'OK',
        'report': report_text,
        'events_summary': events_summary,
        'tracking_count': len(baseline),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='首板盘中跟踪')
    parser.add_argument('--date', required=True, help='交易日 YYYYMMDD')
    parser.add_argument('--out', help='输出路径')
    args = parser.parse_args()
    
    reports_root = Path(__file__).parent / 'qmt_sync' / 'reports'
    out_path = Path(args.out) if args.out else None
    
    result = build_first_board_intraday_report(args.date, reports_root, out_path)
    
    if result['status'] == 'EMPTY_BASELINE':
        # 空候选不是错误：今日竞价未筛出首板候选，跳过跟踪
        print(f"信息：{result['message']}")
        return
    
    if result['status'] != 'OK':
        print(f"错误：{result['message']}")
        raise SystemExit(1)
    
    print(result['report'])


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首板盘中买入信号分析 - 从跟踪报告中提取值得关注的买入机会
"""

import argparse
import json
from pathlib import Path
from typing import Optional


def analyze_buy_signals(report_path: Path, baseline_path: Path) -> dict:
    """分析买入信号"""
    
    # 加载报告
    report_text = report_path.read_text(encoding='utf-8', errors='replace')
    
    # 加载基线数据（首板候选）
    baseline_data = json.loads(baseline_path.read_text(encoding='utf-8', errors='replace'))
    baseline_rows = {row['ts_code']: row for row in baseline_data.get('rows', [])}
    
    # 解析报告，提取每只股票的最新状态
    stocks = {}
    current_code = None
    current_name = None
    current_theme = None
    current_baseline = None
    
    for line in report_text.split('\n'):
        # 匹配股票标题行：### 002201.SZ 九鼎新材 - 年报增长
        if line.startswith('### '):
            parts = line[4:].split(' - ')
            if len(parts) == 2:
                code_name = parts[0].strip()
                theme = parts[1].strip()
                code_parts = code_name.split(' ', 1)
                if len(code_parts) == 2:
                    current_code = code_parts[0]
                    current_name = code_parts[1]
                    current_theme = theme
                    current_baseline = baseline_rows.get(current_code, {})
                    stocks[current_code] = {
                        'code': current_code,
                        'name': current_name,
                        'theme': current_theme,
                        'baseline': current_baseline,
                        'timeline': [],
                    }
        
        # 匹配时间线：- 14:00: 封死 [封板] | 涨幅 9.98% | 成交额 20.97亿
        if current_code and line.startswith('- ') and ':' in line:
            parts = line[2:].split(':', 1)
            if len(parts) == 2:
                time_tag = parts[0].strip()
                status_parts = parts[1].split('|')
                if len(status_parts) >= 3:
                    status_text = status_parts[0].strip()
                    pct_text = status_parts[1].strip()
                    amount_text = status_parts[2].strip()
                    
                    # 提取状态和事件
                    status = status_text.split('[')[0].strip()
                    event = None
                    if '[' in status_text and ']' in status_text:
                        event = status_text.split('[')[1].split(']')[0]
                    
                    # 提取涨幅
                    pct = 0.0
                    if '涨幅' in pct_text:
                        pct_str = pct_text.split('涨幅')[1].strip().replace('%', '')
                        try:
                            pct = float(pct_str)
                        except ValueError:
                            pass
                    
                    stocks[current_code]['timeline'].append({
                        'time': time_tag,
                        'status': status,
                        'event': event,
                        'pct': pct,
                    })
    
    # 分析买入信号
    buy_signals = []
    
    for code, data in stocks.items():
        if not data['timeline']:
            continue
        
        latest = data['timeline'][-1]
        baseline = data['baseline']
        open_pct = baseline.get('open_pct', 0)
        
        # 只关注真正值得买入的机会
        
        # 信号1：炸板回封（最强买入信号）
        if latest['event'] == '回封':
            buy_signals.append({
                'code': code,
                'name': data['name'],
                'theme': data['theme'],
                'signal': '炸板回封',
                'reason': f"炸板后回封至 {latest['pct']:.2f}%，资金二次确认",
                'priority': 1,
                'action': '重点关注',
                'note': '回封说明资金认可度高，可考虑次日低吸',
            })
        
        # 信号2：封死涨停且早盘开盘强势（开盘 > 6%）
        elif latest['status'] == '封死' and open_pct > 6.0:
            buy_signals.append({
                'code': code,
                'name': data['name'],
                'theme': data['theme'],
                'signal': '强势封板',
                'reason': f"早盘开盘 {open_pct:.2f}%，现已封死涨停",
                'priority': 2,
                'action': '次日观察',
                'note': '等待次日竞价，若高开 3-5% 可考虑',
            })
        
        # 信号3：炸板但涨幅仍在 5-8%（低吸机会）
        elif latest['status'] == '炸板' and 5.0 <= latest['pct'] < 8.0:
            buy_signals.append({
                'code': code,
                'name': data['name'],
                'theme': data['theme'],
                'signal': '炸板回调',
                'reason': f"炸板回调至 {latest['pct']:.2f}%，尾盘可能有低吸机会",
                'priority': 3,
                'action': '尾盘观察',
                'note': '若尾盘有资金回流可考虑，否则等次日',
            })
    
    # 按优先级排序
    buy_signals.sort(key=lambda x: x['priority'])
    
    return {
        'signals': buy_signals,
        'total': len(buy_signals),
    }


def format_buy_report(signals: list) -> str:
    """格式化买入建议报告"""
    if not signals:
        return "暂无明确买入信号"
    
    lines = []
    
    # 按信号类型分组
    by_signal = {}
    for sig in signals:
        signal_type = sig['signal']
        by_signal.setdefault(signal_type, []).append(sig)
    
    for signal_type, items in by_signal.items():
        lines.append(f"**{signal_type} {len(items)} 只**")
        for item in items[:3]:  # 每类最多显示 3 只
            lines.append(f"- {item['code']} {item['name']}（{item['theme']}）")
            lines.append(f"  {item['reason']}")
            lines.append(f"  操作：{item['action']} | {item['note']}")
        lines.append('')
    
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='首板盘中买入信号分析')
    parser.add_argument('--date', required=True, help='交易日 YYYYMMDD')
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent
    reports_root = repo_root / 'qmt_sync' / 'reports'
    
    report_path = reports_root / args.date / 'first_board_intraday_tracker.txt'
    baseline_path = reports_root / args.date / 'tushare_auction_0927_candidates.json'
    
    if not report_path.exists():
        print('ERROR: 跟踪报告不存在')
        return
    
    if not baseline_path.exists():
        print('ERROR: 基线数据不存在')
        return
    
    result = analyze_buy_signals(report_path, baseline_path)
    
    if result['total'] == 0:
        print('暂无明确买入信号')
        return
    
    print(format_buy_report(result['signals']))


if __name__ == '__main__':
    main()

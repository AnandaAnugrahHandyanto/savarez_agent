#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今日双重评分报告
获取今日涨停板数据，计算策略分和入场分
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# 添加runtime目录到路径
runtime_dir = Path.home() / '.hermes' / 'runtime-hermes-agent'
sys.path.insert(0, str(runtime_dir))

from lib.entry_timing.data_fetcher import TushareDataFetcher
from lib.entry_timing.signal_detector_v2 import StopFallingSignalDetectorV2


def calculate_strategy_score(limit_data: Dict, daily_data: List[Dict]) -> Dict:
    """
    计算策略分（简化版qmt_candidate_ranker逻辑）
    """
    if not daily_data:
        return {'score': 0, 'breakdown': {}, 'signals': []}
    
    today = daily_data[-1]
    
    # 基础数据
    amount = today.get('amount', 0) * 10000  # 转换为元
    open_price = today.get('open', 0)
    pre_close = today.get('pre_close', 0)
    
    # 计算开盘幅度
    open_pct = 0
    if pre_close > 0:
        open_pct = (open_price - pre_close) / pre_close * 100
    
    score = 0
    breakdown = {}
    signals = []
    
    # 1. 成交额评分（30分）
    if amount >= 3_000_000_000:
        amount_score = 30
        signals.append(f"✓ 超大成交额 ({amount/100000000:.1f}亿)")
    elif amount >= 1_500_000_000:
        amount_score = 25
        signals.append(f"✓ 大成交额 ({amount/100000000:.1f}亿)")
    elif amount >= 800_000_000:
        amount_score = 20
        signals.append(f"○ 中等成交额 ({amount/100000000:.1f}亿)")
    elif amount >= 500_000_000:
        amount_score = 15
        signals.append(f"○ 一般成交额 ({amount/100000000:.1f}亿)")
    else:
        amount_score = 10
        signals.append(f"✗ 成交额偏小 ({amount/100000000:.1f}亿)")
    
    score += amount_score
    breakdown['amount'] = amount_score
    
    # 2. 开盘幅度评分（30分）
    if 1.0 <= open_pct <= 4.0:
        open_score = 30
        signals.append(f"✓ 理想开盘 (+{open_pct:.2f}%)")
    elif 0.3 <= open_pct <= 5.5:
        open_score = 25
        signals.append(f"○ 合理开盘 (+{open_pct:.2f}%)")
    elif -1.0 <= open_pct <= 6.5:
        open_score = 20
        signals.append(f"○ 可接受开盘 ({open_pct:+.2f}%)")
    else:
        open_score = 10
        signals.append(f"✗ 开盘幅度异常 ({open_pct:+.2f}%)")
    
    score += open_score
    breakdown['open'] = open_score
    
    # 3. 买卖比评分（20分）- 简化为固定值
    bid_ask_score = 12
    signals.append(f"○ 买卖比 (数据缺失)")
    score += bid_ask_score
    breakdown['bid_ask'] = bid_ask_score
    
    # 4. 题材评分（20分）- 简化为固定值
    theme_score = 10
    signals.append(f"○ 题材 (待补充)")
    score += theme_score
    breakdown['theme'] = theme_score
    
    return {
        'score': score,
        'breakdown': breakdown,
        'signals': signals
    }


def generate_today_report(trade_date: str = None):
    """
    生成今日双重评分报告
    """
    if not os.environ.get('TUSHARE_TOKEN'):
        print("错误: 未设置 TUSHARE_TOKEN 环境变量")
        return
    
    fetcher = TushareDataFetcher()
    detector = StopFallingSignalDetectorV2()
    
    # 确定交易日期
    if not trade_date:
        # 获取最近交易日
        recent_dates = fetcher.get_recent_trade_dates(5)
        trade_date = recent_dates[-1] if recent_dates else datetime.now().strftime('%Y%m%d')
    
    print(f"{'='*80}")
    print(f"双重评分报告 - {trade_date}")
    print(f"{'='*80}\n")
    
    # 获取涨停板数据
    print("获取涨停板数据...")
    try:
        limit_dict = fetcher.get_limit_list(trade_date)
    except Exception as e:
        print(f"错误: 无法获取涨停板数据 - {e}")
        return
    
    if not limit_dict:
        print(f"{trade_date} 无涨停板数据")
        return
    
    print(f"共 {len(limit_dict)} 只涨停股\n")
    
    # 分析每只股票
    candidates = []
    
    for i, (ts_code, limit_data) in enumerate(limit_dict.items(), 1):
        if i % 10 == 0:
            print(f"  分析进度: {i}/{len(limit_dict)}")
        
        try:
            name = limit_data.get('name', '')
            
            # 排除ST
            if 'ST' in name or 'st' in name:
                continue
            
            # 排除一字板
            open_pct = limit_data.get('open', 0)
            if open_pct >= 9.5:
                continue
            
            # 获取历史数据
            start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
            daily_data = fetcher.get_daily_data(ts_code, start_date, trade_date)
            
            if not daily_data or len(daily_data) < 2:
                continue
            
            # 计算策略分
            strategy_result = calculate_strategy_score(limit_data, daily_data)
            strategy_score = strategy_result['score']
            
            # 计算入场分（模拟次日）
            # 注意：这里用今日数据模拟，实际应该等次日数据
            entry_signal = detector.check_signal(daily_data[-10:])
            entry_score = entry_signal['score']
            
            candidates.append({
                'ts_code': ts_code,
                'name': name,
                'strategy_score': strategy_score,
                'strategy_breakdown': strategy_result['breakdown'],
                'strategy_signals': strategy_result['signals'],
                'entry_score': entry_score,
                'entry_breakdown': entry_signal['breakdown'],
                'entry_signals': entry_signal['signals'][:5],  # 只取前5个信号
                'can_enter': entry_signal['can_enter'],
                'scenario': entry_signal['details'].get('scenario', 'unknown'),
                'today_pct': daily_data[-1].get('pct_chg', 0),
                'amount': daily_data[-1].get('amount', 0) * 10000
            })
        
        except Exception as e:
            continue
    
    # 排序：策略分 + 入场分
    candidates.sort(key=lambda x: (x['strategy_score'] + x['entry_score']), reverse=True)
    
    # 分类统计
    high_quality = [c for c in candidates if c['strategy_score'] >= 60 and c['entry_score'] >= 70]
    medium_quality = [c for c in candidates if c['strategy_score'] >= 60 and c['entry_score'] >= 55]
    all_qualified = [c for c in candidates if c['strategy_score'] >= 60]
    
    print(f"\n{'='*80}")
    print("统计摘要")
    print(f"{'='*80}\n")
    print(f"总候选数: {len(candidates)}")
    print(f"策略分≥60: {len(all_qualified)} 个")
    print(f"策略分≥60 且 入场分≥55: {len(medium_quality)} 个")
    print(f"策略分≥60 且 入场分≥70: {len(high_quality)} 个 ⭐\n")
    
    # 打印高质量候选
    if high_quality:
        print(f"{'='*80}")
        print(f"高质量候选（策略分≥60 且 入场分≥70）")
        print(f"{'='*80}\n")
        
        for i, c in enumerate(high_quality, 1):
            print(f"{i}. {c['name']} ({c['ts_code']})")
            print(f"   策略分: {c['strategy_score']:.0f} | 入场分: {c['entry_score']:.0f} | 场景: {c['scenario']}")
            print(f"   涨幅: {c['today_pct']:+.2f}% | 成交额: {c['amount']/100000000:.1f}亿")
            print(f"   策略信号: {', '.join(c['strategy_signals'][:3])}")
            print(f"   入场信号: {', '.join(c['entry_signals'][:3])}")
            print()
    
    # 打印中等质量候选
    if medium_quality and len(medium_quality) > len(high_quality):
        print(f"{'='*80}")
        print(f"中等质量候选（策略分≥60 且 入场分≥55）")
        print(f"{'='*80}\n")
        
        medium_only = [c for c in medium_quality if c not in high_quality][:10]
        for i, c in enumerate(medium_only, 1):
            print(f"{i}. {c['name']} ({c['ts_code']})")
            print(f"   策略分: {c['strategy_score']:.0f} | 入场分: {c['entry_score']:.0f} | 场景: {c['scenario']}")
            print(f"   涨幅: {c['today_pct']:+.2f}% | 成交额: {c['amount']/100000000:.1f}亿")
            print()
    
    # 打印完整列表（前20）
    print(f"{'='*80}")
    print(f"完整候选列表（策略分≥60，按综合得分排序，前20）")
    print(f"{'='*80}\n")
    
    print(f"{'排名':<6} {'代码':<12} {'名称':<12} {'策略分':<8} {'入场分':<8} {'综合':<8} {'场景':<15}")
    print(f"{'-'*80}")
    
    for i, c in enumerate(all_qualified[:20], 1):
        total = c['strategy_score'] + c['entry_score']
        marker = "⭐" if c in high_quality else "○" if c in medium_quality else ""
        print(f"{i:<6} {c['ts_code']:<12} {c['name']:<12} {c['strategy_score']:<8.0f} {c['entry_score']:<8.0f} {total:<8.0f} {c['scenario']:<15} {marker}")
    
    print(f"\n{'='*80}\n")
    
    # 保存结果
    output_file = Path.home() / '.hermes' / 'state' / 'qmt' / f'daily_report_{trade_date}.json'
    output_data = {
        'trade_date': trade_date,
        'timestamp': datetime.now().isoformat(),
        'total_candidates': len(candidates),
        'high_quality_count': len(high_quality),
        'medium_quality_count': len(medium_quality),
        'all_qualified_count': len(all_qualified),
        'high_quality': high_quality,
        'medium_quality': medium_only if medium_quality else [],
        'all_candidates': all_qualified
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"详细报告已保存到: {output_file}\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='今日双重评分报告')
    parser.add_argument('--date', type=str, help='交易日期（YYYYMMDD），默认最近交易日')
    
    args = parser.parse_args()
    
    generate_today_report(trade_date=args.date)

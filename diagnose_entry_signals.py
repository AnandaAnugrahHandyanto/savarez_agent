#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测诊断脚本
分析失败案例特征，找出评分体系的问题
"""
import os
import sys
import json
from pathlib import Path
from collections import defaultdict

# 添加runtime目录到路径
runtime_dir = Path.home() / '.hermes' / 'runtime-hermes-agent'
sys.path.insert(0, str(runtime_dir))

from lib.entry_timing.data_fetcher import TushareDataFetcher
from lib.entry_timing.signal_detector_v2 import StopFallingSignalDetectorV2


def analyze_case(fetcher: TushareDataFetcher, detector: StopFallingSignalDetectorV2, 
                 ts_code: str, entry_date: str):
    """分析单个案例"""
    from datetime import datetime, timedelta
    
    # 获取数据
    start_date = (datetime.strptime(entry_date, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
    end_date = (datetime.strptime(entry_date, '%Y%m%d') + timedelta(days=10)).strftime('%Y%m%d')
    
    daily_data = fetcher.get_daily_data(ts_code, start_date, end_date)
    
    if not daily_data:
        return None
    
    # 找到选股日
    entry_idx = None
    for i, day in enumerate(daily_data):
        if day['trade_date'] == entry_date:
            entry_idx = i
            break
    
    if entry_idx is None or entry_idx >= len(daily_data) - 2:
        return None
    
    # 检查次日和第三日的信号
    results = []
    for offset in [1, 2]:
        check_idx = entry_idx + offset
        if check_idx >= len(daily_data):
            break
        
        history = daily_data[:check_idx + 1]
        signal = detector.check_signal(history[-10:])
        
        check_day = daily_data[check_idx]
        next_day = daily_data[check_idx + 1] if check_idx + 1 < len(daily_data) else None
        
        # 计算实际收益（简化：用次日收盘价）
        actual_profit = None
        if next_day:
            entry_price = check_day.get('close', 0)
            exit_price = next_day.get('close', 0)
            if entry_price > 0:
                actual_profit = (exit_price - entry_price) / entry_price * 100
        
        results.append({
            'day': offset,
            'date': check_day.get('trade_date'),
            'signal': signal,
            'actual_profit': actual_profit
        })
    
    return {
        'ts_code': ts_code,
        'entry_date': entry_date,
        'checks': results
    }


def diagnose_failures(sample_size: int = 30):
    """诊断失败案例"""
    if not os.environ.get('TUSHARE_TOKEN'):
        print("错误: 未设置 TUSHARE_TOKEN 环境变量")
        return
    
    fetcher = TushareDataFetcher()
    detector = StopFallingSignalDetectorV2()
    
    # 获取候选
    trade_dates = fetcher.get_recent_trade_dates(30)
    candidates = []
    
    print("收集候选案例...")
    for trade_date in trade_dates[:10]:  # 只取最近10天
        try:
            limit_dict = fetcher.get_limit_list(trade_date)
            for ts_code, limit_data in list(limit_dict.items())[:5]:  # 每天取5个
                name = limit_data.get('name', '')
                if 'ST' not in name:
                    candidates.append((ts_code, trade_date))
        except:
            continue
    
    if len(candidates) > sample_size:
        import random
        candidates = random.sample(candidates, sample_size)
    
    print(f"\n分析 {len(candidates)} 个案例...\n")
    
    # 统计
    stats = {
        'false_positive': [],  # 信号通过但亏损
        'false_negative': [],  # 信号拒绝但盈利
        'true_positive': [],   # 信号通过且盈利
        'true_negative': [],   # 信号拒绝且亏损
    }
    
    for ts_code, entry_date in candidates:
        result = analyze_case(fetcher, detector, ts_code, entry_date)
        if not result:
            continue
        
        for check in result['checks']:
            signal = check['signal']
            profit = check['actual_profit']
            
            if profit is None:
                continue
            
            can_enter = signal.get('can_enter', False)
            score = signal.get('score', 0)
            
            if can_enter and profit < 0:
                stats['false_positive'].append({
                    'code': ts_code,
                    'date': check['date'],
                    'score': score,
                    'profit': profit,
                    'breakdown': signal.get('breakdown', {}),
                    'scenario': signal.get('details', {}).get('scenario', 'unknown')
                })
            elif not can_enter and profit > 0:
                stats['false_negative'].append({
                    'code': ts_code,
                    'date': check['date'],
                    'score': score,
                    'profit': profit,
                    'breakdown': signal.get('breakdown', {}),
                    'scenario': signal.get('details', {}).get('scenario', 'unknown')
                })
            elif can_enter and profit > 0:
                stats['true_positive'].append({
                    'code': ts_code,
                    'date': check['date'],
                    'score': score,
                    'profit': profit
                })
            else:
                stats['true_negative'].append({
                    'code': ts_code,
                    'date': check['date'],
                    'score': score,
                    'profit': profit
                })
    
    # 打印诊断结果
    print(f"{'='*60}")
    print("诊断结果")
    print(f"{'='*60}\n")
    
    print(f"真阳性（信号✓ 盈利✓）: {len(stats['true_positive'])} 个")
    print(f"真阴性（信号✗ 亏损✓）: {len(stats['true_negative'])} 个")
    print(f"假阳性（信号✓ 亏损✗）: {len(stats['false_positive'])} 个")
    print(f"假阴性（信号✗ 盈利✗）: {len(stats['false_negative'])} 个")
    
    # 分析假阳性（最关键的问题）
    if stats['false_positive']:
        print(f"\n{'='*60}")
        print("假阳性分析（信号通过但亏损）")
        print(f"{'='*60}\n")
        
        # 场景分布
        scenario_dist = defaultdict(int)
        for case in stats['false_positive']:
            scenario_dist[case['scenario']] += 1
        
        print("场景分布:")
        for scenario, count in scenario_dist.items():
            print(f"  {scenario}: {count} 个")
        
        # 评分分布
        scores = [c['score'] for c in stats['false_positive']]
        print(f"\n评分分布:")
        print(f"  平均分: {sum(scores)/len(scores):.1f}")
        print(f"  最高分: {max(scores)}")
        print(f"  最低分: {min(scores)}")
        
        # 各维度得分分析
        print(f"\n各维度平均得分:")
        breakdown_avg = defaultdict(list)
        for case in stats['false_positive']:
            for dim, score in case['breakdown'].items():
                breakdown_avg[dim].append(score)
        
        for dim, scores in breakdown_avg.items():
            print(f"  {dim}: {sum(scores)/len(scores):.1f}")
    
    # 分析假阴性
    if stats['false_negative']:
        print(f"\n{'='*60}")
        print("假阴性分析（信号拒绝但盈利）")
        print(f"{'='*60}\n")
        
        # 场景分布
        scenario_dist = defaultdict(int)
        for case in stats['false_negative']:
            scenario_dist[case['scenario']] += 1
        
        print("场景分布:")
        for scenario, count in scenario_dist.items():
            print(f"  {scenario}: {count} 个")
        
        # 评分分布
        scores = [c['score'] for c in stats['false_negative']]
        print(f"\n评分分布:")
        print(f"  平均分: {sum(scores)/len(scores):.1f}")
        print(f"  最高分: {max(scores)}")
        print(f"  最低分: {min(scores)}")
        
        # 各维度得分分析
        print(f"\n各维度平均得分:")
        breakdown_avg = defaultdict(list)
        for case in stats['false_negative']:
            for dim, score in case['breakdown'].items():
                breakdown_avg[dim].append(score)
        
        for dim, scores in breakdown_avg.items():
            print(f"  {dim}: {sum(scores)/len(scores):.1f}")
    
    print(f"\n{'='*60}\n")
    
    # 保存详细结果
    output_file = Path.home() / '.hermes' / 'state' / 'qmt' / 'diagnosis_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"详细结果已保存到: {output_file}\n")


if __name__ == '__main__':
    diagnose_failures(sample_size=30)

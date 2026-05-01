#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
保守策略回测：仅在极高确定性（70+分）时入场
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# 添加runtime目录到路径
runtime_dir = Path.home() / '.hermes' / 'runtime-hermes-agent'
sys.path.insert(0, str(runtime_dir))

from lib.entry_timing.data_fetcher import TushareDataFetcher
from lib.entry_timing.signal_detector_v2 import StopFallingSignalDetectorV2


def backtest_conservative_strategy(fetcher: TushareDataFetcher, 
                                   test_cases: List[Tuple[str, str]],
                                   threshold: int = 70):
    """
    保守策略回测
    
    Args:
        fetcher: 数据获取器
        test_cases: [(ts_code, entry_date), ...]
        threshold: 入场阈值
    """
    detector = StopFallingSignalDetectorV2()
    
    results = []
    
    print(f"开始回测 {len(test_cases)} 个案例（阈值={threshold}分）...")
    
    for i, (ts_code, entry_date) in enumerate(test_cases, 1):
        if i % 20 == 0:
            print(f"  进度: {i}/{len(test_cases)}")
        
        try:
            # 获取数据
            start_date = (datetime.strptime(entry_date, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
            end_date = (datetime.strptime(entry_date, '%Y%m%d') + timedelta(days=30)).strftime('%Y%m%d')
            
            daily_data = fetcher.get_daily_data(ts_code, start_date, end_date)
            
            if not daily_data:
                continue
            
            # 找到选股日
            entry_day_idx = None
            for idx, day in enumerate(daily_data):
                if day['trade_date'] == entry_date:
                    entry_day_idx = idx
                    break
            
            if entry_day_idx is None:
                continue
            
            # 从次日开始，最多等2天找入场信号
            max_wait_days = 2
            actual_entry_idx = None
            entry_signal = None
            
            for wait_day in range(1, max_wait_days + 1):
                check_idx = entry_day_idx + wait_day
                
                if check_idx >= len(daily_data):
                    break
                
                # 检查止跌信号
                history_data = daily_data[:check_idx + 1]
                signal_result = detector.check_signal(history_data[-10:])
                
                # 使用自定义阈值
                if signal_result['score'] >= threshold:
                    actual_entry_idx = check_idx
                    entry_signal = signal_result
                    break
            
            # 如果2天内没有信号，跳过
            if actual_entry_idx is None:
                continue
            
            # 入场价：当日收盘价
            entry_day = daily_data[actual_entry_idx]
            entry_price = entry_day.get('close', 0)
            entry_actual_date = entry_day.get('trade_date')
            
            if entry_price == 0:
                continue
            
            # 模拟持仓
            stop_profit = 0.20
            stop_loss = 0.08
            time_stop = 10
            
            stop_profit_price = entry_price * (1 + stop_profit)
            stop_loss_price = entry_price * (1 - stop_loss)
            
            holding_days = 0
            exit_reason = None
            exit_price = None
            exit_date = None
            
            # 从入场次日开始检查
            for i in range(actual_entry_idx + 1, len(daily_data)):
                day = daily_data[i]
                holding_days += 1
                
                high = day.get('high', 0)
                low = day.get('low', 0)
                close = day.get('close', 0)
                
                # 检查止盈
                if high >= stop_profit_price:
                    exit_reason = 'stop_profit'
                    exit_price = stop_profit_price
                    exit_date = day.get('trade_date')
                    break
                
                # 检查止损
                if low <= stop_loss_price:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss_price
                    exit_date = day.get('trade_date')
                    break
                
                # 检查时间止损
                if holding_days >= time_stop:
                    exit_reason = 'time_stop'
                    exit_price = close
                    exit_date = day.get('trade_date')
                    break
            
            # 如果没有触发任何止损，用最后一天收盘价
            if exit_reason is None:
                last_day = daily_data[-1]
                exit_reason = 'end_of_data'
                exit_price = last_day.get('close', entry_price)
                exit_date = last_day.get('trade_date')
                holding_days = len(daily_data) - actual_entry_idx - 1
            
            # 计算收益
            profit_pct = (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
            
            results.append({
                'ts_code': ts_code,
                'entry_date': entry_actual_date,
                'entry_price': entry_price,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'holding_days': holding_days,
                'profit_pct': profit_pct,
                'win': profit_pct > 0,
                'score': entry_signal['score'],
                'breakdown': entry_signal['breakdown'],
                'scenario': entry_signal['details'].get('scenario', 'unknown')
            })
        
        except Exception as e:
            continue
    
    return results


def run_threshold_comparison(days: int = 30, max_cases: int = 200):
    """
    对比不同阈值的效果
    """
    if not os.environ.get('TUSHARE_TOKEN'):
        print("错误: 未设置 TUSHARE_TOKEN 环境变量")
        return
    
    fetcher = TushareDataFetcher()
    
    # 获取候选
    trade_dates = fetcher.get_recent_trade_dates(days)
    candidates = []
    
    print("收集候选案例...")
    for trade_date in trade_dates:
        try:
            limit_dict = fetcher.get_limit_list(trade_date)
            
            for ts_code, limit_data in limit_dict.items():
                name = limit_data.get('name', '')
                
                # 排除ST
                if 'ST' in name or 'st' in name:
                    continue
                
                # 排除一字板
                open_pct = limit_data.get('open', 0)
                if open_pct >= 9.5:
                    continue
                
                candidates.append((ts_code, trade_date))
        
        except Exception as e:
            continue
    
    if len(candidates) > max_cases:
        import random
        candidates = random.sample(candidates, max_cases)
    
    print(f"共 {len(candidates)} 个候选案例\n")
    
    # 测试不同阈值
    thresholds = [55, 60, 65, 70, 75, 80]
    
    print(f"{'='*80}")
    print(f"{'阈值':<8} {'入场数':<10} {'胜率':<10} {'平均收益':<12} {'最大盈利':<12} {'最大亏损':<12}")
    print(f"{'='*80}")
    
    all_results = {}
    
    for threshold in thresholds:
        results = backtest_conservative_strategy(fetcher, candidates, threshold)
        
        if not results:
            print(f"{threshold:<8} {'0':<10} {'-':<10} {'-':<12} {'-':<12} {'-':<12}")
            continue
        
        total = len(results)
        win_count = sum(1 for r in results if r['win'])
        win_rate = win_count / total * 100 if total > 0 else 0
        
        profits = [r['profit_pct'] for r in results]
        avg_profit = sum(profits) / len(profits) if profits else 0
        max_profit = max(profits) if profits else 0
        max_loss = min(profits) if profits else 0
        
        print(f"{threshold:<8} {total:<10} {win_rate:<10.2f}% {avg_profit:<12.2f}% {max_profit:<12.2f}% {max_loss:<12.2f}%")
        
        all_results[threshold] = {
            'total': total,
            'win_count': win_count,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'results': results
        }
    
    print(f"{'='*80}\n")
    
    # 保存详细结果
    output_file = Path.home() / '.hermes' / 'state' / 'qmt' / 'conservative_backtest_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"详细结果已保存到: {output_file}\n")
    
    return all_results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='保守策略回测')
    parser.add_argument('--days', type=int, default=30, help='回溯天数（默认30）')
    parser.add_argument('--max-cases', type=int, default=200, help='最大测试案例数（默认200）')
    
    args = parser.parse_args()
    
    run_threshold_comparison(days=args.days, max_cases=args.max_cases)

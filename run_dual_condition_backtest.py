#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双重条件回测：策略分≥60 且 入场分≥70
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict

# 添加runtime目录到路径
runtime_dir = Path.home() / '.hermes' / 'runtime-hermes-agent'
sys.path.insert(0, str(runtime_dir))

from lib.entry_timing.data_fetcher import TushareDataFetcher
from lib.entry_timing.signal_detector_v2 import StopFallingSignalDetectorV2


def get_strategy_score(candidate: Dict) -> float:
    """
    计算策略分（模拟qmt_candidate_ranker的评分逻辑）
    简化版：基于成交额、开盘幅度、买卖比
    """
    amount = candidate.get('amount', 0)
    open_pct = candidate.get('open_pct', 0)
    bid_ask_ratio = candidate.get('bid_ask_ratio', 1.0)
    
    score = 0
    
    # 成交额评分（30分）
    if amount >= 3_000_000_000:
        score += 30
    elif amount >= 1_500_000_000:
        score += 25
    elif amount >= 800_000_000:
        score += 20
    elif amount >= 500_000_000:
        score += 15
    else:
        score += 10
    
    # 开盘幅度评分（30分）
    if 1.0 <= open_pct <= 4.0:
        score += 30
    elif 0.3 <= open_pct <= 5.5:
        score += 25
    elif -1.0 <= open_pct <= 6.5:
        score += 20
    else:
        score += 10
    
    # 买卖比评分（20分）
    if bid_ask_ratio >= 1.8:
        score += 20
    elif bid_ask_ratio >= 1.3:
        score += 15
    elif bid_ask_ratio >= 1.0:
        score += 10
    else:
        score += 5
    
    # 题材加分（20分）- 简化为固定值
    score += 10
    
    return score


def backtest_dual_condition(fetcher: TushareDataFetcher, 
                            test_cases: List[Tuple[str, str, Dict]],
                            strategy_threshold: int = 60,
                            entry_threshold: int = 70):
    """
    双重条件回测
    
    Args:
        fetcher: 数据获取器
        test_cases: [(ts_code, entry_date, candidate_info), ...]
        strategy_threshold: 策略分阈值
        entry_threshold: 入场分阈值
    """
    detector = StopFallingSignalDetectorV2()
    
    results = []
    filtered_by_strategy = 0
    filtered_by_entry = 0
    
    print(f"开始回测 {len(test_cases)} 个案例")
    print(f"条件：策略分≥{strategy_threshold} 且 入场分≥{entry_threshold}\n")
    
    for i, (ts_code, entry_date, candidate_info) in enumerate(test_cases, 1):
        if i % 20 == 0:
            print(f"  进度: {i}/{len(test_cases)}")
        
        try:
            # 计算策略分
            strategy_score = get_strategy_score(candidate_info)
            
            # 第一层过滤：策略分
            if strategy_score < strategy_threshold:
                filtered_by_strategy += 1
                continue
            
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
                
                # 第二层过滤：入场分
                if signal_result['score'] >= entry_threshold:
                    actual_entry_idx = check_idx
                    entry_signal = signal_result
                    break
            
            # 如果2天内没有信号，跳过
            if actual_entry_idx is None:
                filtered_by_entry += 1
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
                'strategy_score': strategy_score,
                'entry_score': entry_signal['score'],
                'breakdown': entry_signal['breakdown'],
                'scenario': entry_signal['details'].get('scenario', 'unknown')
            })
        
        except Exception as e:
            continue
    
    return results, filtered_by_strategy, filtered_by_entry


def run_dual_condition_backtest(days: int = 30, max_cases: int = 200):
    """
    运行双重条件回测
    """
    if not os.environ.get('TUSHARE_TOKEN'):
        print("错误: 未设置 TUSHARE_TOKEN 环境变量")
        return
    
    fetcher = TushareDataFetcher()
    
    # 获取候选（带模拟的策略信息）
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
                
                # 模拟候选信息（实际应从qmt推送数据中获取）
                candidate_info = {
                    'amount': limit_data.get('amount', 0) * 10000 if limit_data.get('amount') else 500_000_000,  # 转换为元
                    'open_pct': open_pct,
                    'bid_ask_ratio': 1.2,  # 模拟值
                }
                
                candidates.append((ts_code, trade_date, candidate_info))
        
        except Exception as e:
            continue
    
    if len(candidates) > max_cases:
        import random
        candidates = random.sample(candidates, max_cases)
    
    print(f"共 {len(candidates)} 个候选案例\n")
    
    # 执行回测
    results, filtered_strategy, filtered_entry = backtest_dual_condition(
        fetcher, candidates, strategy_threshold=60, entry_threshold=70
    )
    
    # 打印结果
    print(f"\n{'='*60}")
    print("双重条件回测结果")
    print(f"{'='*60}\n")
    
    print(f"总候选数: {len(candidates)}")
    print(f"策略分过滤: {filtered_strategy} 个")
    print(f"入场分过滤: {filtered_entry} 个")
    print(f"实际入场: {len(results)} 个")
    print(f"总过滤率: {(filtered_strategy + filtered_entry) / len(candidates) * 100:.2f}%\n")
    
    if results:
        win_count = sum(1 for r in results if r['win'])
        win_rate = win_count / len(results) * 100
        
        profits = [r['profit_pct'] for r in results]
        avg_profit = sum(profits) / len(profits)
        max_profit = max(profits)
        max_loss = min(profits)
        
        print(f"胜率: {win_rate:.2f}%")
        print(f"平均收益: {avg_profit:.2f}%")
        print(f"最大盈利: {max_profit:.2f}%")
        print(f"最大亏损: {max_loss:.2f}%")
        
        # 场景分布
        from collections import Counter
        scenario_dist = Counter([r['scenario'] for r in results])
        print(f"\n场景分布:")
        for scenario, count in scenario_dist.items():
            print(f"  {scenario}: {count} 个")
        
        # 出场原因分布
        exit_dist = Counter([r['exit_reason'] for r in results])
        print(f"\n出场原因:")
        for reason, count in exit_dist.items():
            print(f"  {reason}: {count} 个")
    else:
        print("无符合条件的入场案例")
    
    print(f"\n{'='*60}\n")
    
    # 保存结果
    output_file = Path.home() / '.hermes' / 'state' / 'qmt' / 'dual_condition_backtest_results.json'
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'total_candidates': len(candidates),
        'filtered_by_strategy': filtered_strategy,
        'filtered_by_entry': filtered_entry,
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"详细结果已保存到: {output_file}\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='双重条件回测')
    parser.add_argument('--days', type=int, default=30, help='回溯天数（默认30）')
    parser.add_argument('--max-cases', type=int, default=200, help='最大测试案例数（默认200）')
    
    args = parser.parse_args()
    
    run_dual_condition_backtest(days=args.days, max_cases=args.max_cases)

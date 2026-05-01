#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
涨停板回测脚本
从历史涨停板数据中提取候选，验证新评分体系
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
from lib.entry_timing.backtest import BacktestEngine


def get_limit_up_candidates(fetcher: TushareDataFetcher, days: int = 30) -> List[Tuple[str, str]]:
    """
    获取历史涨停板股票作为候选
    
    Args:
        fetcher: 数据获取器
        days: 回溯天数
    
    Returns:
        [(ts_code, entry_date), ...]
    """
    candidates = []
    
    # 获取最近N天的交易日
    trade_dates = fetcher.get_recent_trade_dates(days)
    
    print(f"扫描最近 {len(trade_dates)} 个交易日的涨停板数据...")
    
    for trade_date in trade_dates:
        try:
            # 获取当日涨停板
            limit_dict = fetcher.get_limit_list(trade_date)
            
            if not limit_dict:
                continue
            
            print(f"  {trade_date}: {len(limit_dict)} 只涨停股")
            
            # 筛选：排除ST、新股、一字板
            for ts_code, limit_data in limit_dict.items():
                name = limit_data.get('name', '')
                
                # 排除ST
                if 'ST' in name or 'st' in name:
                    continue
                
                # 排除一字板（开盘即涨停）
                open_pct = limit_data.get('open', 0)
                if open_pct >= 9.5:  # 接近涨停价开盘
                    continue
                
                candidates.append((ts_code, trade_date))
        
        except Exception as e:
            print(f"  跳过 {trade_date}: {e}")
            continue
    
    print(f"\n共提取 {len(candidates)} 个候选案例（排除ST和一字板）")
    return candidates


def run_limit_up_backtest(days: int = 30, max_cases: int = 50):
    """
    执行涨停板回测
    
    Args:
        days: 回溯天数
        max_cases: 最大测试案例数
    """
    # 检查环境变量
    if not os.environ.get('TUSHARE_TOKEN'):
        print("错误: 未设置 TUSHARE_TOKEN 环境变量")
        return
    
    fetcher = TushareDataFetcher()
    
    # 获取候选
    candidates = get_limit_up_candidates(fetcher, days)
    
    if not candidates:
        print("未找到候选数据")
        return
    
    # 限制测试数量（避免API限流）
    if len(candidates) > max_cases:
        print(f"限制测试数量为 {max_cases} 个（从 {len(candidates)} 个中随机抽样）")
        import random
        candidates = random.sample(candidates, max_cases)
    
    # 执行回测
    engine = BacktestEngine(fetcher)
    
    print(f"\n{'='*60}")
    print(f"开始批量回测 - 共 {len(candidates)} 个案例")
    print(f"{'='*60}\n")
    
    comparison = engine.compare_strategies(candidates)
    
    # 打印结果
    print(f"\n{'='*60}")
    print("回测结果汇总")
    print(f"{'='*60}\n")
    
    print("原策略（次日开盘买入）:")
    orig = comparison['original']
    print(f"  总案例数: {orig['total']}")
    print(f"  盈利案例: {orig['win_count']}")
    print(f"  胜率: {orig['win_rate']:.2f}%")
    print(f"  平均收益: {orig['avg_profit']:.2f}%")
    print(f"  最大盈利: {orig['max_profit']:.2f}%")
    print(f"  最大亏损: {orig['max_loss']:.2f}%")
    
    print("\n优化策略（止跌信号入场）:")
    opt = comparison['optimized']
    print(f"  总案例数: {opt['total']}")
    print(f"  盈利案例: {opt['win_count']}")
    print(f"  胜率: {opt['win_rate']:.2f}%")
    print(f"  平均收益: {opt['avg_profit']:.2f}%")
    print(f"  最大盈利: {opt['max_profit']:.2f}%")
    print(f"  最大亏损: {opt['max_loss']:.2f}%")
    print(f"  跳过案例: {comparison['skipped_count']} (无止跌信号)")
    
    print("\n改进幅度:")
    imp = comparison['improvement']
    print(f"  胜率提升: {imp['win_rate']:+.2f}%")
    print(f"  平均收益提升: {imp['avg_profit']:+.2f}%")
    
    # 假信号率分析
    if opt['total'] > 0:
        false_signal_rate = (opt['total'] - opt['win_count']) / opt['total'] * 100
        print(f"\n假信号率: {false_signal_rate:.2f}% (入场后亏损的比例)")
    
    # 信号过滤效果
    if orig['total'] > 0:
        filter_rate = comparison['skipped_count'] / (opt['total'] + comparison['skipped_count']) * 100
        print(f"信号过滤率: {filter_rate:.2f}% (拒绝入场的比例)")
    
    # 保存结果
    output_file = Path.home() / '.hermes' / 'state' / 'qmt' / 'limit_up_backtest_results.json'
    result_data = {
        'timestamp': datetime.now().isoformat(),
        'test_period_days': days,
        'test_cases_count': len(candidates),
        'comparison': comparison
    }
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {output_file}")
    print(f"\n{'='*60}\n")
    
    return comparison


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='涨停板回测')
    parser.add_argument('--days', type=int, default=30, help='回溯天数（默认30）')
    parser.add_argument('--max-cases', type=int, default=50, help='最大测试案例数（默认50）')
    
    args = parser.parse_args()
    
    run_limit_up_backtest(days=args.days, max_cases=args.max_cases)

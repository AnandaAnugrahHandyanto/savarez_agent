#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量回测脚本
用近1个月历史数据验证新评分体系
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from lib.entry_timing.data_fetcher import TushareDataFetcher
from lib.entry_timing.backtest import BacktestEngine


def load_historical_candidates(days: int = 30) -> List[Tuple[str, str]]:
    """
    从历史推送记录中提取候选股票
    
    Args:
        days: 回溯天数
    
    Returns:
        [(ts_code, entry_date), ...]
    """
    candidates = []
    state_dir = Path.home() / '.hermes' / 'state' / 'qmt'
    
    if not state_dir.exists():
        print(f"警告: 状态目录不存在 {state_dir}")
        return []
    
    # 获取最近N天的交易日
    fetcher = TushareDataFetcher()
    trade_dates = fetcher.get_recent_trade_dates(days)
    
    print(f"扫描最近 {len(trade_dates)} 个交易日的推送记录...")
    
    for trade_date in trade_dates:
        # 查找该日期的推送文件
        snapshot_file = state_dir / f"intraday_snapshot_{trade_date}.json"
        
        if not snapshot_file.exists():
            continue
        
        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取候选股票
            pool = data.get('strategy_candidate_pool', [])
            for item in pool:
                ts_code = item.get('code')
                action = item.get('final_action')
                
                # 只取"主攻"和"备选"
                if ts_code and action in ['主攻', '备选']:
                    candidates.append((ts_code, trade_date))
        
        except Exception as e:
            print(f"  跳过 {trade_date}: {e}")
            continue
    
    print(f"共提取 {len(candidates)} 个候选案例")
    return candidates


def run_batch_backtest(test_cases: List[Tuple[str, str]], output_file: str = None):
    """
    批量回测
    
    Args:
        test_cases: [(ts_code, entry_date), ...]
        output_file: 输出文件路径（可选）
    """
    fetcher = TushareDataFetcher()
    engine = BacktestEngine(fetcher)
    
    print(f"\n{'='*60}")
    print(f"开始批量回测 - 共 {len(test_cases)} 个案例")
    print(f"{'='*60}\n")
    
    # 执行对比回测
    comparison = engine.compare_strategies(test_cases)
    
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
    
    # 保存结果
    if output_file:
        result_data = {
            'timestamp': datetime.now().isoformat(),
            'test_cases_count': len(test_cases),
            'comparison': comparison
        }
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n结果已保存到: {output_path}")
    
    print(f"\n{'='*60}\n")
    
    return comparison


def main():
    """主函数"""
    # 检查环境变量
    if not os.environ.get('TUSHARE_TOKEN'):
        print("错误: 未设置 TUSHARE_TOKEN 环境变量")
        print("请运行: export TUSHARE_TOKEN='your_token'")
        return
    
    # 加载历史候选
    test_cases = load_historical_candidates(days=30)
    
    if not test_cases:
        print("未找到历史候选数据，使用示例数据进行测试...")
        # 使用一些示例数据
        test_cases = [
            ('002580.SZ', '20260421'),
            ('002192.SZ', '20260422'),
            ('300502.SZ', '20260423'),
        ]
    
    # 执行回测
    output_file = Path.home() / '.hermes' / 'state' / 'qmt' / 'backtest_results.json'
    run_batch_backtest(test_cases, str(output_file))


if __name__ == '__main__':
    main()

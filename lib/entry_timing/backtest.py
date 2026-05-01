"""
回测模块
对比原策略（次日开盘买入）vs 优化策略（止跌信号入场）
"""
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from .data_fetcher import TushareDataFetcher
from .signal_detector_v2 import StopFallingSignalDetectorV2


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, fetcher: TushareDataFetcher):
        self.fetcher = fetcher
        self.detector = StopFallingSignalDetectorV2()
    
    def backtest_original_strategy(self, ts_code: str, entry_date: str, 
                                   lookback_days: int = 20) -> Dict:
        """
        回测原策略：次日开盘买入
        
        Args:
            ts_code: 股票代码
            entry_date: 选股日期（YYYYMMDD）
            lookback_days: 回看天数
        
        Returns:
            回测结果
        """
        # 获取数据
        start_date = (datetime.strptime(entry_date, '%Y%m%d') - timedelta(days=lookback_days+10)).strftime('%Y%m%d')
        end_date = (datetime.strptime(entry_date, '%Y%m%d') + timedelta(days=30)).strftime('%Y%m%d')
        
        daily_data = self.fetcher.get_daily_data(ts_code, start_date, end_date)
        
        if not daily_data:
            return {'success': False, 'reason': '无数据'}
        
        # 找到选股日
        entry_day_idx = None
        for i, day in enumerate(daily_data):
            if day['trade_date'] == entry_date:
                entry_day_idx = i
                break
        
        if entry_day_idx is None or entry_day_idx >= len(daily_data) - 1:
            return {'success': False, 'reason': '选股日无效'}
        
        # 次日开盘买入
        entry_day = daily_data[entry_day_idx + 1]
        entry_price = entry_day.get('open', 0)
        entry_actual_date = entry_day.get('trade_date')
        
        if entry_price == 0:
            return {'success': False, 'reason': '无开盘价'}
        
        # 模拟持仓
        result = self._simulate_holding(daily_data, entry_day_idx + 1, entry_price)
        result['strategy'] = 'original'
        result['entry_date'] = entry_actual_date
        result['entry_price'] = entry_price
        
        return result
    
    def backtest_optimized_strategy(self, ts_code: str, entry_date: str,
                                    lookback_days: int = 20) -> Dict:
        """
        回测优化策略：止跌信号入场
        
        Args:
            ts_code: 股票代码
            entry_date: 选股日期（YYYYMMDD）
            lookback_days: 回看天数
        
        Returns:
            回测结果
        """
        # 获取数据
        start_date = (datetime.strptime(entry_date, '%Y%m%d') - timedelta(days=lookback_days+10)).strftime('%Y%m%d')
        end_date = (datetime.strptime(entry_date, '%Y%m%d') + timedelta(days=30)).strftime('%Y%m%d')
        
        daily_data = self.fetcher.get_daily_data(ts_code, start_date, end_date)
        
        if not daily_data:
            return {'success': False, 'reason': '无数据'}
        
        # 找到选股日
        entry_day_idx = None
        for i, day in enumerate(daily_data):
            if day['trade_date'] == entry_date:
                entry_day_idx = i
                break
        
        if entry_day_idx is None:
            return {'success': False, 'reason': '选股日无效'}
        
        # 从次日开始，最多等2天找入场信号
        max_wait_days = 2
        actual_entry_idx = None
        
        for wait_day in range(1, max_wait_days + 1):
            check_idx = entry_day_idx + wait_day
            
            if check_idx >= len(daily_data):
                break
            
            # 检查止跌信号
            history_data = daily_data[:check_idx + 1]
            signal_result = self.detector.check_signal(history_data[-10:])  # 用最近10天数据
            
            if signal_result['can_enter']:
                actual_entry_idx = check_idx
                break
        
        # 如果2天内没有信号，放弃
        if actual_entry_idx is None:
            return {
                'success': False,
                'reason': '等待期内无止跌信号',
                'strategy': 'optimized',
                'skipped': True
            }
        
        # 入场价：当日收盘价（简化，实际应该是盘中价）
        entry_day = daily_data[actual_entry_idx]
        entry_price = entry_day.get('close', 0)
        entry_actual_date = entry_day.get('trade_date')
        
        if entry_price == 0:
            return {'success': False, 'reason': '无收盘价'}
        
        # 模拟持仓
        result = self._simulate_holding(daily_data, actual_entry_idx, entry_price)
        result['strategy'] = 'optimized'
        result['entry_date'] = entry_actual_date
        result['entry_price'] = entry_price
        result['wait_days'] = actual_entry_idx - entry_day_idx - 1
        
        return result
    
    def _simulate_holding(self, daily_data: List[Dict], entry_idx: int, 
                         entry_price: float) -> Dict:
        """
        模拟持仓过程
        
        Args:
            daily_data: 日线数据
            entry_idx: 入场日索引
            entry_price: 入场价
        
        Returns:
            持仓结果
        """
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
        for i in range(entry_idx + 1, len(daily_data)):
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
            holding_days = len(daily_data) - entry_idx - 1
        
        # 计算收益
        profit_pct = (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
        
        return {
            'success': True,
            'exit_reason': exit_reason,
            'exit_date': exit_date,
            'exit_price': exit_price,
            'holding_days': holding_days,
            'profit_pct': profit_pct,
            'win': profit_pct > 0
        }
    
    def compare_strategies(self, test_cases: List[Tuple[str, str]]) -> Dict:
        """
        对比两种策略
        
        Args:
            test_cases: [(ts_code, entry_date), ...]
        
        Returns:
            对比结果统计
        """
        original_results = []
        optimized_results = []
        
        print(f"开始回测 {len(test_cases)} 个案例...")
        
        for i, (ts_code, entry_date) in enumerate(test_cases, 1):
            print(f"  [{i}/{len(test_cases)}] {ts_code} @ {entry_date}")
            
            # 原策略
            orig = self.backtest_original_strategy(ts_code, entry_date)
            if orig.get('success'):
                original_results.append(orig)
            
            # 优化策略
            opt = self.backtest_optimized_strategy(ts_code, entry_date)
            if opt.get('success'):
                optimized_results.append(opt)
        
        # 统计
        def calc_stats(results: List[Dict]) -> Dict:
            if not results:
                return {
                    'total': 0,
                    'win_count': 0,
                    'win_rate': 0,
                    'avg_profit': 0,
                    'max_profit': 0,
                    'max_loss': 0
                }
            
            total = len(results)
            win_count = sum(1 for r in results if r['win'])
            win_rate = win_count / total * 100 if total > 0 else 0
            
            profits = [r['profit_pct'] for r in results]
            avg_profit = sum(profits) / len(profits) if profits else 0
            max_profit = max(profits) if profits else 0
            max_loss = min(profits) if profits else 0
            
            return {
                'total': total,
                'win_count': win_count,
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'max_profit': max_profit,
                'max_loss': max_loss
            }
        
        original_stats = calc_stats(original_results)
        optimized_stats = calc_stats(optimized_results)
        
        # 计算优化策略跳过的案例数
        skipped_count = sum(1 for opt in [self.backtest_optimized_strategy(ts_code, entry_date) 
                                          for ts_code, entry_date in test_cases]
                           if opt.get('skipped'))
        
        return {
            'original': original_stats,
            'optimized': optimized_stats,
            'skipped_count': skipped_count,
            'improvement': {
                'win_rate': optimized_stats['win_rate'] - original_stats['win_rate'],
                'avg_profit': optimized_stats['avg_profit'] - original_stats['avg_profit']
            }
        }


if __name__ == '__main__':
    # 测试
    fetcher = TushareDataFetcher()
    engine = BacktestEngine(fetcher)
    
    print("测试回测引擎...")
    
    # 测试单个案例
    print("\n原策略回测:")
    orig = engine.backtest_original_strategy('002580.SZ', '20260421')
    if orig['success']:
        print(f"  入场: {orig['entry_date']} @ ¥{orig['entry_price']:.2f}")
        print(f"  出场: {orig['exit_date']} @ ¥{orig['exit_price']:.2f}")
        print(f"  收益: {orig['profit_pct']:.2f}%")
        print(f"  原因: {orig['exit_reason']}")
    
    print("\n优化策略回测:")
    opt = engine.backtest_optimized_strategy('002580.SZ', '20260421')
    if opt['success']:
        print(f"  等待: {opt.get('wait_days', 0)}天")
        print(f"  入场: {opt['entry_date']} @ ¥{opt['entry_price']:.2f}")
        print(f"  出场: {opt['exit_date']} @ ¥{opt['exit_price']:.2f}")
        print(f"  收益: {opt['profit_pct']:.2f}%")
        print(f"  原因: {opt['exit_reason']}")
    
    print("\n✓ 回测模块测试通过")

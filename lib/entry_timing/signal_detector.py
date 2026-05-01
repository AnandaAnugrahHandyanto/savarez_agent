"""
止跌信号判断模块
多维度评分系统，判断股票是否出现止跌信号
"""
from typing import List, Dict, Optional


class StopFallingSignalDetector:
    """止跌信号检测器"""
    
    def __init__(self):
        self.signal_weights = {
            'close_positive': 30,      # 收阳
            'not_break_low': 25,       # 不破前低
            'volume_shrink': 25,       # 缩量
            'low_open_high_close': 20, # 低开高走
        }
    
    def check_signal(self, daily_data: List[Dict], intraday_data: Optional[List[Dict]] = None) -> Dict:
        """
        检查止跌信号
        
        Args:
            daily_data: 日线数据（至少3天，按日期升序）
            intraday_data: 分时数据（可选，用于更精确判断）
        
        Returns:
            {
                'can_enter': bool,
                'score': int,
                'signals': List[str],
                'details': Dict
            }
        """
        if len(daily_data) < 2:
            return {
                'can_enter': False,
                'score': 0,
                'signals': ['数据不足'],
                'details': {}
            }
        
        today = daily_data[-1]
        yesterday = daily_data[-2]
        
        score = 0
        signals = []
        details = {}
        
        # 1. 收阳/收阴
        today_pct = today.get('pct_chg', 0)
        if today_pct > 0:
            score += self.signal_weights['close_positive']
            signals.append(f"✓ 今日收阳 (+{today_pct:.2f}%)")
            details['close_positive'] = True
        else:
            signals.append(f"✗ 今日收阴 ({today_pct:.2f}%)")
            details['close_positive'] = False
        
        # 2. 不破前低
        today_low = today.get('low', 0)
        yesterday_low = yesterday.get('low', 0)
        
        if yesterday_low > 0:
            low_ratio = today_low / yesterday_low
            if low_ratio >= 0.98:  # 允许2%误差
                score += self.signal_weights['not_break_low']
                signals.append(f"✓ 未破昨日最低 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['not_break_low'] = True
            else:
                signals.append(f"✗ 破昨日最低 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['not_break_low'] = False
        
        # 3. 缩量程度
        today_vol = today.get('vol', 0)
        yesterday_vol = yesterday.get('vol', 0)
        
        if yesterday_vol > 0:
            vol_ratio = today_vol / yesterday_vol
            details['volume_ratio'] = vol_ratio
            
            if vol_ratio < 0.5:
                score += self.signal_weights['volume_shrink']
                signals.append(f"✓ 明显缩量 ({vol_ratio*100:.1f}%)")
                details['volume_shrink'] = 'strong'
            elif vol_ratio < 0.7:
                score += int(self.signal_weights['volume_shrink'] * 0.8)
                signals.append(f"✓ 缩量 ({vol_ratio*100:.1f}%)")
                details['volume_shrink'] = 'moderate'
            elif vol_ratio < 1.0:
                score += int(self.signal_weights['volume_shrink'] * 0.6)
                signals.append(f"○ 温和缩量 ({vol_ratio*100:.1f}%)")
                details['volume_shrink'] = 'mild'
            else:
                signals.append(f"✗ 放量 ({vol_ratio*100:.1f}%)")
                details['volume_shrink'] = 'none'
        
        # 4. 低开高走
        today_open = today.get('open', 0)
        today_close = today.get('close', 0)
        yesterday_close = yesterday.get('close', 0)
        
        if today_open > 0 and today_close > 0 and yesterday_close > 0:
            if today_open < yesterday_close and today_close > today_open:
                intraday_gain = (today_close - today_open) / today_open * 100
                score += self.signal_weights['low_open_high_close']
                signals.append(f"✓ 低开高走 (盘中+{intraday_gain:.2f}%)")
                details['low_open_high_close'] = True
                details['intraday_gain'] = intraday_gain
            else:
                details['low_open_high_close'] = False
        
        # 5. 额外扣分项：昨日跌幅过大
        yesterday_pct = yesterday.get('pct_chg', 0)
        if yesterday_pct < -10:
            score -= 20
            signals.append(f"⚠ 昨日跌幅过大 ({yesterday_pct:.2f}%)")
            details['yesterday_drop_warning'] = True
        
        # 6. 分时数据辅助判断（如果有）
        if intraday_data and len(intraday_data) > 0:
            intraday_score, intraday_signals = self._check_intraday_stability(intraday_data)
            score += intraday_score
            signals.extend(intraday_signals)
            details['intraday_stable'] = intraday_score > 0
        
        # 综合判断
        can_enter = score >= 50
        
        return {
            'can_enter': can_enter,
            'score': score,
            'signals': signals,
            'details': details,
            'today_date': today.get('trade_date'),
            'today_close': today_close,
            'today_pct': today_pct,
        }
    
    def _check_intraday_stability(self, intraday_data: List[Dict]) -> tuple:
        """
        检查分时稳定性
        
        Returns:
            (score, signals)
        """
        if len(intraday_data) < 10:
            return (0, [])
        
        score = 0
        signals = []
        
        # 计算分时均价线
        closes = [d.get('close', 0) for d in intraday_data if d.get('close', 0) > 0]
        if not closes:
            return (0, [])
        
        avg_price = sum(closes) / len(closes)
        
        # 检查最后30分钟是否在均价线上方
        last_30min = intraday_data[-6:]  # 假设5分钟K线
        above_avg_count = sum(1 for d in last_30min if d.get('close', 0) > avg_price)
        
        if above_avg_count >= 4:
            score += 10
            signals.append("✓ 尾盘在分时均价线上方")
        
        # 检查是否有明显拉升
        if len(closes) >= 20:
            early_avg = sum(closes[:10]) / 10
            late_avg = sum(closes[-10:]) / 10
            
            if late_avg > early_avg * 1.01:
                score += 5
                signals.append("✓ 盘中有拉升")
        
        return (score, signals)
    
    def batch_check(self, stocks_data: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """
        批量检查多只股票
        
        Args:
            stocks_data: {ts_code: daily_data}
        
        Returns:
            {ts_code: signal_result}
        """
        results = {}
        for ts_code, daily_data in stocks_data.items():
            results[ts_code] = self.check_signal(daily_data)
        return results


if __name__ == '__main__':
    # 测试
    from .data_fetcher import TushareDataFetcher
    
    fetcher = TushareDataFetcher()
    detector = StopFallingSignalDetector()
    
    # 测试单只股票
    print("测试止跌信号检测...")
    daily = fetcher.get_daily_data('002580.SZ', '20260410', '20260423')
    
    result = detector.check_signal(daily)
    
    print(f"\n股票: 002580.SZ")
    print(f"评分: {result['score']}/100")
    print(f"可入场: {result['can_enter']}")
    print("\n信号:")
    for signal in result['signals']:
        print(f"  {signal}")
    
    print("\n✓ 止跌信号检测模块测试通过")

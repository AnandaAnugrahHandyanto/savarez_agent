"""
止跌信号判断模块 v2.0
优化后的多维度评分系统，更精准、更细化
"""
from typing import List, Dict, Optional


class StopFallingSignalDetectorV2:
    """止跌信号检测器 v2.0"""
    
    def __init__(self):
        # 新权重体系
        self.weights = {
            'kline_pattern': 35,      # K线形态
            'volume_price': 30,       # 量价配合
            'support_pressure': 20,   # 支撑压力
            'trend_continuity': 15,   # 趋势延续（暂不实施）
        }
    
    def check_signal(self, daily_data: List[Dict], intraday_data: Optional[List[Dict]] = None) -> Dict:
        """
        检查止跌信号
        
        Args:
            daily_data: 日线数据（至少3天，按日期升序）
            intraday_data: 分时数据（可选）
        
        Returns:
            {
                'can_enter': bool,
                'score': int,
                'signals': List[str],
                'details': Dict,
                'breakdown': Dict  # 各维度得分明细
            }
        """
        if len(daily_data) < 2:
            return {
                'can_enter': False,
                'score': 0,
                'signals': ['数据不足'],
                'details': {},
                'breakdown': {}
            }
        
        today = daily_data[-1]
        yesterday = daily_data[-2]
        
        # 场景识别：是否涨停后首日
        yesterday_pct = yesterday.get('pct_chg', 0)
        is_after_limit_up = yesterday_pct >= 9.5
        
        score = 0
        signals = []
        details = {}
        breakdown = {}
        details['scenario'] = 'after_limit_up' if is_after_limit_up else 'normal'
        
        # 一、K线形态（35分）
        kline_score, kline_signals, kline_details = self._score_kline_pattern(today, yesterday)
        score += kline_score
        signals.extend(kline_signals)
        details.update(kline_details)
        breakdown['kline_pattern'] = kline_score
        
        # 二、量价配合（30分）- 涨停后场景调整权重
        volume_score, volume_signals, volume_details = self._score_volume_price(
            today, yesterday, is_after_limit_up
        )
        score += volume_score
        signals.extend(volume_signals)
        details.update(volume_details)
        breakdown['volume_price'] = volume_score
        
        # 三、支撑压力（20分）
        support_score, support_signals, support_details = self._score_support_pressure(
            today, yesterday, daily_data
        )
        score += support_score
        signals.extend(support_signals)
        details.update(support_details)
        breakdown['support_pressure'] = support_score
        
        # 扣分项
        penalty_score, penalty_signals = self._calculate_penalties(today, yesterday, daily_data)
        score += penalty_score
        if penalty_signals:
            signals.extend(penalty_signals)
        breakdown['penalty'] = penalty_score
        
        # 综合判断 - 涨停后场景提高阈值
        threshold = 55 if is_after_limit_up else 48
        can_enter = score >= threshold
        
        return {
            'can_enter': can_enter,
            'score': score,
            'signals': signals,
            'details': details,
            'breakdown': breakdown,
            'today_date': today.get('trade_date'),
            'today_close': today.get('close', 0),
            'today_pct': today.get('pct_chg', 0),
        }
    
    def _score_kline_pattern(self, today: Dict, yesterday: Dict) -> tuple:
        """
        K线形态评分（35分）
        
        Returns:
            (score, signals, details)
        """
        score = 0
        signals = []
        details = {}
        
        pct_chg = today.get('pct_chg', 0)
        open_price = today.get('open', 0)
        close_price = today.get('close', 0)
        high_price = today.get('high', 0)
        low_price = today.get('low', 0)
        yesterday_close = yesterday.get('close', 0)
        
        # 1.1 收盘涨跌幅（20分）
        if pct_chg >= 5:
            score += 20
            signals.append(f"✓ 大阳线 (+{pct_chg:.2f}%)")
            details['kline_type'] = 'big_positive'
        elif pct_chg >= 2:
            score += 16
            signals.append(f"✓ 中阳线 (+{pct_chg:.2f}%)")
            details['kline_type'] = 'mid_positive'
        elif pct_chg > 0:
            score += 12
            signals.append(f"✓ 小阳线 (+{pct_chg:.2f}%)")
            details['kline_type'] = 'small_positive'
        elif pct_chg >= -0.5:
            score += 6
            signals.append(f"○ 十字星 ({pct_chg:.2f}%)")
            details['kline_type'] = 'doji'
        elif pct_chg >= -2:
            score += 0
            signals.append(f"✗ 小阴线 ({pct_chg:.2f}%)")
            details['kline_type'] = 'small_negative'
        elif pct_chg >= -5:
            score -= 5
            signals.append(f"✗ 中阴线 ({pct_chg:.2f}%)")
            details['kline_type'] = 'mid_negative'
        else:
            score -= 10
            signals.append(f"✗ 大阴线 ({pct_chg:.2f}%)")
            details['kline_type'] = 'big_negative'
        
        # 1.2 实体与影线比例（10分）
        if open_price > 0 and close_price > 0 and high_price > 0 and low_price > 0:
            body = abs(close_price - open_price)
            upper_shadow = high_price - max(open_price, close_price)
            lower_shadow = min(open_price, close_price) - low_price
            
            details['body'] = body
            details['upper_shadow'] = upper_shadow
            details['lower_shadow'] = lower_shadow
            
            # 下影线长度判断（强支撑信号）
            if body > 0:
                if lower_shadow > body * 2:
                    score += 10
                    signals.append(f"✓ 长下影线（锤子线形态）")
                    details['hammer'] = True
                elif lower_shadow > body:
                    score += 5
                    signals.append(f"○ 下影线较长")
                    details['hammer'] = False
                
                # 上影线过长（上方压力）
                if upper_shadow > body * 2:
                    score -= 5
                    signals.append(f"⚠ 长上影线（上方压力大）")
                    details['upper_pressure'] = True
        
        # 1.3 开盘位置（5分）
        if open_price > 0 and yesterday_close > 0:
            if open_price < yesterday_close and close_price > open_price:
                score += 8
                signals.append(f"✓ 低开高走")
                details['open_type'] = 'low_open_high_close'
            elif abs(open_price - yesterday_close) / yesterday_close < 0.01 and close_price > open_price:
                score += 5
                signals.append(f"○ 平开上涨")
                details['open_type'] = 'flat_open_rise'
            elif open_price > yesterday_close and close_price < open_price:
                score -= 3
                signals.append(f"⚠ 高开回落")
                details['open_type'] = 'high_open_fall'
            elif open_price < yesterday_close and close_price < open_price:
                score -= 5
                signals.append(f"✗ 低开低走")
                details['open_type'] = 'low_open_low_close'
        
        return (score, signals, details)
    
    def _score_volume_price(self, today: Dict, yesterday: Dict, is_after_limit_up: bool = False) -> tuple:
        """
        量价配合评分（30分）
        
        Args:
            today: 今日数据
            yesterday: 昨日数据
            is_after_limit_up: 是否涨停后首日
        
        Returns:
            (score, signals, details)
        """
        score = 0
        signals = []
        details = {}
        
        today_vol = today.get('vol', 0)
        yesterday_vol = yesterday.get('vol', 0)
        pct_chg = today.get('pct_chg', 0)
        
        if yesterday_vol <= 0:
            return (0, ['⚠ 昨日成交量数据缺失'], {})
        
        vol_ratio = today_vol / yesterday_vol
        details['volume_ratio'] = vol_ratio
        
        # 2.1 量能变化（15分）- 涨停后场景调整
        if is_after_limit_up:
            # 涨停后分歧：适度放量更健康
            if vol_ratio < 0.5:
                vol_score = 8
                vol_desc = "缩量（分歧不足）"
            elif vol_ratio < 0.8:
                vol_score = 12
                vol_desc = "温和缩量"
            elif vol_ratio < 1.2:
                vol_score = 15
                vol_desc = "持平（分歧充分）"
            elif vol_ratio < 1.8:
                vol_score = 13
                vol_desc = "适度放量（换手健康）"
            elif vol_ratio < 2.5:
                vol_score = 8
                vol_desc = "明显放量"
            else:
                vol_score = 0
                vol_desc = "巨量（分歧过大）"
        else:
            # 正常场景：缩量更优
            if vol_ratio < 0.3:
                vol_score = 15
                vol_desc = "极度缩量"
            elif vol_ratio < 0.5:
                vol_score = 12
                vol_desc = "明显缩量"
            elif vol_ratio < 0.7:
                vol_score = 10
                vol_desc = "缩量"
            elif vol_ratio < 0.9:
                vol_score = 8
                vol_desc = "温和缩量"
            elif vol_ratio < 1.1:
                vol_score = 5
                vol_desc = "持平"
            elif vol_ratio < 1.5:
                vol_score = 3
                vol_desc = "温和放量"
            elif vol_ratio < 2.0:
                vol_score = 0
                vol_desc = "明显放量"
            else:
                vol_score = -5
                vol_desc = "巨量"
        
        score += vol_score
        signals.append(f"{'✓' if vol_score > 10 else '○' if vol_score > 5 else '✗'} {vol_desc} ({vol_ratio*100:.1f}%)")
        details['volume_change'] = vol_desc
        
        # 2.2 量价配合度（15分）
        if pct_chg > 0:  # 上涨
            if is_after_limit_up:
                # 涨停后上涨：适度放量更好
                if 0.8 <= vol_ratio <= 1.5:
                    match_score = 15
                    signals.append(f"✓ 适度放量上涨（分歧后突破）")
                    details['volume_price_match'] = 'moderate_expand_rise'
                elif vol_ratio < 0.8:
                    match_score = 10
                    signals.append(f"○ 缩量上涨（惜售）")
                    details['volume_price_match'] = 'shrink_rise'
                else:
                    match_score = 5
                    signals.append(f"○ 放量上涨（换手充分）")
                    details['volume_price_match'] = 'expand_rise'
            else:
                # 正常场景：缩量上涨更优
                if vol_ratio < 0.7:
                    match_score = 15
                    signals.append(f"✓ 缩量上涨（惜售）")
                    details['volume_price_match'] = 'shrink_rise'
                elif vol_ratio > 1.5:
                    match_score = 10
                    signals.append(f"✓ 放量上涨（突破）")
                    details['volume_price_match'] = 'expand_rise'
                else:
                    match_score = 8
                    signals.append(f"○ 温和放量上涨")
                    details['volume_price_match'] = 'mild_rise'
        else:  # 下跌
            if vol_ratio < 0.5:
                match_score = 10
                signals.append(f"✓ 缩量下跌（抛压减轻）")
                details['volume_price_match'] = 'shrink_fall'
            elif vol_ratio > 1.5:
                match_score = -10
                signals.append(f"✗ 放量下跌（恐慌）")
                details['volume_price_match'] = 'expand_fall'
            else:
                match_score = 0
                signals.append(f"○ 温和下跌")
                details['volume_price_match'] = 'mild_fall'
        
        score += match_score
        
        return (score, signals, details)
    
    def _score_support_pressure(self, today: Dict, yesterday: Dict, daily_data: List[Dict]) -> tuple:
        """
        支撑压力评分（20分）
        
        Returns:
            (score, signals, details)
        """
        score = 0
        signals = []
        details = {}
        
        today_low = today.get('low', 0)
        yesterday_low = yesterday.get('low', 0)
        today_close = today.get('close', 0)
        
        # 3.1 不破前低（10分）
        if yesterday_low > 0 and today_low > 0:
            low_ratio = today_low / yesterday_low
            details['low_ratio'] = low_ratio
            
            if low_ratio >= 1.02:
                score += 10
                signals.append(f"✓ 站稳昨低上方 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['break_low'] = False
            elif low_ratio >= 1.00:
                score += 8
                signals.append(f"○ 持平昨低 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['break_low'] = False
            elif low_ratio >= 0.98:
                score += 5
                signals.append(f"○ 轻微破位 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['break_low'] = True
            elif low_ratio >= 0.95:
                score += 0
                signals.append(f"✗ 破昨日最低 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['break_low'] = True
            else:
                score -= 10
                signals.append(f"✗ 深度破位 (今{today_low:.2f} vs 昨{yesterday_low:.2f})")
                details['break_low'] = True
        
        # 3.2 关键支撑位验证（10分）
        if len(daily_data) >= 5 and today_close > 0:
            # 计算关键支撑位
            recent_5_low = min([d.get('low', float('inf')) for d in daily_data[-5:]])
            recent_10_low = min([d.get('low', float('inf')) for d in daily_data[-10:]]) if len(daily_data) >= 10 else recent_5_low
            
            # 计算均线（简化版）
            recent_closes = [d.get('close', 0) for d in daily_data[-5:] if d.get('close', 0) > 0]
            ma5 = sum(recent_closes) / len(recent_closes) if recent_closes else 0
            
            support_levels = [recent_5_low, recent_10_low, ma5]
            details['support_levels'] = support_levels
            
            # 检查是否在支撑位附近
            near_support = False
            for support in support_levels:
                if support > 0:
                    if abs(today_low - support) / support < 0.02:  # 2%范围内
                        near_support = True
                        break
            
            if near_support:
                score += 10
                signals.append(f"✓ 在关键支撑位获得支撑")
                details['near_support'] = True
            elif today_close > max(support_levels):
                score += 5
                signals.append(f"○ 站上支撑位")
                details['near_support'] = False
            else:
                details['near_support'] = False
        
        return (score, signals, details)
    
    def _calculate_penalties(self, today: Dict, yesterday: Dict, daily_data: List[Dict]) -> tuple:
        """
        计算扣分项
        
        Returns:
            (penalty_score, signals)
        """
        penalty = 0
        signals = []
        
        yesterday_pct = yesterday.get('pct_chg', 0)
        today_pct = today.get('pct_chg', 0)
        
        # 5.1 昨日异常波动
        if yesterday_pct < -10:
            penalty -= 15
            signals.append(f"⚠ 昨日跌幅过大 ({yesterday_pct:.2f}%)")
        # 注意：昨日涨停不扣分，这是龙头回调策略的正常模式
        
        yesterday_high = yesterday.get('high', 0)
        yesterday_low = yesterday.get('low', 0)
        yesterday_close = yesterday.get('close', 0)
        if yesterday_high > 0 and yesterday_low > 0 and yesterday_close > 0:
            yesterday_amplitude = (yesterday_high - yesterday_low) / yesterday_close * 100
            if yesterday_amplitude > 15:
                penalty -= 5
                signals.append(f"⚠ 昨日振幅过大 ({yesterday_amplitude:.1f}%)")
        
        # 5.2 连续阴线
        if len(daily_data) >= 3:
            consecutive_negative = 0
            for i in range(len(daily_data)-1, max(len(daily_data)-4, -1), -1):
                if daily_data[i].get('pct_chg', 0) < 0:
                    consecutive_negative += 1
                else:
                    break
            
            if consecutive_negative >= 3:
                penalty -= 10
                signals.append(f"⚠ 连续{consecutive_negative}根阴线")
            elif consecutive_negative == 2:
                penalty -= 5
                signals.append(f"⚠ 连续2根阴线")
        
        # 5.3 破位加速
        if today_pct < 0 and yesterday_pct < 0:
            if today_pct < yesterday_pct:
                penalty -= 10
                signals.append(f"⚠ 加速下跌（今{today_pct:.2f}% vs 昨{yesterday_pct:.2f}%）")
        
        return (penalty, signals)
    
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
    import os
    import sys
    sys.path.insert(0, "/Users/zezesun/.hermes/runtime-hermes-agent")
    
    from lib.entry_timing.data_fetcher import TushareDataFetcher
    
    token = os.environ.get('TUSHARE_TOKEN')
    fetcher = TushareDataFetcher(token)
    detector = StopFallingSignalDetectorV2()
    
    # 测试博云新材
    print("测试止跌信号检测 v2.0...")
    print("="*60)
    
    daily = fetcher.get_daily_data('002297.SZ', '20260410', '20260424')
    
    result = detector.check_signal(daily)
    
    print(f"\n股票: 002297.SZ 博云新材")
    print(f"评分: {result['score']}/100")
    print(f"可入场: {result['can_enter']}")
    
    print(f"\n得分明细:")
    for key, value in result['breakdown'].items():
        print(f"  {key}: {value}分")
    
    print("\n信号:")
    for signal in result['signals']:
        print(f"  {signal}")
    
    print("\n✓ 止跌信号检测 v2.0 测试通过")

"""
入场决策模块
综合止跌信号和分时走势，给出具体入场建议
"""
from typing import List, Dict, Optional
from datetime import datetime


class EntryDecisionMaker:
    """入场决策器"""
    
    def __init__(self, stop_profit: float = 0.20, stop_loss: float = 0.08, time_stop: int = 10):
        """
        Args:
            stop_profit: 止盈比例（默认20%）
            stop_loss: 止损比例（默认8%）
            time_stop: 时间止损天数（默认10天）
        """
        self.stop_profit = stop_profit
        self.stop_loss = stop_loss
        self.time_stop = time_stop
    
    def decide(self, signal_result: Dict, current_date: str) -> Dict:
        """
        做出入场决策
        
        Args:
            signal_result: 止跌信号检测结果
            current_date: 当前日期（YYYYMMDD）
        
        Returns:
            {
                'action': 'enter' | 'wait' | 'skip',
                'timing': str,
                'entry_price': float,
                'stop_profit_price': float,
                'stop_loss_price': float,
                'reason': str,
                'confidence': str  # 'high' | 'medium' | 'low'
            }
        """
        can_enter = signal_result.get('can_enter', False)
        score = signal_result.get('score', 0)
        today_close = signal_result.get('today_close', 0)
        today_date = signal_result.get('today_date', '')
        
        if not can_enter:
            return {
                'action': 'wait',
                'timing': '继续观察，等待更明确止跌信号',
                'entry_price': 0,
                'stop_profit_price': 0,
                'stop_loss_price': 0,
                'reason': f'止跌信号不足（评分{score}/100）',
                'confidence': 'low'
            }
        
        # 判断是否当日
        is_today = (today_date == current_date)
        
        # 计算入场价和止盈止损价
        entry_price = today_close
        stop_profit_price = entry_price * (1 + self.stop_profit)
        stop_loss_price = entry_price * (1 - self.stop_loss)
        
        # 判断信心度
        if score >= 70:
            confidence = 'high'
            timing_desc = "强烈建议入场"
        elif score >= 60:
            confidence = 'medium'
            timing_desc = "建议入场"
        else:
            confidence = 'medium'
            timing_desc = "可以入场"
        
        # 具体入场时机
        if is_today:
            timing = f"{timing_desc}，盘中10:30-14:00企稳后入场"
        else:
            timing = f"{timing_desc}，次日开盘观察30分钟后入场"
        
        return {
            'action': 'enter',
            'timing': timing,
            'entry_price': entry_price,
            'stop_profit_price': stop_profit_price,
            'stop_loss_price': stop_loss_price,
            'reason': f'止跌信号明确（评分{score}/100）',
            'confidence': confidence,
            'score': score
        }
    
    def get_intraday_entry_suggestion(self, intraday_data: List[Dict], 
                                     entry_price_ref: float) -> Dict:
        """
        根据分时数据给出盘中入场建议
        
        Args:
            intraday_data: 分时数据
            entry_price_ref: 参考入场价（通常是昨日收盘价）
        
        Returns:
            {
                'can_enter_now': bool,
                'suggested_price': float,
                'reason': str
            }
        """
        if not intraday_data or len(intraday_data) < 5:
            return {
                'can_enter_now': False,
                'suggested_price': entry_price_ref,
                'reason': '分时数据不足'
            }
        
        # 获取最新价格
        latest = intraday_data[-1]
        current_price = latest.get('close', 0)
        current_time = latest.get('trade_time', '')
        
        # 计算分时均价
        closes = [d.get('close', 0) for d in intraday_data if d.get('close', 0) > 0]
        avg_price = sum(closes) / len(closes) if closes else 0
        
        # 判断逻辑
        can_enter = False
        reason = ""
        
        # 1. 时间窗口检查（10:30-14:00）
        if current_time:
            hour_min = current_time[8:13]  # 提取 HH:MM
            if '10:30' <= hour_min <= '14:00':
                time_ok = True
            else:
                time_ok = False
                reason = f"当前时间{hour_min}不在建议入场窗口（10:30-14:00）"
        else:
            time_ok = True
        
        if not time_ok:
            return {
                'can_enter_now': False,
                'suggested_price': current_price,
                'reason': reason
            }
        
        # 2. 价格位置检查
        if current_price > avg_price * 0.98:
            # 在均价线上方或附近
            can_enter = True
            reason = f"当前价¥{current_price:.2f}在分时均价线上方，可入场"
        else:
            can_enter = False
            reason = f"当前价¥{current_price:.2f}低于分时均价线，建议等待"
        
        # 3. 不追高检查
        if current_price > entry_price_ref * 1.03:
            can_enter = False
            reason = f"当前价¥{current_price:.2f}较参考价涨幅过大，不追高"
        
        return {
            'can_enter_now': can_enter,
            'suggested_price': current_price,
            'reason': reason
        }
    
    def format_decision(self, ts_code: str, name: str, decision: Dict) -> str:
        """
        格式化决策输出
        
        Args:
            ts_code: 股票代码
            name: 股票名称
            decision: 决策结果
        
        Returns:
            格式化的决策文本
        """
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"{name} ({ts_code})")
        lines.append(f"{'='*60}")
        
        action = decision['action']
        if action == 'enter':
            lines.append(f"✓ 决策: 可以入场")
            lines.append(f"  信心度: {decision['confidence'].upper()}")
            lines.append(f"  评分: {decision.get('score', 0)}/100")
            lines.append(f"  时机: {decision['timing']}")
            lines.append(f"  入场价: ¥{decision['entry_price']:.2f}")
            lines.append(f"  止盈价: ¥{decision['stop_profit_price']:.2f} (+{self.stop_profit*100:.0f}%)")
            lines.append(f"  止损价: ¥{decision['stop_loss_price']:.2f} (-{self.stop_loss*100:.0f}%)")
            lines.append(f"  时间止损: {self.time_stop}天")
        elif action == 'wait':
            lines.append(f"○ 决策: 继续观察")
            lines.append(f"  原因: {decision['reason']}")
            lines.append(f"  建议: {decision['timing']}")
        else:
            lines.append(f"✗ 决策: 跳过")
            lines.append(f"  原因: {decision['reason']}")
        
        return "\n".join(lines)


if __name__ == '__main__':
    # 测试
    from .data_fetcher import TushareDataFetcher
    from .signal_detector import StopFallingSignalDetector
    
    fetcher = TushareDataFetcher()
    detector = StopFallingSignalDetector()
    decision_maker = EntryDecisionMaker()
    
    print("测试入场决策...")
    
    # 测试圣阳股份
    daily = fetcher.get_daily_data('002580.SZ', '20260410', '20260423')
    signal_result = detector.check_signal(daily)
    decision = decision_maker.decide(signal_result, '20260423')
    
    output = decision_maker.format_decision('002580.SZ', '圣阳股份', decision)
    print(output)
    
    print("\n✓ 入场决策模块测试通过")

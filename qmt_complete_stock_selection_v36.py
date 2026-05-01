#!/usr/bin/env python3
"""
龙头回调策略 v3.6 完整选股系统
策略评分（125分）+ 买入确认信号 + 低吸位置建议
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from lib.entry_timing.data_fetcher import TushareDataFetcher
from lib.entry_timing.signal_detector_v2 import StopFallingSignalDetectorV2
from lib.entry_timing.entry_decision import EntryDecisionMaker


def post_tushare(api: str, params: dict, token: str) -> list:
    """调用Tushare API"""
    url = "https://api.tushare.pro"
    data = {
        "api_name": api,
        "token": token,
        "params": params,
        "fields": ""
    }
    response = requests.post(url, json=data, timeout=30)
    result = response.json()

    if result.get('code') != 0:
        raise Exception(f"API调用失败: {result.get('msg')}")

    items = result.get('data', {})
    fields = items.get('fields', [])
    rows = items.get('items', [])

    return [dict(zip(fields, row)) for row in rows]


def get_stock_name(ts_code: str, token: str) -> str:
    """获取股票名称"""
    try:
        rows = post_tushare('stock_basic', {'ts_code': ts_code}, token)
        return rows[0]['name'] if rows else ts_code
    except:
        return ts_code


def calculate_consecutive_limits(daily_history: dict, code: str, current_date: str) -> int:
    """计算截至current_date的连续涨停板数"""
    dates = sorted([d for d in daily_history.keys() if d <= current_date], reverse=True)

    consecutive = 0
    for date in dates:
        if code in daily_history.get(date, {}):
            stock = daily_history[date][code]
            if stock.get('limit') == 'U':
                consecutive += 1
            else:
                break
        else:
            break

    return consecutive


def find_stocks_with_4plus_limits(daily_history: dict, current_date: str, lookback_days: int = 20) -> list:
    """
    找出最近20个交易日内出现过4连板及以上的股票
    """
    candidates = []
    seen = set()

    dates = sorted([d for d in daily_history.keys() if d <= current_date], reverse=True)
    lookback_dates = dates[:lookback_days]

    for date in lookback_dates:
        date_data = daily_history.get(date, {})
        for code in date_data:
            if code.startswith('000001.SH'):
                continue
            if code in seen:
                continue

            max_consecutive = calculate_consecutive_limits(daily_history, code, date)
            if max_consecutive >= 4:
                candidates.append(code)
                seen.add(code)

    return candidates


def score_by_thresholds(value: float, thresholds: list[tuple[float, int]], default: int = 0) -> int:
    """按从高到低阈值映射分数。"""
    for threshold, score in thresholds:
        if value >= threshold:
            return score
    return default


def calculate_macro_factors(code: str, today_data: dict, daily_history: dict, current_date: str, token: str) -> dict:
    """
    计算宏观因子评分（总分25分）。

    v3.6 不再使用固定默认分：
    - 板块/短线强度：根据当日涨停池数量、候选成交额相对位置估算。
    - 大盘情绪：根据上证指数当日涨跌幅映射。
    - 热点追踪：根据涨停池规模与近5日热点持续性估算。
    """
    market_sentiment = 0
    sector_strength = 0
    hot_tracking = 0

    sorted_amounts = []
    for stock in daily_history.get(current_date, {}).values():
        if isinstance(stock, dict) and stock.get('amount'):
            sorted_amounts.append(float(stock.get('amount') or 0))
    sorted_amounts.sort(reverse=True)

    amount = float(today_data.get('amount') or 0)
    amount_rank_ratio = 1.0
    if sorted_amounts and amount > 0:
        higher = sum(1 for x in sorted_amounts if x > amount)
        amount_rank_ratio = higher / max(len(sorted_amounts), 1)

    # 1. 板块/短线强度（0-10）：当日涨停池越强、候选成交额越靠前，分越高。
    try:
        rows = post_tushare('limit_list_d', {'trade_date': current_date}, token)
        limit_up_count = sum(1 for row in rows if row.get('limit') == 'U')
    except Exception:
        limit_up_count = 0

    sector_strength = score_by_thresholds(
        limit_up_count,
        [
            (80, 10),
            (60, 8),
            (40, 6),
            (25, 4),
            (10, 2),
        ],
        default=0,
    )
    if amount_rank_ratio <= 0.1:
        sector_strength = min(10, sector_strength + 2)
    elif amount_rank_ratio <= 0.25:
        sector_strength = min(10, sector_strength + 1)

    # 2. 大盘情绪（0-5）：读取上证指数当天涨跌幅
    market_pct = 0.0
    index_code = '000001.SH'
    try:
        rows = post_tushare('index_daily', {'ts_code': index_code, 'trade_date': current_date}, token)
        if rows:
            market_pct = float(rows[0].get('pct_chg') or 0)
        elif index_code in daily_history.get(current_date, {}):
            market_pct = float(daily_history[current_date][index_code].get('pct_chg') or 0)
    except Exception:
        if index_code in daily_history.get(current_date, {}):
            market_pct = float(daily_history[current_date][index_code].get('pct_chg') or 0)
        else:
            market_pct = 0.0

    market_sentiment = score_by_thresholds(
        market_pct,
        [
            (1.5, 5),
            (0.8, 4),
            (0.2, 3),
            (-0.5, 2),
            (-1.5, 1),
        ],
        default=0,
    )

    # 3. 热点追踪（0-10）：涨停池规模 + 近5日热点持续性
    hot_tracking = score_by_thresholds(
        limit_up_count,
        [
            (80, 8),
            (60, 6),
            (40, 4),
            (20, 2),
        ],
        default=0,
    )

    recent_dates = sorted([d for d in daily_history.keys() if d <= current_date], reverse=True)[:5]
    if recent_dates:
        active_days = 0
        limit_rows_by_date = {}
        for d in recent_dates:
            try:
                limit_rows_by_date[d] = [row for row in post_tushare('limit_list_d', {'trade_date': d}, token) if row.get('limit') == 'U']
            except Exception:
                limit_rows_by_date[d] = []
            if len(limit_rows_by_date[d]) >= 20:
                active_days += 1
        hot_tracking += min(2, active_days // 2)

    hot_tracking = max(0, min(10, hot_tracking))
    total = sector_strength + market_sentiment + hot_tracking

    return {
        'sector_strength': sector_strength,
        'market_sentiment': market_sentiment,
        'hot_tracking': hot_tracking,
        'total': total,
    }


def calculate_entry_signal_score(current_data: dict, recent_daily: list[dict]) -> dict:
    """
    计算买入确认信号评分
    返回:
        {
            'signal_score': float,  # 总分
            'positive_signals': list,  # 正面信号
            'negative_signals': list,  # 负面信号
            'level': str  # 信号等级
        }
    """
    positive_signals = []
    negative_signals = []
    score = 0.0

    if not recent_daily:
        return {
            'signal_score': 0,
            'positive_signals': [],
            'negative_signals': ['无历史数据'],
            'level': 'none'
        }

    today = recent_daily[0] if recent_daily else current_data
    prev = recent_daily[1] if len(recent_daily) > 1 else {}

    open_price = float(today.get('open') or 0)
    high_price = float(today.get('high') or 0)
    low_price = float(today.get('low') or 0)
    close_price = float(today.get('close') or 0)
    vol = float(today.get('vol') or 0)
    prev_vol = float(prev.get('vol') or 0)

    # 1. 长下影线 (+1分)
    if high_price > 0 and close_price > 0 and low_price > 0:
        body_low = min(open_price, close_price)
        lower_shadow = body_low - low_price
        total_range = high_price - low_price
        if total_range > 0 and lower_shadow / total_range >= 0.35:
            score += 1
            positive_signals.append('长下影线')

    # 2. V型反转 (+1分)
    if close_price > open_price and high_price > 0:
        if low_price <= open_price * 0.97 and close_price >= (high_price + low_price) / 2:
            score += 1
            positive_signals.append('V型反转')

    # 3. 尾盘强势 (+1分)
    if high_price > low_price:
        close_pos = (close_price - low_price) / (high_price - low_price)
        if close_pos >= 0.75:
            score += 1
            positive_signals.append('尾盘强势')
        elif close_pos <= 0.35:
            score -= 0.5
            negative_signals.append('尾盘弱势')

    # 4. 缩量惜售 (+1分)
    if prev_vol > 0:
        vol_ratio = vol / prev_vol
        if vol_ratio <= 0.7:
            score += 1
            positive_signals.append('缩量惜售')
        elif vol_ratio >= 1.3 and close_price < open_price:
            score -= 1
            negative_signals.append('放量下跌')

    # 5. 地量 (+0.5分)
    recent_vols = [float(item.get('vol') or 0) for item in recent_daily[:5] if item.get('vol')]
    if recent_vols and vol == min(recent_vols):
        score += 0.5
        positive_signals.append('地量')

    # 6. 回调到支撑 (+0.5分)
    closes = [float(item.get('close') or 0) for item in recent_daily[:20] if item.get('close')]
    if len(closes) >= 10:
        ma10 = sum(closes[:10]) / 10
        if abs(close_price - ma10) / ma10 <= 0.02:
            score += 0.5
            positive_signals.append('回调到支撑')
        elif close_price < ma10 * 0.97:
            score -= 1
            negative_signals.append('跌破支撑')

    # 7. 冲高回落 (-0.5分)
    if high_price > 0 and close_price > 0 and open_price > 0:
        intraday_gain = (high_price - open_price) / open_price if open_price else 0
        close_drawback = (high_price - close_price) / high_price if high_price else 0
        if intraday_gain >= 0.04 and close_drawback >= 0.03:
            score -= 0.5
            negative_signals.append('冲高回落')

    # 附加信号：回调结构
    pct_chg = float(today.get('pct_chg') or 0)
    if -5 <= pct_chg <= -2:
        score += 0.5
        positive_signals.append('回调缩量')
    elif pct_chg < -7:
        score -= 0.5
        negative_signals.append('深度回调')

    if prev_vol > 0 and vol / prev_vol <= 0.5:
        score += 0.5
        positive_signals.append('极度缩量')

    if current_data.get('is_leader'):
        score += 0.5
        positive_signals.append('板块龙头')

    if score >= 3:
        level = 'strong'
    elif score >= 1.5:
        level = 'medium'
    elif score > 0:
        level = 'weak'
    else:
        level = 'none'

    return {
        'signal_score': round(score, 1),
        'positive_signals': positive_signals,
        'negative_signals': negative_signals,
        'level': level,
    }


def generate_entry_position_advice(today_data: dict, daily_history: dict, code: str, current_date: str) -> dict:
    """
    生成低吸位置建议
    """
    dates = sorted([d for d in daily_history.keys() if d <= current_date], reverse=True)
    closes = []
    lows = []
    highs = []
    limit_high = None

    for d in dates[:20]:
        stock = daily_history.get(d, {}).get(code)
        if not stock:
            continue
        if stock.get('close') is not None:
            closes.append(float(stock['close']))
        if stock.get('low') is not None:
            lows.append(float(stock['low']))
        if stock.get('high') is not None:
            highs.append(float(stock['high']))
        if stock.get('limit') == 'U' and limit_high is None:
            limit_high = float(stock.get('high') or stock.get('close') or 0)

    close_price = float(today_data.get('close') or 0)
    today_low = float(today_data.get('low') or close_price)
    ma5 = sum(closes[:5]) / min(len(closes), 5) if closes else close_price
    ma10 = sum(closes[:10]) / min(len(closes), 10) if closes else close_price
    ma20 = sum(closes[:20]) / min(len(closes), 20) if closes else close_price
    recent_low = min(lows[:10]) if lows else today_low
    recent_high = max(highs[:10]) if highs else close_price
    fib_382 = recent_high - (recent_high - recent_low) * 0.382
    fib_500 = recent_high - (recent_high - recent_low) * 0.5

    support_levels = {
        'today_low': {'label': '今日低点', 'price': round(today_low, 2)},
        'ma5': {'label': '5日线', 'price': round(ma5, 2)},
        'ma10': {'label': '10日线', 'price': round(ma10, 2)},
        'ma20': {'label': '20日线', 'price': round(ma20, 2)},
        'recent_low': {'label': '近10日低点', 'price': round(recent_low, 2)},
        'fib_382': {'label': '回撤38.2%', 'price': round(fib_382, 2)},
        'fib_500': {'label': '回撤50%', 'price': round(fib_500, 2)},
    }
    if limit_high:
        support_levels['limit_high'] = {'label': '涨停高点', 'price': round(limit_high, 2)}

    base_entry = min(today_low, ma5, ma10)
    stronger_support = min(ma10, ma20, fib_382)

    strategies = {
        'A': {
            'name': '激进',
            'entry_price': round(base_entry, 2),
            'stop_loss': round(base_entry * 0.97, 2),
        },
        'B': {
            'name': '稳健',
            'entry_price': round(stronger_support, 2),
            'stop_loss': round(stronger_support * 0.97, 2),
        },
        'C': {
            'name': '分批（推荐）',
            'first_batch': round(base_entry, 2),
            'second_batch': round(stronger_support, 2),
            'stop_loss': round(min(base_entry, stronger_support) * 0.97, 2),
        },
    }

    return {
        'support_levels': support_levels,
        'strategies': strategies,
    }


def calculate_strategy_score_v36(code: str, today_data: dict, daily_history: dict, current_date: str, token: str) -> dict:
    """
    计算策略评分 v3.6（总分125分）
    """
    score_detail = {
        'total': 0,
        'limit_strength': 0,        # 1. 连板强度 0-20
        'pullback_depth': 0,         # 2. 回调幅度 -5-15
        'volume_shrink': 0,          # 3. 缩量程度 0-20
        'volume_ratio_health': 0,    # 4. 量比健康度 0-12
        'support': 0,                # 5. 支撑位 0-18
        'rebound_signal': 0,         # 6. 反弹信号 0-10
        'trend': 0,                  # 7. 趋势 0-10
        'sector_heat': 0,            # 8. 板块热度 0-5
        'leader_risk': 0,            # 9. 高位股风险 -20-0
        'turnover_risk': 0,          # 10. 换手率异常 -10-0
        'time_dimension': 0,         # 11. 时间维度 -5-0
    }

    dates = sorted([d for d in daily_history.keys() if d <= current_date], reverse=True)

    # 1. 连板强度（0-20分）
    max_consecutive = 0
    for date in dates[:20]:
        consecutive = calculate_consecutive_limits(daily_history, code, date)
        max_consecutive = max(max_consecutive, consecutive)

    if max_consecutive >= 6:
        score_detail['limit_strength'] = 20
    elif max_consecutive == 5:
        score_detail['limit_strength'] = 18
    elif max_consecutive == 4:
        score_detail['limit_strength'] = 16
    elif max_consecutive == 3:
        score_detail['limit_strength'] = 14
    elif max_consecutive == 2:
        score_detail['limit_strength'] = 12

    # 2. 回调幅度（-5-15分）
    closes = [float(daily_history[d][code].get('close') or 0) for d in dates[:10] if code in daily_history.get(d, {})]
    if closes:
        recent_high = max(closes)
        current_close = float(today_data.get('close') or closes[0])
        pullback_pct = ((recent_high - current_close) / recent_high * 100) if recent_high else 0
        if max_consecutive >= 4:
            if 8 <= pullback_pct <= 15:
                score_detail['pullback_depth'] = 15
            elif 5 <= pullback_pct < 8:
                score_detail['pullback_depth'] = 10
            elif 15 < pullback_pct <= 20:
                score_detail['pullback_depth'] = 0
            else:
                score_detail['pullback_depth'] = 5
        else:
            if 4 <= pullback_pct <= 10:
                score_detail['pullback_depth'] = 10
            elif 2 <= pullback_pct < 4:
                score_detail['pullback_depth'] = 5
            else:
                score_detail['pullback_depth'] = 5
    else:
        score_detail['pullback_depth'] = 5

    # 3. 缩量程度（0-20分）= A部分（0-12分）+ B部分（-8-+8分）
    today_vol = float(today_data.get('vol') or 0)
    recent_vols = [float(daily_history[d][code].get('vol') or 0) for d in dates[:10] if code in daily_history.get(d, {})]
    if len(recent_vols) >= 2 and today_vol > 0:
        peak_vol = max(recent_vols)
        if peak_vol > 0:
            ratio_to_peak = today_vol / peak_vol
            if ratio_to_peak <= 0.35:
                score_detail['volume_shrink'] = 12
            elif ratio_to_peak <= 0.5:
                score_detail['volume_shrink'] = 9
            elif ratio_to_peak <= 0.7:
                score_detail['volume_shrink'] = 6
            elif ratio_to_peak <= 0.9:
                score_detail['volume_shrink'] = 3
            else:
                score_detail['volume_shrink'] = 0
        else:
            score_detail['volume_shrink'] = 3
    else:
        score_detail['volume_shrink'] = 3

    prev3 = recent_vols[1:4]
    if prev3 and today_vol > 0:
        avg_prev3 = sum(prev3) / len(prev3)
        ratio_prev3 = today_vol / avg_prev3 if avg_prev3 else 1
        if ratio_prev3 <= 0.45:
            score_detail['volume_shrink'] += 8
        elif ratio_prev3 <= 0.7:
            score_detail['volume_shrink'] += 4
        elif ratio_prev3 <= 0.9:
            score_detail['volume_shrink'] += 4
        elif ratio_prev3 >= 1.5:
            score_detail['volume_shrink'] -= 8
        elif ratio_prev3 >= 1.2:
            score_detail['volume_shrink'] -= 4
    score_detail['volume_shrink'] = max(0, min(20, score_detail['volume_shrink']))

    # 4. 量比健康度（0-12分）
    volume_ratio = float(today_data.get('volume_ratio') or 0)
    if volume_ratio:
        if 0.6 <= volume_ratio <= 1.2:
            score_detail['volume_ratio_health'] = 12
        elif 0.4 <= volume_ratio < 0.6 or 1.2 < volume_ratio <= 1.5:
            score_detail['volume_ratio_health'] = 8
        elif 0.2 <= volume_ratio < 0.4 or 1.5 < volume_ratio <= 2.0:
            score_detail['volume_ratio_health'] = 4
    else:
        score_detail['volume_ratio_health'] = 8

    # 5. 支撑位接近度（0-18分）
    closes20 = [float(daily_history[d][code].get('close') or 0) for d in dates[:20] if code in daily_history.get(d, {})]
    lows10 = [float(daily_history[d][code].get('low') or 0) for d in dates[:10] if code in daily_history.get(d, {})]
    close_price = float(today_data.get('close') or 0)
    today_low = float(today_data.get('low') or close_price)
    support_refs = []
    if closes20:
        support_refs.append(sum(closes20[:5]) / min(5, len(closes20)))
        support_refs.append(sum(closes20[:10]) / min(10, len(closes20)))
        support_refs.append(sum(closes20[:20]) / min(20, len(closes20)))
    if lows10:
        support_refs.append(min(lows10))
    if support_refs and close_price > 0:
        min_distance = min(abs(close_price - ref) / close_price for ref in support_refs if ref)
    else:
        min_distance = 1.0

    if close_price <= 0:
        score_detail['support'] = 0
    elif min_distance <= 0.01:
        score_detail['support'] = 18
    elif min_distance <= 0.02:
        score_detail['support'] = 15
    elif min_distance <= 0.03:
        score_detail['support'] = 10
    elif min_distance <= 0.05:
        score_detail['support'] = 5
    else:
        score_detail['support'] = 2

    # 6. 反弹信号（0-10分）
    open_price = float(today_data.get('open') or close_price)
    high_price = float(today_data.get('high') or close_price)
    if close_price > open_price:
        score_detail['rebound_signal'] += 5
    if high_price > today_low and close_price > 0:
        close_pos = (close_price - today_low) / max(high_price - today_low, 1e-6)
        if close_pos >= 0.75:
            score_detail['rebound_signal'] += 3
    pct_chg = float(today_data.get('pct_chg') or 0)
    if pct_chg >= -1:
        score_detail['rebound_signal'] += 2
    score_detail['rebound_signal'] = min(10, score_detail['rebound_signal'])

    # 7. 趋势判断（0-10分）
    if len(closes20) >= 20:
        ma5 = sum(closes20[:5]) / 5
        ma10 = sum(closes20[:10]) / 10
        ma20 = sum(closes20[:20]) / 20
        if ma5 >= ma10 >= ma20:
            score_detail['trend'] = 10
        elif ma10 >= ma20:
            score_detail['trend'] = 5
        else:
            score_detail['trend'] = 0

    # 8. 板块热度（0-5分）：复用宏观热点宽度，避免固定默认分。
    macro_factors = calculate_macro_factors(code, today_data, daily_history, current_date, token)
    score_detail['sector_heat'] = max(0, min(5, round(macro_factors['hot_tracking'] / 2)))

    # 9. 高位风险（-20-0分）
    if max_consecutive >= 7:
        score_detail['leader_risk'] = -10
    elif max_consecutive >= 6:
        score_detail['leader_risk'] = -5
    else:
        score_detail['leader_risk'] = 0

    if closes20:
        recent_high = max(closes20)
        current_close = close_price or closes20[0]
        drawdown = ((recent_high - current_close) / recent_high * 100) if recent_high else 0
        if drawdown < 3 and max_consecutive >= 6:
            score_detail['leader_risk'] = min(score_detail['leader_risk'], -20)
        elif drawdown < 5 and max_consecutive >= 5:
            score_detail['leader_risk'] = min(score_detail['leader_risk'], -10)

    # 10. 换手率异常（-10-0分）
    turnover = float(today_data.get('turnover_rate') or 0)
    if turnover >= 35:
        score_detail['turnover_risk'] = -10
    elif turnover >= 25:
        score_detail['turnover_risk'] = -5

    # 11. 时间维度（-5-0分）
    if dates:
        last_limit_date = None
        for d in dates:
            if code in daily_history.get(d, {}) and daily_history[d][code].get('limit') == 'U':
                last_limit_date = datetime.strptime(d, '%Y%m%d')
                break
        if last_limit_date:
            current_dt = datetime.strptime(current_date, '%Y%m%d')
            delta = (current_dt - last_limit_date).days
            if delta <= 3:
                score_detail['time_dimension'] = 0
            elif delta <= 7:
                score_detail['time_dimension'] = -5
            else:
                score_detail['time_dimension'] = -5

    # 宏观因子（25分）
    score_detail['sector_strength'] = macro_factors['sector_strength']
    score_detail['market_sentiment'] = macro_factors['market_sentiment']
    score_detail['hot_tracking'] = macro_factors['hot_tracking']

    # 计算总分
    score_detail['total'] = sum(score_detail.values())
    score_detail['max_consecutive'] = max_consecutive

    return score_detail


def main():
    token = os.environ.get('TUSHARE_TOKEN')
    if not token:
        print("错误: 未设置TUSHARE_TOKEN环境变量")
        return

    print("龙头回调策略 v3.6 - 完整选股系统")
    print("策略评分（125分）+ 买入确认信号 + 低吸位置建议")
    print("=" * 80)

    fetcher = TushareDataFetcher(token)
    detector = StopFallingSignalDetectorV2()
    decision_maker = EntryDecisionMaker()

    recent_dates = fetcher.get_recent_trade_dates(days=30)
    if not recent_dates:
        print("未获取到交易日")
        return

    daily_history = {}
    stock_name_map = {}
    latest_date = None

    for date in recent_dates:
        try:
            daily_raw = post_tushare('daily', {'trade_date': date}, token)
            if not daily_raw:
                continue
            latest_date = latest_date or date

            basic_map = {}
            try:
                basic_data = post_tushare('daily_basic', {'trade_date': date}, token)
                basic_map = {row['ts_code']: row for row in basic_data}
            except Exception:
                basic_map = {}

            limit_map = {}
            try:
                limit_data = post_tushare('limit_list_d', {'trade_date': date}, token)
                limit_map = {row['ts_code']: row for row in limit_data}
            except Exception:
                limit_map = {}

            index_map = {}
            try:
                index_rows = post_tushare('index_daily', {'ts_code': '000001.SH', 'trade_date': date}, token)
                if index_rows:
                    index_map['000001.SH'] = index_rows[0]
            except Exception:
                index_map = {}

            merged = {}
            for row in daily_raw:
                code = row['ts_code']
                combined = dict(row)
                basic_row = basic_map.get(code, {})
                if basic_row:
                    combined.update({
                        'turnover_rate': basic_row.get('turnover_rate'),
                        'volume_ratio': basic_row.get('volume_ratio'),
                    })
                limit_row = limit_map.get(code, {})
                if limit_row:
                    combined['limit'] = limit_row.get('limit')
                merged[code] = combined
                stock_name_map.setdefault(code, get_stock_name(code, token))
            merged.update(index_map)
            daily_history[date] = merged
        except Exception as exc:
            print(f"加载 {date} 数据失败: {exc}")

    if not daily_history or not latest_date:
        print("未加载到有效行情数据")
        return

    print(f"分析日期: {latest_date} (有数据的最新交易日)")
    print("\n正在筛选最近20日内出现过4连板以上的股票...")
    candidates = find_stocks_with_4plus_limits(daily_history, latest_date, lookback_days=20)
    print(f"找到候选股票: {len(candidates)} 只")

    print("\n正在计算策略评分 v3.6...")
    scored_stocks = []
    for code in candidates:
        today_data = daily_history.get(latest_date, {}).get(code)
        if not today_data:
            continue
        strategy_score = calculate_strategy_score_v36(code, today_data, daily_history, latest_date, token)
        if strategy_score['total'] >= 60:
            entry_advice = generate_entry_position_advice(today_data, daily_history, code, latest_date)
            recent_daily = [daily_history[d][code] for d in sorted([d for d in daily_history.keys() if d <= latest_date], reverse=True)[:10] if code in daily_history.get(d, {})]
            signal_result = detector.check_signal(recent_daily)
            entry_signal = calculate_entry_signal_score(today_data, recent_daily)
            signal_result = signal_result or {}
            signal_result.setdefault('score', 0)
            signal_result.setdefault('signals', [])
            signal_result.setdefault('breakdown', {})
            signal_result.setdefault('action', 'wait')
            decision = decision_maker.decide(signal_result, latest_date)
            scored_stocks.append({
                'code': code,
                'name': stock_name_map.get(code, code),
                'strategy_score': strategy_score['total'],
                'score_detail': strategy_score,
                'entry_signal': entry_signal,
                'entry_score': signal_result['score'],
                'signal_result': signal_result,
                'decision': decision,
                'entry_advice': entry_advice,
                'max_consecutive': strategy_score['max_consecutive'],
                'pct_chg': float(today_data.get('pct_chg') or 0),
            })

    scored_stocks.sort(key=lambda x: x['strategy_score'], reverse=True)
    print(f"策略评分≥60分: {len(scored_stocks)} 只")
    print("\n正在分析入场时机...")

    print(f"\n完整分析结果（{latest_date}）")
    print("=" * 80)
    for stock in scored_stocks:
        detail = stock['score_detail']
        entry_signal = stock['entry_signal']
        signal_result = stock['signal_result']
        entry_advice = stock['entry_advice']
        decision = stock['decision']
        decision_text = decision.get('action', 'wait') if isinstance(decision, dict) else str(decision)
        print(f"\n{stock['name']} ({stock['code']})")
        print(f"策略评分: {stock['strategy_score']}/125")
        print(f"  1. 连板强度: {detail['limit_strength']}/20")
        print(f"  2. 回调幅度: {detail['pullback_depth']}/15")
        print(f"  3. 缩量程度: {detail['volume_shrink']}/20")
        print(f"  4. 量比健康度: {detail['volume_ratio_health']}/12")
        print(f"  5. 支撑位: {detail['support']}/18")
        print(f"  6. 反弹信号: {detail['rebound_signal']}/10")
        print(f"  7. 趋势判断: {detail['trend']}/10")
        print(f"  8. 板块热度: {detail['sector_heat']}/5")
        print(f"  宏观因子: {detail['sector_strength'] + detail['market_sentiment'] + detail['hot_tracking']}/25")
        print(f"\n买入确认信号: {entry_signal['signal_score']:.1f}分 ({entry_signal['level'].upper()})")
        print(f"\n入场评分: {signal_result['score']}/100")
        breakdown = signal_result.get('breakdown', {})
        if breakdown:
            print(f"  得分明细:")
            print(f"    K线形态: {breakdown.get('kline_pattern', 0)}/30")
            print(f"    量价配合: {breakdown.get('volume_price', 0)}/30")
            print(f"    支撑压力: {breakdown.get('support_pressure', 0)}/20")
            if breakdown.get('penalty'):
                print(f"    扣分项: {breakdown.get('penalty', 0)}")
        print(f"\n交易决策: {decision_text}")
        if isinstance(decision, dict):
            print(f"  原因: {decision.get('reason', '')}")
            print(f"  时机: {decision.get('timing', '')}")
        print(f"  支撑位分析:")
        for key, level in entry_advice['support_levels'].items():
            print(f"    {level['label']}: {level['price']}")
        print(f"  策略A（激进）: {entry_advice['strategies']['A']['entry_price']}")
        print(f"  策略B（稳健）: {entry_advice['strategies']['B']['entry_price']}")
        print(f"  策略C（分批）: {entry_advice['strategies']['C']['first_batch']} + {entry_advice['strategies']['C']['second_batch']}")

    print("\n完整评分表（所有评分≥60分的股票）")
    print("=" * 80)
    print(f"{'排名':<4} {'代码':<12} {'名称':<10} {'连板':<6} {'今日涨跌':<10} {'策略评分':<10} {'入场评分':<10} {'决策':<10}")
    for i, stock in enumerate(scored_stocks, 1):
        decision_text = stock['decision'].get('action', 'wait') if isinstance(stock['decision'], dict) else str(stock['decision'])
        print(f"{i:<4} {stock['code']:<12} {stock['name']:<10} {stock['max_consecutive']}板   {stock['pct_chg']:>+6.2f}%   {stock['strategy_score']:>3}/125   {stock['entry_score']:>3}/100   {decision_text:<10}")

    priority = [stock for stock in scored_stocks if stock['strategy_score'] >= 80]
    watch = [stock for stock in scored_stocks if 60 <= stock['strategy_score'] < 80]
    if priority:
        print("\n重点关注：")
        for stock in priority:
            print(f"  ✓ {stock['name']} ({stock['code']}) - 策略{stock['strategy_score']}分")
    if watch:
        print("\n观察名单：")
        for stock in watch:
            print(f"  ○ {stock['name']} ({stock['code']}) - 策略{stock['strategy_score']}分")

    output_dir = ROOT_DIR / 'qmt_sync' / 'reports' / latest_date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_data = {
        'date': latest_date,
        'strategy': 'leader_pullback_v36',
        'candidates': scored_stocks,
    }
    output_file = output_dir / 'leader_pullback_selection.json'
    output_file.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✓ 结果已保存到: {output_file}")


if __name__ == '__main__':
    main()

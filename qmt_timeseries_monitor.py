#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT 分时数据接入
9:30-15:00 每分钟分时数据
实时计算承接强度
"""

import json
import time
from pathlib import Path
from datetime import datetime, date
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"
TIMESERIES_DIR = HERMES_HOME / "state" / "qmt_timeseries"
TIMESERIES_DIR.mkdir(parents=True, exist_ok=True)


def fetch_realtime_tick(code: str) -> Optional[dict]:
    """
    获取实时分时数据
    
    返回:
    {
        "code": "300123",
        "name": "太阳鸟",
        "time": "2026-04-21 09:31:00",
        "price": 12.34,
        "volume": 1234567,
        "amount": 15234567.89,
        "bid_volume": 123456,
        "ask_volume": 234567,
        "change_pct": 3.2,
    }
    """
    
    # 使用数据源适配器
    from qmt_data_source import get_data_source
    
    try:
        source = get_data_source("auto")
        quote = source.get_realtime_quote(code)
        
        if not quote:
            return None
        
        return {
            "code": code,
            "name": quote.get("name", ""),
            "time": quote.get("time", datetime.now().isoformat()),
            "price": quote.get("price", 0.0),
            "volume": quote.get("volume", 0),
            "amount": quote.get("amount", 0.0),
            "bid_volume": quote.get("bid_volume", 0),
            "ask_volume": quote.get("ask_volume", 0),
            "change_pct": quote.get("change_pct", 0.0),
        }
    except Exception as e:
        print(f"获取 {code} 实时数据失败: {e}")
        return None


def save_tick_data(code: str, tick: dict):
    """保存分时数据"""
    today = date.today().isoformat()
    tick_file = TIMESERIES_DIR / f"{code}_{today}.jsonl"
    
    with open(tick_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(tick, ensure_ascii=False) + "\n")


def load_today_ticks(code: str) -> list[dict]:
    """加载今日分时数据"""
    today = date.today().isoformat()
    tick_file = TIMESERIES_DIR / f"{code}_{today}.jsonl"
    
    if not tick_file.exists():
        return []
    
    ticks = []
    with open(tick_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                ticks.append(json.loads(line))
    
    return ticks


def calculate_承接强度(ticks: list[dict]) -> dict:
    """
    计算承接强度
    
    指标:
    - 量能趋势: 最近 5 分钟 vs 前 5 分钟
    - 买卖比: 买盘 / 卖盘
    - 价格稳定性: 波动率
    - 封单强度: 涨停价附近的挂单
    """
    
    if len(ticks) < 10:
        return {
            "承接强度": 0.0,
            "量能趋势": 0.0,
            "买卖比": 0.0,
            "价格稳定性": 0.0,
        }
    
    # 最近 5 分钟
    recent_ticks = ticks[-5:]
    prev_ticks = ticks[-10:-5]
    
    # 量能趋势
    recent_volume = sum(t["volume"] for t in recent_ticks)
    prev_volume = sum(t["volume"] for t in prev_ticks)
    volume_trend = (recent_volume / prev_volume - 1) * 100 if prev_volume > 0 else 0.0
    
    # 买卖比
    total_bid = sum(t["bid_volume"] for t in recent_ticks)
    total_ask = sum(t["ask_volume"] for t in recent_ticks)
    bid_ask_ratio = total_bid / total_ask if total_ask > 0 else 0.0
    
    # 价格稳定性（波动率）
    prices = [t["price"] for t in recent_ticks]
    avg_price = sum(prices) / len(prices)
    volatility = sum(abs(p - avg_price) for p in prices) / avg_price if avg_price > 0 else 0.0
    stability = max(0, 1 - volatility * 10)  # 波动越小越稳定
    
    # 承接强度综合评分
    承接强度 = (
        min(volume_trend / 50, 1.0) * 0.4 +  # 量能趋势 40%
        min(bid_ask_ratio / 2, 1.0) * 0.4 +  # 买卖比 40%
        stability * 0.2  # 稳定性 20%
    ) * 10
    
    return {
        "承接强度": 承接强度,
        "量能趋势": volume_trend,
        "买卖比": bid_ask_ratio,
        "价格稳定性": stability,
    }


def monitor_realtime_candidates(codes: list[str], duration_minutes: int = 30):
    """
    实时监控候选票
    
    codes: 候选票代码列表
    duration_minutes: 监控时长（分钟）
    """
    
    print(f"开始监控 {len(codes)} 个候选票，时长 {duration_minutes} 分钟")
    
    start_time = time.time()
    end_time = start_time + duration_minutes * 60
    
    while time.time() < end_time:
        for code in codes:
            tick = fetch_realtime_tick(code)
            save_tick_data(code, tick)
        
        # 每分钟采集一次
        time.sleep(60)
    
    print("监控结束")
    
    # 计算承接强度
    for code in codes:
        ticks = load_today_ticks(code)
        strength = calculate_承接强度(ticks)
        print(f"{code}: 承接强度 {strength['承接强度']:.1f}")


def get_realtime_strength_report(codes: list[str]) -> dict:
    """获取实时承接强度报告"""
    report = {}
    
    for code in codes:
        ticks = load_today_ticks(code)
        if ticks:
            strength = calculate_承接强度(ticks)
            report[code] = {
                "tick_count": len(ticks),
                "latest_price": ticks[-1]["price"],
                "latest_change_pct": ticks[-1]["change_pct"],
                **strength,
            }
    
    return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="QMT 分时数据接入")
    parser.add_argument("action", choices=["monitor", "report"])
    parser.add_argument("--codes", nargs="+", help="股票代码列表")
    parser.add_argument("--duration", type=int, default=30, help="监控时长（分钟）")
    
    args = parser.parse_args()
    
    if args.action == "monitor":
        if not args.codes:
            print("错误：需要 --codes")
            exit(1)
        monitor_realtime_candidates(args.codes, args.duration)
    
    elif args.action == "report":
        if not args.codes:
            print("错误：需要 --codes")
            exit(1)
        report = get_realtime_strength_report(args.codes)
        print(json.dumps(report, ensure_ascii=False, indent=2))

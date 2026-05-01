#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史趋势分析
- 过去 5 日涨跌幅
- 过去 20 日成交额趋势
- 历史同题材表现
"""

import json
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"
HISTORY_DIR = HERMES_HOME / "state" / "qmt_history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def load_historical_data(code: str, days: int = 20) -> list[dict]:
    """
    加载历史数据
    
    返回: [{"date": "2026-04-21", "close": 12.34, "volume": 1234567, "amount": 15234567.89, "change_pct": 3.2}, ...]
    """
    
    # 使用数据源适配器
    from qmt_data_source import get_data_source
    
    try:
        source = get_data_source("auto")
        history = source.get_historical_data(code, days)
        return history
    except Exception as e:
        print(f"获取 {code} 历史数据失败: {e}")
        return []


def calculate_historical_trend(code: str) -> dict:
    """
    计算历史趋势
    
    返回:
    {
        "code": "300123",
        "5d_change_pct": 15.2,
        "20d_change_pct": 30.5,
        "5d_avg_amount": 500000000,
        "20d_avg_amount": 300000000,
        "amount_trend": "放量",
        "price_trend": "上升",
        "trend_score": 7.5,
    }
    """
    
    history = load_historical_data(code, days=20)
    
    if len(history) < 5:
        return {
            "code": code,
            "trend_score": 0.0,
            "trend_label": "无数据",
        }
    
    # 5 日涨跌幅
    if len(history) >= 5:
        change_5d = (history[-1]["close"] / history[-5]["close"] - 1) * 100
    else:
        change_5d = 0.0
    
    # 20 日涨跌幅
    if len(history) >= 20:
        change_20d = (history[-1]["close"] / history[-20]["close"] - 1) * 100
    else:
        change_20d = 0.0
    
    # 5 日平均成交额
    avg_amount_5d = sum(h["amount"] for h in history[-5:]) / 5
    
    # 20 日平均成交额
    if len(history) >= 20:
        avg_amount_20d = sum(h["amount"] for h in history[-20:]) / 20
    else:
        avg_amount_20d = avg_amount_5d
    
    # 量能趋势
    if avg_amount_5d > avg_amount_20d * 1.5:
        amount_trend = "大幅放量"
    elif avg_amount_5d > avg_amount_20d * 1.2:
        amount_trend = "放量"
    elif avg_amount_5d < avg_amount_20d * 0.8:
        amount_trend = "缩量"
    else:
        amount_trend = "平稳"
    
    # 价格趋势
    if change_5d > 20:
        price_trend = "强势上升"
    elif change_5d > 10:
        price_trend = "上升"
    elif change_5d > 0:
        price_trend = "小幅上升"
    elif change_5d > -10:
        price_trend = "小幅下跌"
    else:
        price_trend = "下跌"
    
    # 趋势评分
    trend_score = (
        min(change_5d / 20, 1.0) * 0.4 +  # 5日涨幅 40%
        min(change_20d / 50, 1.0) * 0.2 +  # 20日涨幅 20%
        min((avg_amount_5d / avg_amount_20d - 1), 1.0) * 0.4  # 量能趋势 40%
    ) * 10
    
    return {
        "code": code,
        "5d_change_pct": change_5d,
        "20d_change_pct": change_20d,
        "5d_avg_amount": avg_amount_5d,
        "20d_avg_amount": avg_amount_20d,
        "amount_trend": amount_trend,
        "price_trend": price_trend,
        "trend_score": trend_score,
    }


def calculate_theme_historical_performance(theme: str, days: int = 20) -> dict:
    """
    计算题材历史表现
    
    返回:
    {
        "theme": "AI算力",
        "avg_change_pct": 5.2,
        "limit_up_count": 15,
        "performance_label": "强势",
    }
    """
    
    # TODO: 从历史数据中统计题材表现
    # 目前返回默认值
    
    return {
        "theme": theme,
        "avg_change_pct": 0.0,
        "limit_up_count": 0,
        "performance_label": "无数据",
    }


def enrich_candidates_with_historical_analysis(candidates: list[dict]) -> list[dict]:
    """用历史趋势分析增强候选票"""
    
    print(f"分析 {len(candidates)} 个候选的历史趋势")
    
    for cand in candidates:
        code = cand["code"]
        
        # 个股历史趋势
        trend = calculate_historical_trend(code)
        cand["historical_trend"] = trend
        
        # 题材历史表现
        trade_theme = cand.get("trade_theme")
        if trade_theme:
            theme_perf = calculate_theme_historical_performance(trade_theme)
            cand["theme_historical_performance"] = theme_perf
        
        # 调整评分：历史趋势占 10% 权重
        if "score" in cand:
            original_score = cand["score"]
            trend_bonus = (trend["trend_score"] / 10.0) * 1.0  # 最高加 1 分
            cand["score"] = original_score + trend_bonus
            
            if "score_breakdown" not in cand:
                cand["score_breakdown"] = {}
            cand["score_breakdown"]["历史趋势"] = trend_bonus
    
    # 重新排序
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return candidates


def generate_historical_analysis_report(candidates: list[dict], output_path: Path):
    """生成历史趋势分析报告"""
    
    report = []
    report.append("=== 历史趋势分析报告 ===")
    report.append(f"候选数: {len(candidates)}")
    report.append("")
    
    # 按趋势评分排序
    sorted_candidates = sorted(
        candidates,
        key=lambda x: x.get("historical_trend", {}).get("trend_score", 0),
        reverse=True,
    )
    
    for cand in sorted_candidates[:20]:  # 只显示前 20 个
        trend = cand.get("historical_trend", {})
        
        report.append(f"## {cand['name']} ({cand['code']})")
        report.append(f"评分: {cand.get('score', 0):.1f}")
        report.append(f"5日涨幅: {trend.get('5d_change_pct', 0):.2f}%")
        report.append(f"20日涨幅: {trend.get('20d_change_pct', 0):.2f}%")
        report.append(f"量能: {trend.get('amount_trend', '未知')}")
        report.append(f"趋势: {trend.get('price_trend', '未知')}")
        report.append("")
    
    # 保存报告
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print(f"✓ 历史趋势报告已保存: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="历史趋势分析")
    parser.add_argument("--candidates", required=True, help="候选 JSON 文件")
    parser.add_argument("--output", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 加载候选
    with open(args.candidates, "r", encoding="utf-8") as f:
        candidates_data = json.load(f)
        candidates = candidates_data.get("candidates", [])
    
    print(f"加载 {len(candidates)} 个候选")
    
    # 历史趋势分析
    enhanced_candidates = enrich_candidates_with_historical_analysis(candidates)
    
    # 保存结果
    output_file = args.output or args.candidates.replace(".json", "_historical_enhanced.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "enhanced_at": date.today().isoformat(),
            "candidates": enhanced_candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 历史趋势增强结果已保存: {output_file}")
    
    # 生成报告
    report_file = Path(output_file).with_suffix(".txt")
    generate_historical_analysis_report(enhanced_candidates, report_file)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块联动分析
- 同板块其他票的表现
- 板块资金流向
- 板块情绪指标
"""

import json
from pathlib import Path
from datetime import date
from collections import defaultdict
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"


def load_sector_stocks(sector: str) -> list[str]:
    """加载板块成分股"""
    # TODO: 从题材库或行业分类中加载
    # 目前返回空列表
    return []


def calculate_sector_sentiment(sector: str, all_stocks_data: list[dict]) -> dict:
    """
    计算板块情绪
    
    返回:
    {
        "sector": "AI算力",
        "total_stocks": 50,
        "limit_up_count": 5,
        "limit_up_ratio": 0.10,
        "avg_change_pct": 3.2,
        "total_amount": 15000000000,
        "sentiment_score": 7.5,
        "sentiment_label": "强势",
    }
    """
    
    # 筛选板块内的股票
    sector_stocks = [
        stock for stock in all_stocks_data
        if sector in stock.get("theme_tags", []) or sector in stock.get("stock_theme_tags", [])
    ]
    
    if not sector_stocks:
        return {
            "sector": sector,
            "total_stocks": 0,
            "sentiment_score": 0.0,
            "sentiment_label": "无数据",
        }
    
    # 统计
    total_stocks = len(sector_stocks)
    limit_up_count = sum(1 for s in sector_stocks if s.get("change_pct", 0) >= 9.5)
    limit_up_ratio = limit_up_count / total_stocks
    
    avg_change_pct = sum(s.get("change_pct", 0) for s in sector_stocks) / total_stocks
    total_amount = sum(s.get("amount", 0) for s in sector_stocks)
    
    # 情绪评分
    sentiment_score = (
        limit_up_ratio * 50 +  # 涨停率 50%
        min(avg_change_pct / 5, 1.0) * 30 +  # 平均涨幅 30%
        min(total_amount / 50_000_000_000, 1.0) * 20  # 总成交额 20%
    )
    
    # 情绪标签
    if sentiment_score >= 7.0:
        sentiment_label = "强势"
    elif sentiment_score >= 5.0:
        sentiment_label = "活跃"
    elif sentiment_score >= 3.0:
        sentiment_label = "一般"
    else:
        sentiment_label = "弱势"
    
    return {
        "sector": sector,
        "total_stocks": total_stocks,
        "limit_up_count": limit_up_count,
        "limit_up_ratio": limit_up_ratio,
        "avg_change_pct": avg_change_pct,
        "total_amount": total_amount,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
    }


def calculate_sector_money_flow(sector: str, all_stocks_data: list[dict]) -> dict:
    """
    计算板块资金流向
    
    返回:
    {
        "sector": "AI算力",
        "net_inflow": 1500000000,  # 净流入
        "main_inflow": 1200000000,  # 主力净流入
        "retail_inflow": 300000000,  # 散户净流入
        "flow_label": "主力流入",
    }
    """
    
    # 筛选板块内的股票
    sector_stocks = [
        stock for stock in all_stocks_data
        if sector in stock.get("theme_tags", []) or sector in stock.get("stock_theme_tags", [])
    ]
    
    if not sector_stocks:
        return {
            "sector": sector,
            "net_inflow": 0.0,
            "flow_label": "无数据",
        }
    
    # 简化计算：用成交额 * 涨幅 估算资金流向
    net_inflow = sum(
        s.get("amount", 0) * s.get("change_pct", 0) / 100
        for s in sector_stocks
    )
    
    # 流向标签
    if net_inflow > 1_000_000_000:
        flow_label = "大幅流入"
    elif net_inflow > 0:
        flow_label = "小幅流入"
    elif net_inflow > -1_000_000_000:
        flow_label = "小幅流出"
    else:
        flow_label = "大幅流出"
    
    return {
        "sector": sector,
        "net_inflow": net_inflow,
        "flow_label": flow_label,
    }


def enrich_candidates_with_sector_analysis(candidates: list[dict], all_stocks_data: list[dict]) -> list[dict]:
    """用板块联动分析增强候选票"""
    
    # 收集所有涉及的板块
    all_sectors = set()
    for cand in candidates:
        if cand.get("trade_theme"):
            all_sectors.add(cand["trade_theme"])
        if cand.get("theme_tags"):
            all_sectors.update(cand["theme_tags"])
    
    print(f"分析 {len(all_sectors)} 个板块")
    
    # 计算板块情绪和资金流向
    sector_sentiment_map = {}
    sector_flow_map = {}
    
    for sector in all_sectors:
        sentiment = calculate_sector_sentiment(sector, all_stocks_data)
        flow = calculate_sector_money_flow(sector, all_stocks_data)
        
        sector_sentiment_map[sector] = sentiment
        sector_flow_map[sector] = flow
    
    # 为每个候选票添加板块分析
    for cand in candidates:
        trade_theme = cand.get("trade_theme")
        
        if trade_theme and trade_theme in sector_sentiment_map:
            sentiment = sector_sentiment_map[trade_theme]
            flow = sector_flow_map[trade_theme]
            
            cand["sector_sentiment"] = sentiment
            cand["sector_flow"] = flow
            
            # 调整评分：板块情绪占 10% 权重
            if "score" in cand:
                original_score = cand["score"]
                sector_bonus = (sentiment["sentiment_score"] / 10.0) * 1.0  # 最高加 1 分
                cand["score"] = original_score + sector_bonus
                
                if "score_breakdown" not in cand:
                    cand["score_breakdown"] = {}
                cand["score_breakdown"]["板块情绪"] = sector_bonus
    
    # 重新排序
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return candidates


def generate_sector_analysis_report(candidates: list[dict], output_path: Path):
    """生成板块分析报告"""
    
    # 统计板块
    sector_stats = defaultdict(list)
    for cand in candidates:
        trade_theme = cand.get("trade_theme")
        if trade_theme:
            sector_stats[trade_theme].append(cand)
    
    report = []
    report.append("=== 板块联动分析报告 ===")
    report.append(f"涉及板块: {len(sector_stats)}")
    report.append("")
    
    # 按板块情绪排序
    sorted_sectors = sorted(
        sector_stats.items(),
        key=lambda x: x[1][0].get("sector_sentiment", {}).get("sentiment_score", 0),
        reverse=True,
    )
    
    for sector, sector_cands in sorted_sectors[:10]:  # 只显示前 10 个板块
        sentiment = sector_cands[0].get("sector_sentiment", {})
        flow = sector_cands[0].get("sector_flow", {})
        
        report.append(f"## {sector}")
        report.append(f"情绪: {sentiment.get('sentiment_label', '未知')} ({sentiment.get('sentiment_score', 0):.1f})")
        report.append(f"涨停: {sentiment.get('limit_up_count', 0)}/{sentiment.get('total_stocks', 0)} ({sentiment.get('limit_up_ratio', 0)*100:.1f}%)")
        report.append(f"资金: {flow.get('flow_label', '未知')} ({flow.get('net_inflow', 0)/100000000:.1f}亿)")
        report.append(f"候选票: {len(sector_cands)}")
        
        for cand in sector_cands[:3]:  # 只显示前 3 个
            report.append(f"  - {cand['name']} ({cand['code']}) 评分 {cand.get('score', 0):.1f}")
        
        report.append("")
    
    # 保存报告
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print(f"✓ 板块分析报告已保存: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="板块联动分析")
    parser.add_argument("--candidates", required=True, help="候选 JSON 文件")
    parser.add_argument("--all-stocks", required=True, help="全市场股票数据 JSON 文件")
    parser.add_argument("--output", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 加载数据
    with open(args.candidates, "r", encoding="utf-8") as f:
        candidates_data = json.load(f)
        candidates = candidates_data.get("candidates", [])
    
    with open(args.all_stocks, "r", encoding="utf-8") as f:
        all_stocks_data = json.load(f)
        all_stocks = all_stocks_data.get("stocks", [])
    
    print(f"加载 {len(candidates)} 个候选，{len(all_stocks)} 只股票")
    
    # 板块分析
    enhanced_candidates = enrich_candidates_with_sector_analysis(candidates, all_stocks)
    
    # 保存结果
    output_file = args.output or args.candidates.replace(".json", "_sector_enhanced.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "enhanced_at": date.today().isoformat(),
            "candidates": enhanced_candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 板块增强结果已保存: {output_file}")
    
    # 生成报告
    report_file = Path(output_file).with_suffix(".txt")
    generate_sector_analysis_report(enhanced_candidates, report_file)

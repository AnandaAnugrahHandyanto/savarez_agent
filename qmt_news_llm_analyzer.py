#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息面 LLM 智能分析
- 自动分析新闻标题和内容
- 识别利好/利空强度
- 提取相关个股和板块
- 判断持续性（1日/3日/周级）
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"


def analyze_news_with_llm(news_title: str, news_content: Optional[str] = None) -> dict:
    """
    用 LLM 分析新闻
    
    返回:
    {
        "sentiment": "利好" | "利空" | "中性",
        "strength": 1-10,
        "related_sectors": ["板块1", "板块2"],
        "related_stocks": ["股票1", "股票2"],
        "duration": "1日" | "3日" | "周级" | "月级",
        "catalyst_score": 0-10,
        "summary": "简短总结",
        "reasoning": "分析理由"
    }
    """
    
    # 使用 LLM 客户端
    from llm_client import get_llm_client
    
    try:
        client = get_llm_client("auto")
        result = client.analyze_news(news_title, news_content)
        return result
    except Exception as e:
        print(f"LLM 分析失败: {e}")
        # Fallback 到规则引擎
        from llm_client import RuleBasedFallback
        fallback = RuleBasedFallback()
        return fallback.analyze_news(news_title, news_content)


def batch_analyze_news(news_list: list[dict]) -> list[dict]:
    """
    批量分析新闻
    
    news_list: [{"title": "...", "content": "...", "url": "..."}, ...]
    """
    results = []
    
    for news in news_list:
        title = news.get("title", "")
        content = news.get("content", "")
        
        if not title:
            continue
        
        analysis = analyze_news_with_llm(title, content)
        analysis["source_title"] = title
        analysis["source_url"] = news.get("url", "")
        analysis["analyzed_at"] = datetime.now().isoformat()
        
        results.append(analysis)
    
    return results


def filter_high_catalyst_news(analyzed_news: list[dict], min_score: float = 7.0) -> list[dict]:
    """筛选高催化剂评分的新闻"""
    return [
        news for news in analyzed_news
        if news.get("catalyst_score", 0) >= min_score
        and news.get("sentiment") == "利好"
    ]


def summarize_sector_catalyst(analyzed_news: list[dict]) -> dict:
    """汇总板块催化剂"""
    sector_news = {}
    
    for news in analyzed_news:
        for sector in news.get("related_sectors", []):
            if sector not in sector_news:
                sector_news[sector] = []
            sector_news[sector].append({
                "title": news["source_title"],
                "catalyst_score": news["catalyst_score"],
                "duration": news["duration"],
                "summary": news["summary"],
            })
    
    # 按催化剂评分排序
    for sector in sector_news:
        sector_news[sector].sort(key=lambda x: x["catalyst_score"], reverse=True)
    
    return sector_news


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="消息面 LLM 智能分析")
    parser.add_argument("--title", help="新闻标题")
    parser.add_argument("--content", help="新闻内容")
    parser.add_argument("--batch", help="批量分析 JSON 文件路径")
    parser.add_argument("--min-score", type=float, default=7.0, help="最低催化剂评分")
    
    args = parser.parse_args()
    
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            news_list = json.load(f)
        
        results = batch_analyze_news(news_list)
        high_catalyst = filter_high_catalyst_news(results, args.min_score)
        sector_summary = summarize_sector_catalyst(high_catalyst)
        
        print(f"=== 分析 {len(news_list)} 条新闻 ===")
        print(f"高催化剂新闻: {len(high_catalyst)} 条 (>= {args.min_score})")
        print()
        
        print("=== 板块催化剂汇总 ===")
        for sector, news_items in sector_summary.items():
            print(f"\n{sector} ({len(news_items)} 条)")
            for item in news_items[:3]:  # 只显示前3条
                print(f"  [{item['catalyst_score']:.1f}] {item['title'][:40]}")
                print(f"    持续性: {item['duration']}")
        
        # 保存结果
        output_file = Path(args.batch).parent / f"analyzed_{Path(args.batch).name}"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "analyzed_at": datetime.now().isoformat(),
                "total_news": len(news_list),
                "high_catalyst_count": len(high_catalyst),
                "sector_summary": sector_summary,
                "all_results": results,
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 结果已保存: {output_file}")
    
    elif args.title:
        result = analyze_news_with_llm(args.title, args.content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    else:
        print("错误：需要 --title 或 --batch")
        exit(1)

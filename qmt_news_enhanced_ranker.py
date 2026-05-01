#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息面增强候选打分
将 LLM 分析的消息催化剂融入候选票打分
"""

import json
from pathlib import Path
from datetime import date
from qmt_news_llm_analyzer import batch_analyze_news, filter_high_catalyst_news, summarize_sector_catalyst

HERMES_HOME = Path.home() / ".hermes"
NEWS_DIR = HERMES_HOME / "state" / "qmt_news"


def load_morning_news() -> list[dict]:
    """加载今日早盘新闻"""
    today = date.today().isoformat()
    news_file = NEWS_DIR / f"morning_news_{today}.json"
    
    if not news_file.exists():
        return []
    
    with open(news_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("news", [])


def enrich_candidates_with_news(candidates: list[dict]) -> list[dict]:
    """
    用消息面增强候选票
    
    candidates: qmt_candidate_ranker.py 输出的候选列表
    """
    
    # 1. 加载今日新闻
    news_list = load_morning_news()
    if not news_list:
        print("无今日新闻，跳过消息面增强")
        return candidates
    
    print(f"加载 {len(news_list)} 条新闻")
    
    # 2. LLM 分析新闻
    analyzed_news = batch_analyze_news(news_list)
    high_catalyst = filter_high_catalyst_news(analyzed_news, min_score=6.0)
    sector_summary = summarize_sector_catalyst(high_catalyst)
    
    print(f"高催化剂新闻: {len(high_catalyst)} 条")
    print(f"涉及板块: {len(sector_summary)}")
    
    # 3. 为每个候选票匹配消息催化剂
    for cand in candidates:
        cand_themes = set()
        
        # 收集候选票的所有题材
        if cand.get("trade_theme"):
            cand_themes.add(cand["trade_theme"])
        if cand.get("theme_tags"):
            cand_themes.update(cand["theme_tags"])
        if cand.get("stock_theme_tags"):
            cand_themes.update(cand["stock_theme_tags"])
        
        # 匹配消息催化剂
        matched_news = []
        max_catalyst_score = 0.0
        
        for theme in cand_themes:
            if theme in sector_summary:
                for news_item in sector_summary[theme]:
                    matched_news.append({
                        "theme": theme,
                        "title": news_item["title"],
                        "catalyst_score": news_item["catalyst_score"],
                        "duration": news_item["duration"],
                    })
                    max_catalyst_score = max(max_catalyst_score, news_item["catalyst_score"])
        
        # 更新候选票
        cand["news_catalyst"] = matched_news
        cand["news_catalyst_score"] = max_catalyst_score
        
        # 调整总分：消息催化剂占 15% 权重
        if "score" in cand and max_catalyst_score > 0:
            original_score = cand["score"]
            news_bonus = (max_catalyst_score / 10.0) * 1.5  # 最高加 1.5 分
            cand["score"] = original_score + news_bonus
            cand["score_breakdown"]["消息催化"] = news_bonus
    
    # 4. 重新排序
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return candidates


def generate_news_enhanced_report(candidates: list[dict], output_path: Path):
    """生成消息面增强报告"""
    
    # 统计
    with_news = [c for c in candidates if c.get("news_catalyst_score", 0) > 0]
    
    report = []
    report.append("=== 消息面增强候选报告 ===")
    report.append(f"总候选数: {len(candidates)}")
    report.append(f"有消息催化: {len(with_news)}")
    report.append("")
    
    # A1 主攻
    a1_candidates = [c for c in candidates if c.get("grade") == "A1"]
    if a1_candidates:
        report.append("## A1 主攻")
        for cand in a1_candidates:
            report.append(f"{cand['name']} ({cand['code']}) | 评分 {cand['score']:.1f}")
            report.append(f"  题材: {cand.get('trade_theme', '未知')}")
            report.append(f"  原因: {' | '.join(cand.get('reasons', []))}")
            
            if cand.get("news_catalyst"):
                report.append(f"  消息催化 ({cand['news_catalyst_score']:.1f}):")
                for news in cand["news_catalyst"][:2]:  # 只显示前2条
                    report.append(f"    - [{news['catalyst_score']:.1f}] {news['title'][:40]}")
            report.append("")
    
    # A2 备选
    a2_candidates = [c for c in candidates if c.get("grade") == "A2"]
    if a2_candidates:
        report.append("## A2 备选")
        for cand in a2_candidates[:5]:  # 只显示前5个
            report.append(f"{cand['name']} ({cand['code']}) | 评分 {cand['score']:.1f}")
            if cand.get("news_catalyst"):
                report.append(f"  消息: {cand['news_catalyst'][0]['title'][:40]}")
            report.append("")
    
    # 保存报告
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print(f"✓ 报告已保存: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="消息面增强候选打分")
    parser.add_argument("--input", required=True, help="候选 JSON 文件")
    parser.add_argument("--output", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 加载候选
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
        candidates = data.get("candidates", [])
    
    print(f"加载 {len(candidates)} 个候选")
    
    # 消息面增强
    enhanced_candidates = enrich_candidates_with_news(candidates)
    
    # 保存结果
    output_file = args.output or args.input.replace(".json", "_news_enhanced.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "enhanced_at": date.today().isoformat(),
            "candidates": enhanced_candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 增强结果已保存: {output_file}")
    
    # 生成报告
    report_file = Path(output_file).with_suffix(".txt")
    generate_news_enhanced_report(enhanced_candidates, report_file)

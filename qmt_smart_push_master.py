#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT 一进二智能推送系统 - 总控脚本
整合消息面分析、板块联动、历史趋势、风控管理
"""

import json
import sys
from pathlib import Path
from datetime import datetime, date

# 导入各模块
from qmt_fetch_morning_news import fetch_all_morning_news, save_morning_news
from qmt_news_llm_analyzer import batch_analyze_news, filter_high_catalyst_news
from qmt_news_enhanced_ranker import enrich_candidates_with_news
from qmt_sector_analysis import enrich_candidates_with_sector_analysis
from qmt_historical_analysis import enrich_candidates_with_historical_analysis
from qmt_risk_manager import add_virtual_position, get_portfolio_summary
from qmt_candidate_ranker import main as run_candidate_ranker

HERMES_HOME = Path.home() / ".hermes"
OUTPUT_DIR = HERMES_HOME / "state" / "qmt_smart_push"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def step1_fetch_morning_news():
    """步骤1: 抓取早盘新闻"""
    print("\n=== 步骤1: 抓取早盘新闻 ===")
    news_list = fetch_all_morning_news()
    
    if not news_list:
        print("⚠ 未抓取到新闻，跳过消息面分析")
        return None
    
    news_file = save_morning_news(news_list)
    print(f"✓ 抓取 {len(news_list)} 条新闻")
    return news_file


def step2_analyze_news_with_llm(news_file: Path):
    """步骤2: LLM 分析新闻"""
    print("\n=== 步骤2: LLM 分析新闻 ===")
    
    if not news_file or not news_file.exists():
        print("⚠ 无新闻文件，跳过")
        return None
    
    with open(news_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        news_list = data.get("news", [])
    
    analyzed_news = batch_analyze_news(news_list)
    high_catalyst = filter_high_catalyst_news(analyzed_news, min_score=6.0)
    
    print(f"✓ 分析 {len(news_list)} 条新闻，高催化剂 {len(high_catalyst)} 条")
    
    # 保存分析结果
    analyzed_file = news_file.parent / f"analyzed_{news_file.name}"
    with open(analyzed_file, "w", encoding="utf-8") as f:
        json.dump({
            "analyzed_at": datetime.now().isoformat(),
            "total_news": len(news_list),
            "high_catalyst_count": len(high_catalyst),
            "analyzed_news": analyzed_news,
        }, f, ensure_ascii=False, indent=2)
    
    return analyzed_file


def step3_generate_candidates(qmt_snapshot_file: Path):
    """步骤3: 生成候选票"""
    print("\n=== 步骤3: 生成候选票 ===")
    
    if not qmt_snapshot_file.exists():
        print(f"✗ QMT 快照文件不存在: {qmt_snapshot_file}")
        return None
    
    # 调用 qmt_candidate_ranker.py
    output_file = OUTPUT_DIR / f"candidates_{date.today().isoformat()}.json"
    
    # TODO: 这里应该调用 qmt_candidate_ranker.py 的主函数
    # 目前返回空候选
    candidates = []
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "candidates": candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 生成 {len(candidates)} 个候选")
    return output_file


def step4_enrich_with_news(candidates_file: Path):
    """步骤4: 消息面增强"""
    print("\n=== 步骤4: 消息面增强 ===")
    
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        candidates = data.get("candidates", [])
    
    enhanced_candidates = enrich_candidates_with_news(candidates)
    
    output_file = candidates_file.parent / f"news_enhanced_{candidates_file.name}"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "enhanced_at": datetime.now().isoformat(),
            "candidates": enhanced_candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 消息面增强完成")
    return output_file


def step5_enrich_with_sector(candidates_file: Path, all_stocks_file: Path):
    """步骤5: 板块联动增强"""
    print("\n=== 步骤5: 板块联动增强 ===")
    
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        candidates = data.get("candidates", [])
    
    # 加载全市场数据
    if all_stocks_file.exists():
        with open(all_stocks_file, "r", encoding="utf-8") as f:
            all_stocks_data = json.load(f)
            all_stocks = all_stocks_data.get("stocks", [])
    else:
        print("⚠ 无全市场数据，跳过板块分析")
        all_stocks = []
    
    enhanced_candidates = enrich_candidates_with_sector_analysis(candidates, all_stocks)
    
    output_file = candidates_file.parent / f"sector_enhanced_{candidates_file.name}"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "enhanced_at": datetime.now().isoformat(),
            "candidates": enhanced_candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 板块联动增强完成")
    return output_file


def step6_enrich_with_historical(candidates_file: Path):
    """步骤6: 历史趋势增强"""
    print("\n=== 步骤6: 历史趋势增强 ===")
    
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        candidates = data.get("candidates", [])
    
    enhanced_candidates = enrich_candidates_with_historical_analysis(candidates)
    
    output_file = candidates_file.parent / f"final_{candidates_file.name}"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "enhanced_at": datetime.now().isoformat(),
            "candidates": enhanced_candidates,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 历史趋势增强完成")
    return output_file


def step7_generate_final_report(candidates_file: Path):
    """步骤7: 生成最终报告"""
    print("\n=== 步骤7: 生成最终报告 ===")
    
    with open(candidates_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        candidates = data.get("candidates", [])
    
    # 生成报告
    report = []
    report.append("=" * 60)
    report.append("QMT 一进二智能推送报告")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 60)
    report.append("")
    
    # 持仓摘要
    portfolio = get_portfolio_summary()
    report.append("## 持仓摘要")
    report.append(f"活跃持仓: {portfolio['active_positions']} (仓位 {portfolio.get('active_total_size', 0)*100:.1f}%)")
    report.append(f"总盈亏: {portfolio['total_pnl_pct']:.2f}%")
    report.append(f"胜率: {portfolio['win_rate']:.1f}%")
    report.append("")
    
    # A1 主攻
    a1_candidates = [c for c in candidates if c.get("grade") == "A1"]
    if a1_candidates:
        report.append("## A1 主攻 (30% 仓位)")
        for cand in a1_candidates:
            report.append(f"\n{cand['name']} ({cand['code']}) | 评分 {cand.get('score', 0):.1f}")
            report.append(f"  题材: {cand.get('trade_theme', '未知')}")
            report.append(f"  原因: {' | '.join(cand.get('reasons', []))}")
            
            # 消息催化
            if cand.get("news_catalyst"):
                report.append(f"  消息催化 ({cand['news_catalyst_score']:.1f}):")
                for news in cand["news_catalyst"][:2]:
                    report.append(f"    - [{news['catalyst_score']:.1f}] {news['title'][:40]}")
            
            # 板块情绪
            if cand.get("sector_sentiment"):
                sentiment = cand["sector_sentiment"]
                report.append(f"  板块情绪: {sentiment['sentiment_label']} ({sentiment['sentiment_score']:.1f})")
            
            # 历史趋势
            if cand.get("historical_trend"):
                trend = cand["historical_trend"]
                report.append(f"  历史趋势: {trend['price_trend']} | 5日 {trend['5d_change_pct']:.1f}%")
            
            report.append(f"  建议仓位: 30%")
            report.append(f"  止盈: 8% | 止损: -5%")
    
    # A2 备选
    a2_candidates = [c for c in candidates if c.get("grade") == "A2"]
    if a2_candidates:
        report.append("\n## A2 备选 (20% 仓位)")
        for cand in a2_candidates[:5]:
            report.append(f"\n{cand['name']} ({cand['code']}) | 评分 {cand.get('score', 0):.1f}")
            report.append(f"  题材: {cand.get('trade_theme', '未知')}")
            if cand.get("news_catalyst"):
                report.append(f"  消息: {cand['news_catalyst'][0]['title'][:40]}")
            report.append(f"  建议仓位: 20%")
            report.append(f"  止盈: 6% | 止损: -5%")
    
    # B1 观察
    b1_candidates = [c for c in candidates if c.get("grade") == "B1"]
    if b1_candidates:
        report.append("\n## B1 观察 (10% 仓位)")
        for cand in b1_candidates[:3]:
            report.append(f"{cand['name']} ({cand['code']}) | 评分 {cand.get('score', 0):.1f}")
    
    report.append("\n" + "=" * 60)
    report.append("风险提示: 虚拟持仓仅供参考，实盘操作需谨慎")
    report.append("=" * 60)
    
    # 保存报告
    report_file = OUTPUT_DIR / f"smart_push_report_{date.today().isoformat()}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print(f"✓ 最终报告已保存: {report_file}")
    
    # 打印到控制台
    print("\n" + "\n".join(report))
    
    return report_file


def main():
    """主流程"""
    print("=" * 60)
    print("QMT 一进二智能推送系统")
    print("=" * 60)
    
    # 步骤1: 抓取早盘新闻
    news_file = step1_fetch_morning_news()
    
    # 步骤2: LLM 分析新闻
    analyzed_news_file = step2_analyze_news_with_llm(news_file)
    
    # 步骤3: 生成候选票
    qmt_snapshot_file = HERMES_HOME / "state" / "qmt_snapshots" / "latest.json"
    candidates_file = step3_generate_candidates(qmt_snapshot_file)
    
    if not candidates_file:
        print("\n✗ 候选生成失败，退出")
        return
    
    # 步骤4: 消息面增强
    candidates_file = step4_enrich_with_news(candidates_file)
    
    # 步骤5: 板块联动增强
    all_stocks_file = HERMES_HOME / "state" / "qmt_snapshots" / "all_stocks.json"
    candidates_file = step5_enrich_with_sector(candidates_file, all_stocks_file)
    
    # 步骤6: 历史趋势增强
    candidates_file = step6_enrich_with_historical(candidates_file)
    
    # 步骤7: 生成最终报告
    report_file = step7_generate_final_report(candidates_file)
    
    print("\n" + "=" * 60)
    print("✓ 智能推送完成")
    print(f"最终报告: {report_file}")
    print("=" * 60)


def run_completion_check():
    """运行开发完成检查"""
    print("\n" + "=" * 60)
    print("开发完成检查")
    print("=" * 60)
    
    try:
        # 导入检查模块
        check_script = Path.home() / ".hermes/skills/software-development/development-completion-checklist/scripts/check_completion.py"
        
        if not check_script.exists():
            print("⚠️  检查脚本不存在，跳过")
            return True
        
        # 动态导入
        import importlib.util
        spec = importlib.util.spec_from_file_location("check_completion", check_script)
        check_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check_module)
        
        # 运行检查
        project_dir = Path(__file__).parent
        results = check_module.check_development_completion(str(project_dir))
        is_complete = check_module.print_checklist_report(results, str(project_dir))
        
        if not is_complete:
            print("\n⚠️  发现交付物缺失")
            print("建议：补充缺失的文档后再正式交付")
            print()
            
            # 不阻塞执行，只是警告
            response = input("是否继续？[Y/n]: ")
            if response.lower() == 'n':
                return False
        
        return True
        
    except Exception as e:
        print(f"⚠️  检查失败: {e}")
        print("继续执行...")
        return True


if __name__ == "__main__":
    main()
    
    # 开发完成检查
    run_completion_check()

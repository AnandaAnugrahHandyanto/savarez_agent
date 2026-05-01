#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动跟踪 QMT 推送的候选票，记录虚拟持仓
从盘中推送报告中提取 A1/A2/B1 候选，自动添加到风控系统
"""

import json
import re
from pathlib import Path
from datetime import datetime
from qmt_risk_manager import add_virtual_position

HERMES_HOME = Path.home() / ".hermes"
REPORTS_DIR = HERMES_HOME / "state" / "qmt_reports"


def parse_candidate_from_report(report_path: Path) -> list:
    """从报告中解析候选票"""
    if not report_path.exists():
        return []
    
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    candidates = []
    
    # 匹配格式: A1 主攻 | 300123 | 太阳鸟 | 8.5 | 低空经济 | 高开3.2% + 量能1.5亿
    pattern = r"(A[12]|B[12])\s+\S+\s+\|\s+(\d{6})\s+\|\s+(\S+)\s+\|\s+([\d.]+)\s+\|\s+([^|]+)\s+\|\s+(.+)"
    
    for match in re.finditer(pattern, content):
        grade = match.group(1)
        code = match.group(2)
        name = match.group(3)
        score = float(match.group(4))
        theme = match.group(5).strip()
        reason = match.group(6).strip()
        
        # 提取价格（如果有）
        price_match = re.search(r"价格[：:]\s*([\d.]+)", content)
        price = float(price_match.group(1)) if price_match else 0.0
        
        # 提取消息催化
        news_match = re.search(rf"{name}.*?消息[：:](.+?)(?:\n|$)", content)
        news = news_match.group(1).strip() if news_match else None
        
        candidates.append({
            "grade": grade,
            "code": code,
            "name": name,
            "score": score,
            "theme": theme,
            "reason": reason,
            "price": price,
            "news": news,
        })
    
    return candidates


def auto_track_from_latest_report():
    """从最新报告自动跟踪"""
    if not REPORTS_DIR.exists():
        print("报告目录不存在")
        return
    
    # 找最新的报告
    reports = sorted(REPORTS_DIR.glob("intraday_*.txt"), reverse=True)
    if not reports:
        print("无报告文件")
        return
    
    latest_report = reports[0]
    print(f"读取报告: {latest_report.name}")
    
    candidates = parse_candidate_from_report(latest_report)
    if not candidates:
        print("未找到候选票")
        return
    
    print(f"找到 {len(candidates)} 个候选票")
    
    # 自动添加虚拟持仓
    current_time = datetime.now().isoformat()
    
    for cand in candidates:
        if cand["grade"] not in ["A1", "A2", "B1"]:
            continue  # 只跟踪 A1/A2/B1
        
        if cand["price"] <= 0:
            print(f"跳过 {cand['name']}: 无价格信息")
            continue
        
        position_id = add_virtual_position(
            code=cand["code"],
            name=cand["name"],
            grade=cand["grade"],
            buy_price=cand["price"],
            buy_time=current_time,
            reason=f"{cand['theme']} | {cand['reason']}",
            news_catalyst=cand["news"],
        )
        
        print(f"✓ 添加虚拟持仓: {cand['name']} ({cand['grade']}) @ {cand['price']:.2f}")


if __name__ == "__main__":
    auto_track_from_latest_report()

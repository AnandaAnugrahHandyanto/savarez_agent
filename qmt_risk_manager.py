#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT 虚拟持仓跟踪与风控管理
- 记录每次推送的"虚拟买入"
- 实时跟踪盈亏
- 自动触发止损/止盈提醒
- 仓位管理建议
"""

import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"
STATE_DIR = HERMES_HOME / "state" / "qmt_risk"
STATE_DIR.mkdir(parents=True, exist_ok=True)

POSITIONS_FILE = STATE_DIR / "virtual_positions.json"
ALERTS_FILE = STATE_DIR / "risk_alerts.json"
HISTORY_FILE = STATE_DIR / "trade_history.json"

# 风控规则
RISK_RULES = {
    "stop_loss": {
        "炸板": -3.0,  # 炸板立即止损 -3%
        "封单不足": -2.0,  # 封单 < 1亿，-2% 止损
        "高开回落": -1.5,  # 高开 > 7% 后回落，-1.5% 止损
    },
    "stop_profit": {
        "A1": 8.0,  # A1 主攻：8% 止盈
        "A2": 6.0,  # A2 备选：6% 止盈
        "B1": 4.0,  # B1 观察：4% 止盈
    },
    "position_size": {
        "A1": 0.30,  # 30% 仓位
        "A2": 0.20,  # 20% 仓位
        "B1": 0.10,  # 10% 仓位
        "B2": 0.05,  # 5% 仓位
    },
    "max_single_loss": -5.0,  # 单票最大亏损 -5%
    "max_total_loss": -10.0,  # 总仓位最大亏损 -10%
}


def load_positions() -> dict:
    """加载虚拟持仓"""
    if not POSITIONS_FILE.exists():
        return {}
    with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_positions(positions: dict):
    """保存虚拟持仓"""
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def load_alerts() -> list:
    """加载风控提醒"""
    if not ALERTS_FILE.exists():
        return []
    with open(ALERTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_alerts(alerts: list):
    """保存风控提醒"""
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)


def load_history() -> list:
    """加载交易历史"""
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history: list):
    """保存交易历史"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def add_virtual_position(
    code: str,
    name: str,
    grade: str,
    buy_price: float,
    buy_time: str,
    reason: str,
    news_catalyst: Optional[str] = None,
):
    """添加虚拟持仓"""
    positions = load_positions()
    
    position_id = f"{code}_{buy_time}"
    positions[position_id] = {
        "code": code,
        "name": name,
        "grade": grade,
        "buy_price": buy_price,
        "buy_time": buy_time,
        "reason": reason,
        "news_catalyst": news_catalyst,
        "status": "持仓中",
        "current_price": buy_price,
        "current_pnl_pct": 0.0,
        "max_profit_pct": 0.0,
        "max_loss_pct": 0.0,
        "position_size": RISK_RULES["position_size"].get(grade, 0.05),
    }
    
    save_positions(positions)
    
    # 记录交易历史
    history = load_history()
    history.append({
        "action": "买入",
        "position_id": position_id,
        "code": code,
        "name": name,
        "grade": grade,
        "price": buy_price,
        "time": buy_time,
        "reason": reason,
        "news_catalyst": news_catalyst,
    })
    save_history(history)
    
    return position_id


def update_position_price(code: str, current_price: float, current_time: str):
    """更新持仓价格并检查风控"""
    positions = load_positions()
    alerts = load_alerts()
    
    updated_positions = []
    new_alerts = []
    
    for position_id, pos in positions.items():
        if pos["code"] != code or pos["status"] != "持仓中":
            continue
        
        buy_price = pos["buy_price"]
        pnl_pct = (current_price - buy_price) / buy_price * 100
        
        # 更新持仓数据
        pos["current_price"] = current_price
        pos["current_pnl_pct"] = pnl_pct
        pos["max_profit_pct"] = max(pos["max_profit_pct"], pnl_pct)
        pos["max_loss_pct"] = min(pos["max_loss_pct"], pnl_pct)
        pos["last_update_time"] = current_time
        
        updated_positions.append(position_id)
        
        # 检查止损
        if pnl_pct <= RISK_RULES["max_single_loss"]:
            alert = {
                "type": "止损",
                "level": "严重",
                "position_id": position_id,
                "code": code,
                "name": pos["name"],
                "grade": pos["grade"],
                "buy_price": buy_price,
                "current_price": current_price,
                "pnl_pct": pnl_pct,
                "reason": f"亏损达到 {pnl_pct:.2f}%，触发止损线 {RISK_RULES['max_single_loss']}%",
                "time": current_time,
                "action": "建议立即止损",
            }
            new_alerts.append(alert)
        
        # 检查止盈
        stop_profit_pct = RISK_RULES["stop_profit"].get(pos["grade"], 5.0)
        if pnl_pct >= stop_profit_pct:
            alert = {
                "type": "止盈",
                "level": "提醒",
                "position_id": position_id,
                "code": code,
                "name": pos["name"],
                "grade": pos["grade"],
                "buy_price": buy_price,
                "current_price": current_price,
                "pnl_pct": pnl_pct,
                "reason": f"盈利达到 {pnl_pct:.2f}%，触发止盈线 {stop_profit_pct}%",
                "time": current_time,
                "action": "建议考虑止盈",
            }
            new_alerts.append(alert)
        
        # 检查回撤
        if pos["max_profit_pct"] > 3.0 and pnl_pct < pos["max_profit_pct"] - 3.0:
            alert = {
                "type": "回撤",
                "level": "警告",
                "position_id": position_id,
                "code": code,
                "name": pos["name"],
                "grade": pos["grade"],
                "buy_price": buy_price,
                "current_price": current_price,
                "pnl_pct": pnl_pct,
                "max_profit_pct": pos["max_profit_pct"],
                "reason": f"从最高点 {pos['max_profit_pct']:.2f}% 回撤至 {pnl_pct:.2f}%",
                "time": current_time,
                "action": "建议减仓或止盈",
            }
            new_alerts.append(alert)
    
    save_positions(positions)
    
    if new_alerts:
        alerts.extend(new_alerts)
        save_alerts(alerts)
    
    return {
        "updated_positions": updated_positions,
        "new_alerts": new_alerts,
    }


def close_position(position_id: str, close_price: float, close_time: str, reason: str):
    """平仓"""
    positions = load_positions()
    
    if position_id not in positions:
        return {"error": f"持仓 {position_id} 不存在"}
    
    pos = positions[position_id]
    if pos["status"] != "持仓中":
        return {"error": f"持仓 {position_id} 已平仓"}
    
    buy_price = pos["buy_price"]
    pnl_pct = (close_price - buy_price) / buy_price * 100
    
    pos["status"] = "已平仓"
    pos["close_price"] = close_price
    pos["close_time"] = close_time
    pos["close_reason"] = reason
    pos["final_pnl_pct"] = pnl_pct
    
    save_positions(positions)
    
    # 记录交易历史
    history = load_history()
    history.append({
        "action": "卖出",
        "position_id": position_id,
        "code": pos["code"],
        "name": pos["name"],
        "grade": pos["grade"],
        "buy_price": buy_price,
        "close_price": close_price,
        "pnl_pct": pnl_pct,
        "time": close_time,
        "reason": reason,
    })
    save_history(history)
    
    return {
        "position_id": position_id,
        "code": pos["code"],
        "name": pos["name"],
        "pnl_pct": pnl_pct,
    }


def get_portfolio_summary() -> dict:
    """获取持仓组合摘要"""
    positions = load_positions()
    
    active_positions = [pos for pos in positions.values() if pos["status"] == "持仓中"]
    closed_positions = [pos for pos in positions.values() if pos["status"] == "已平仓"]
    
    if not active_positions and not closed_positions:
        return {
            "total_positions": 0,
            "active_positions": 0,
            "closed_positions": 0,
            "total_pnl_pct": 0.0,
            "win_rate": 0.0,
        }
    
    # 活跃持仓统计
    active_total_pnl = sum(pos["current_pnl_pct"] * pos["position_size"] for pos in active_positions)
    active_total_size = sum(pos["position_size"] for pos in active_positions)
    
    # 已平仓统计
    closed_total_pnl = sum(pos["final_pnl_pct"] * pos["position_size"] for pos in closed_positions)
    closed_total_size = sum(pos["position_size"] for pos in closed_positions)
    
    # 胜率
    win_count = sum(1 for pos in closed_positions if pos["final_pnl_pct"] > 0)
    win_rate = win_count / len(closed_positions) * 100 if closed_positions else 0.0
    
    # 总盈亏
    total_pnl_pct = (active_total_pnl + closed_total_pnl) / (active_total_size + closed_total_size) if (active_total_size + closed_total_size) > 0 else 0.0
    
    return {
        "total_positions": len(positions),
        "active_positions": len(active_positions),
        "closed_positions": len(closed_positions),
        "active_total_size": active_total_size,
        "total_pnl_pct": total_pnl_pct,
        "active_pnl_pct": active_total_pnl / active_total_size if active_total_size > 0 else 0.0,
        "closed_pnl_pct": closed_total_pnl / closed_total_size if closed_total_size > 0 else 0.0,
        "win_rate": win_rate,
        "win_count": win_count,
        "loss_count": len(closed_positions) - win_count,
    }


def get_active_positions() -> list:
    """获取活跃持仓列表"""
    positions = load_positions()
    return [pos for pos in positions.values() if pos["status"] == "持仓中"]


def get_recent_alerts(limit: int = 10) -> list:
    """获取最近的风控提醒"""
    alerts = load_alerts()
    return alerts[-limit:]


def clear_old_alerts(days: int = 7):
    """清理旧提醒"""
    alerts = load_alerts()
    cutoff = datetime.now().timestamp() - days * 86400
    
    filtered = [
        alert for alert in alerts
        if datetime.fromisoformat(alert["time"]).timestamp() > cutoff
    ]
    
    save_alerts(filtered)
    return len(alerts) - len(filtered)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="QMT 虚拟持仓风控管理")
    parser.add_argument("action", choices=["add", "update", "close", "summary", "positions", "alerts", "clear"])
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--name", help="股票名称")
    parser.add_argument("--grade", help="评级 (A1/A2/B1/B2)")
    parser.add_argument("--price", type=float, help="价格")
    parser.add_argument("--time", help="时间 (ISO格式)")
    parser.add_argument("--reason", help="原因")
    parser.add_argument("--news", help="消息催化")
    parser.add_argument("--position-id", help="持仓ID")
    parser.add_argument("--days", type=int, default=7, help="清理天数")
    
    args = parser.parse_args()
    
    if args.action == "add":
        if not all([args.code, args.name, args.grade, args.price, args.time, args.reason]):
            print("错误：add 需要 --code --name --grade --price --time --reason")
            exit(1)
        position_id = add_virtual_position(
            args.code, args.name, args.grade, args.price, args.time, args.reason, args.news
        )
        print(f"✓ 添加虚拟持仓: {position_id}")
    
    elif args.action == "update":
        if not all([args.code, args.price, args.time]):
            print("错误：update 需要 --code --price --time")
            exit(1)
        result = update_position_price(args.code, args.price, args.time)
        print(f"✓ 更新 {len(result['updated_positions'])} 个持仓")
        if result["new_alerts"]:
            print(f"⚠ 触发 {len(result['new_alerts'])} 个风控提醒")
            for alert in result["new_alerts"]:
                print(f"  - [{alert['level']}] {alert['name']} {alert['type']}: {alert['reason']}")
    
    elif args.action == "close":
        if not all([args.position_id, args.price, args.time, args.reason]):
            print("错误：close 需要 --position-id --price --time --reason")
            exit(1)
        result = close_position(args.position_id, args.price, args.time, args.reason)
        if "error" in result:
            print(f"✗ {result['error']}")
        else:
            print(f"✓ 平仓: {result['name']} 盈亏 {result['pnl_pct']:.2f}%")
    
    elif args.action == "summary":
        summary = get_portfolio_summary()
        print("=== 持仓组合摘要 ===")
        print(f"总持仓数: {summary['total_positions']}")
        print(f"活跃持仓: {summary['active_positions']} (仓位 {summary.get('active_total_size', 0)*100:.1f}%)")
        print(f"已平仓: {summary['closed_positions']}")
        print(f"总盈亏: {summary['total_pnl_pct']:.2f}%")
        print(f"活跃盈亏: {summary.get('active_pnl_pct', 0):.2f}%")
        print(f"已平仓盈亏: {summary.get('closed_pnl_pct', 0):.2f}%")
        print(f"胜率: {summary['win_rate']:.1f}% ({summary['win_count']}胜 {summary['loss_count']}负)")
    
    elif args.action == "positions":
        positions = get_active_positions()
        if not positions:
            print("无活跃持仓")
        else:
            print(f"=== 活跃持仓 ({len(positions)}) ===")
            for pos in positions:
                print(f"{pos['name']} ({pos['code']}) [{pos['grade']}]")
                print(f"  买入: {pos['buy_price']:.2f} @ {pos['buy_time']}")
                print(f"  当前: {pos['current_price']:.2f} 盈亏 {pos['current_pnl_pct']:.2f}%")
                print(f"  仓位: {pos['position_size']*100:.1f}%")
                print(f"  原因: {pos['reason']}")
                if pos.get("news_catalyst"):
                    print(f"  消息: {pos['news_catalyst']}")
                print()
    
    elif args.action == "alerts":
        alerts = get_recent_alerts(20)
        if not alerts:
            print("无风控提醒")
        else:
            print(f"=== 最近风控提醒 ({len(alerts)}) ===")
            for alert in alerts:
                print(f"[{alert['level']}] {alert['name']} {alert['type']}")
                print(f"  {alert['reason']}")
                print(f"  {alert['action']}")
                print(f"  时间: {alert['time']}")
                print()
    
    elif args.action == "clear":
        count = clear_old_alerts(args.days)
        print(f"✓ 清理 {count} 条旧提醒 (>{args.days}天)")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时更新虚拟持仓价格并触发风控检查
从 QMT 快照数据中提取最新价格
"""

import json
from pathlib import Path
from datetime import datetime
from qmt_risk_manager import update_position_price, get_active_positions

HERMES_HOME = Path.home() / ".hermes"
QMT_SNAPSHOT_DIR = HERMES_HOME / "state" / "qmt_snapshots"


def load_latest_snapshot() -> dict:
    """加载最新的 QMT 快照"""
    # 使用数据源适配器
    from qmt_data_source import LocalSnapshotDataSource
    
    try:
        source = LocalSnapshotDataSource()
        return source._load_latest_snapshot()
    except Exception as e:
        print(f"加载快照失败: {e}")
        return {}


def update_all_positions():
    """更新所有活跃持仓的价格"""
    active_positions = get_active_positions()
    if not active_positions:
        print("无活跃持仓")
        return
    
    snapshot = load_latest_snapshot()
    if not snapshot:
        print("无快照数据")
        return
    
    # 构建代码 -> 价格映射
    price_map = {}
    for item in snapshot.get("data", []):
        code = item.get("code")
        current_price = item.get("current_price") or item.get("price")
        if code and current_price:
            price_map[code] = float(current_price)
    
    if not price_map:
        print("快照中无价格数据")
        return
    
    current_time = datetime.now().isoformat()
    total_alerts = 0
    
    for pos in active_positions:
        code = pos["code"]
        if code not in price_map:
            continue
        
        current_price = price_map[code]
        result = update_position_price(code, current_price, current_time)
        
        if result["new_alerts"]:
            total_alerts += len(result["new_alerts"])
            print(f"⚠ {pos['name']} 触发 {len(result['new_alerts'])} 个风控提醒")
            for alert in result["new_alerts"]:
                print(f"  [{alert['level']}] {alert['type']}: {alert['reason']}")
                print(f"  {alert['action']}")
    
    print(f"✓ 更新 {len(active_positions)} 个持仓，触发 {total_alerts} 个提醒")


if __name__ == "__main__":
    update_all_positions()

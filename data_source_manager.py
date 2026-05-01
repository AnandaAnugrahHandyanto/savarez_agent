#!/usr/bin/env python3
"""
数据源状态管理
标记数据源降级、失败状态
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

HERMES_HOME = Path.home() / ".hermes"
TEAM_STATE = HERMES_HOME / "state" / "team"
DATA_SOURCE_STATE = TEAM_STATE / "data_source_status.json"

class DataSourceStatus(Enum):
    """数据源状态"""
    NORMAL = "normal"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"

class DataSourceManager:
    """数据源状态管理器"""
    
    def __init__(self):
        self.state_file = DATA_SOURCE_STATE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load_state(self) -> Dict:
        """加载数据源状态"""
        if not self.state_file.exists():
            return {}
        
        with open(self.state_file) as f:
            return json.load(f)
    
    def save_state(self, state: Dict):
        """保存数据源状态"""
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def update_source_status(
        self,
        source_name: str,
        status: DataSourceStatus,
        reason: str = "",
        metadata: Dict = None
    ):
        """更新数据源状态"""
        state = self.load_state()
        
        if source_name not in state:
            state[source_name] = {
                "history": []
            }
        
        state[source_name]["current_status"] = status.value
        state[source_name]["last_updated"] = datetime.now().isoformat()
        state[source_name]["reason"] = reason
        state[source_name]["metadata"] = metadata or {}
        
        # 记录历史
        state[source_name]["history"].append({
            "status": status.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        # 只保留最近 100 条历史
        if len(state[source_name]["history"]) > 100:
            state[source_name]["history"] = state[source_name]["history"][-100:]
        
        self.save_state(state)
    
    def get_source_status(self, source_name: str) -> Optional[Dict]:
        """获取数据源状态"""
        state = self.load_state()
        return state.get(source_name)
    
    def get_all_sources_status(self) -> Dict:
        """获取所有数据源状态"""
        return self.load_state()
    
    def get_degraded_sources(self) -> List[str]:
        """获取降级的数据源列表"""
        state = self.load_state()
        return [
            name for name, info in state.items()
            if info.get("current_status") in [DataSourceStatus.DEGRADED.value, DataSourceStatus.FAILED.value]
        ]
    
    def generate_status_report(self) -> str:
        """生成数据源状态报告"""
        state = self.load_state()
        
        if not state:
            return "无数据源状态记录"
        
        lines = ["数据源状态报告", "=" * 60, ""]
        
        for source_name, info in state.items():
            status = info.get("current_status", "unknown")
            reason = info.get("reason", "")
            last_updated = info.get("last_updated", "")
            
            status_icon = {
                "normal": "✓",
                "degraded": "⚠️",
                "failed": "✗",
                "unknown": "?"
            }.get(status, "?")
            
            lines.append(f"{status_icon} {source_name}: {status}")
            if reason:
                lines.append(f"  原因: {reason}")
            if last_updated:
                lines.append(f"  更新时间: {last_updated}")
            lines.append("")
        
        return "\n".join(lines)


def mark_qmt_degraded(reason: str = "QMT 数据获取失败，已降级为纯 Tushare 模式"):
    """标记 QMT 降级"""
    manager = DataSourceManager()
    manager.update_source_status(
        "QMT",
        DataSourceStatus.DEGRADED,
        reason,
        {"fallback": "Tushare"}
    )


def mark_qmt_normal():
    """标记 QMT 正常"""
    manager = DataSourceManager()
    manager.update_source_status(
        "QMT",
        DataSourceStatus.NORMAL,
        "QMT 数据获取成功"
    )


def check_data_source_warnings() -> List[str]:
    """检查数据源告警"""
    manager = DataSourceManager()
    degraded = manager.get_degraded_sources()
    
    warnings = []
    for source in degraded:
        info = manager.get_source_status(source)
        warnings.append(f"⚠️ {source} 数据源异常: {info.get('reason', '未知原因')}")
    
    return warnings


def main():
    """测试数据源状态管理"""
    manager = DataSourceManager()
    
    # 模拟 QMT 降级
    print("模拟 QMT 降级...")
    mark_qmt_degraded()
    
    # 模拟其他数据源正常
    manager.update_source_status("Tushare", DataSourceStatus.NORMAL, "正常运行")
    manager.update_source_status("财联社", DataSourceStatus.NORMAL, "正常运行")
    manager.update_source_status("雪球", DataSourceStatus.DEGRADED, "Cookie 过期")
    
    # 生成状态报告
    print("\n" + manager.generate_status_report())
    
    # 检查告警
    warnings = check_data_source_warnings()
    if warnings:
        print("数据源告警:")
        for warning in warnings:
            print(f"  {warning}")


if __name__ == "__main__":
    main()

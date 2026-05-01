#!/usr/bin/env python3
"""
数据源健康度监控
每天盘后统计数据源失败情况，连续 3 天失败通知 CIO
"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta
from collections import defaultdict

HERMES_HOME = Path.home() / ".hermes"
TEAM_STATE = HERMES_HOME / "state" / "team"
DATA_SOURCE_STATE = TEAM_STATE / "data_source_status.json"
HEALTH_REPORT = TEAM_STATE / "data_source_health_report.json"

class DataSourceHealthMonitor:
    """数据源健康度监控"""
    
    def __init__(self):
        self.state_file = DATA_SOURCE_STATE
        self.report_file = HEALTH_REPORT
    
    def load_state(self) -> Dict:
        """加载数据源状态"""
        if not self.state_file.exists():
            return {}
        
        with open(self.state_file) as f:
            return json.load(f)
    
    def load_health_report(self) -> Dict:
        """加载健康报告"""
        if not self.report_file.exists():
            return {"daily_stats": {}}
        
        with open(self.report_file) as f:
            return json.load(f)
    
    def save_health_report(self, report: Dict):
        """保存健康报告"""
        with open(self.report_file, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def calculate_daily_stats(self, date: str = None) -> Dict:
        """计算每日统计"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        state = self.load_state()
        
        stats = {
            "date": date,
            "sources": {},
            "summary": {
                "total": len(state),
                "normal": 0,
                "degraded": 0,
                "failed": 0
            }
        }
        
        for source_name, info in state.items():
            status = info.get("current_status", "unknown")
            
            stats["sources"][source_name] = {
                "status": status,
                "reason": info.get("reason", ""),
                "last_updated": info.get("last_updated", "")
            }
            
            if status == "normal":
                stats["summary"]["normal"] += 1
            elif status == "degraded":
                stats["summary"]["degraded"] += 1
            elif status == "failed":
                stats["summary"]["failed"] += 1
        
        return stats
    
    def check_consecutive_failures(self, days: int = 3) -> List[Dict]:
        """检查连续失败的数据源"""
        report = self.load_health_report()
        daily_stats = report.get("daily_stats", {})
        
        # 获取最近 N 天的日期
        dates = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            dates.append(date)
        dates.reverse()
        
        # 统计每个数据源的连续失败天数
        source_failures = defaultdict(int)
        
        for date in dates:
            if date not in daily_stats:
                continue
            
            for source_name, source_info in daily_stats[date]["sources"].items():
                status = source_info.get("status", "unknown")
                if status in ["degraded", "failed"]:
                    source_failures[source_name] += 1
                else:
                    source_failures[source_name] = 0  # 重置计数
        
        # 找出连续失败 >= days 的数据源
        alerts = []
        for source_name, failure_count in source_failures.items():
            if failure_count >= days:
                alerts.append({
                    "source": source_name,
                    "consecutive_failures": failure_count,
                    "severity": "high" if failure_count >= 5 else "medium"
                })
        
        return alerts
    
    def generate_health_report(self) -> str:
        """生成健康报告"""
        # 计算今日统计
        today_stats = self.calculate_daily_stats()
        
        # 检查连续失败
        alerts = self.check_consecutive_failures(days=3)
        
        lines = [
            "数据源健康度报告",
            "=" * 60,
            f"日期: {today_stats['date']}",
            "",
            "今日统计:",
            f"  总数: {today_stats['summary']['total']}",
            f"  正常: {today_stats['summary']['normal']}",
            f"  降级: {today_stats['summary']['degraded']}",
            f"  失败: {today_stats['summary']['failed']}",
            ""
        ]
        
        if alerts:
            lines.append("⚠️ 连续失败告警:")
            for alert in alerts:
                severity_icon = "🔴" if alert["severity"] == "high" else "🟡"
                lines.append(
                    f"  {severity_icon} {alert['source']}: "
                    f"连续 {alert['consecutive_failures']} 天异常"
                )
            lines.append("")
        
        lines.append("数据源详情:")
        for source_name, source_info in today_stats["sources"].items():
            status = source_info["status"]
            status_icon = {
                "normal": "✓",
                "degraded": "⚠️",
                "failed": "✗"
            }.get(status, "?")
            
            lines.append(f"  {status_icon} {source_name}: {status}")
            if source_info["reason"]:
                lines.append(f"    原因: {source_info['reason']}")
        
        return "\n".join(lines)
    
    def update_daily_stats(self):
        """更新每日统计"""
        report = self.load_health_report()
        
        if "daily_stats" not in report:
            report["daily_stats"] = {}
        
        today = datetime.now().strftime("%Y-%m-%d")
        report["daily_stats"][today] = self.calculate_daily_stats(today)
        
        # 只保留最近 30 天的统计
        dates = sorted(report["daily_stats"].keys(), reverse=True)
        if len(dates) > 30:
            for old_date in dates[30:]:
                del report["daily_stats"][old_date]
        
        self.save_health_report(report)


def main():
    """测试健康度监控"""
    monitor = DataSourceHealthMonitor()
    
    # 更新每日统计
    print("更新每日统计...")
    monitor.update_daily_stats()
    
    # 生成健康报告
    print("\n" + monitor.generate_health_report())
    
    # 检查连续失败
    alerts = monitor.check_consecutive_failures(days=3)
    if alerts:
        print("\n需要通知 CIO 的告警:")
        for alert in alerts:
            print(f"  - {alert['source']}: 连续 {alert['consecutive_failures']} 天异常")


if __name__ == "__main__":
    main()

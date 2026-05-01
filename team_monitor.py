#!/usr/bin/env python3
"""
Hermes Team 实时监控
监控工作流执行、数据源健康、推送成功率等指标
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List

HERMES_HOME = Path.home() / ".hermes"
TEAM_STATE = HERMES_HOME / "state" / "team"
RUNTIME = HERMES_HOME / "runtime-hermes-agent"

sys.path.insert(0, str(RUNTIME))

from data_source_manager import DataSourceManager
from data_source_health_monitor import DataSourceHealthMonitor


class TeamMonitor:
    """团队实时监控"""
    
    def __init__(self):
        self.team_state = TEAM_STATE
        self.hermes_home = HERMES_HOME
    
    def load_cron_jobs(self) -> List[Dict]:
        """加载 cron 任务"""
        cron_file = self.hermes_home / "cron" / "jobs.json"
        if not cron_file.exists():
            return []
        
        with open(cron_file) as f:
            data = json.load(f)
            return data.get("jobs", [])
    
    def get_workflow_status(self) -> Dict:
        """获取工作流执行状态"""
        jobs = self.load_cron_jobs()
        
        # 统计各类任务
        total = len(jobs)
        enabled = sum(1 for j in jobs if j.get("enabled"))
        scheduled = sum(1 for j in jobs if j.get("state") == "scheduled")
        completed = sum(1 for j in jobs if j.get("state") == "completed")
        failed = sum(1 for j in jobs if j.get("last_status") == "error")
        
        # 最近执行的任务
        recent_jobs = sorted(
            [j for j in jobs if j.get("last_run_at")],
            key=lambda x: x.get("last_run_at", ""),
            reverse=True
        )[:5]
        
        return {
            "total": total,
            "enabled": enabled,
            "scheduled": scheduled,
            "completed": completed,
            "failed": failed,
            "recent_jobs": recent_jobs
        }
    
    def get_data_source_health(self) -> Dict:
        """获取数据源健康度"""
        monitor = DataSourceHealthMonitor()
        stats = monitor.calculate_daily_stats()
        
        return {
            "total": stats["summary"]["total"],
            "normal": stats["summary"]["normal"],
            "degraded": stats["summary"]["degraded"],
            "failed": stats["summary"]["failed"],
            "sources": stats["sources"]
        }
    
    def get_approval_stats(self) -> Dict:
        """获取审批统计"""
        approvals_file = self.team_state / "approvals.json"
        if not approvals_file.exists():
            return {"pending": 0, "approved": 0, "rejected": 0, "auto_rate": 0}
        
        with open(approvals_file) as f:
            data = json.load(f)
            if isinstance(data, list):
                data = {"pending": [], "approved": data, "rejected": []}
        
        approved = data.get("approved", [])
        auto_approved = sum(1 for a in approved if a.get("auto", False))
        
        return {
            "pending": len(data.get("pending", [])),
            "approved": len(approved),
            "rejected": len(data.get("rejected", [])),
            "auto_rate": (auto_approved / len(approved) * 100) if approved else 0
        }
    
    def get_dedupe_stats(self) -> Dict:
        """获取去重统计"""
        dedupe_dir = self.team_state / "dedupe_baselines"
        if not dedupe_dir.exists():
            return {"baselines": 0, "report_types": []}
        
        baselines = list(dedupe_dir.glob("*_baseline.json"))
        report_types = [b.stem.replace("_baseline", "") for b in baselines]
        
        return {
            "baselines": len(baselines),
            "report_types": report_types
        }
    
    def get_push_success_rate(self) -> float:
        """获取推送成功率"""
        jobs = self.load_cron_jobs()
        
        # 统计最近的推送任务
        push_jobs = [j for j in jobs if "push" in j.get("name", "").lower() or "feishu" in j.get("deliver", "")]
        
        if not push_jobs:
            return 0.0
        
        success = sum(1 for j in push_jobs if j.get("last_status") == "ok")
        
        return (success / len(push_jobs) * 100) if push_jobs else 0.0
    
    def generate_monitor_report(self) -> str:
        """生成监控报告"""
        # 收集指标
        workflow_status = self.get_workflow_status()
        data_source_health = self.get_data_source_health()
        approval_stats = self.get_approval_stats()
        dedupe_stats = self.get_dedupe_stats()
        push_success_rate = self.get_push_success_rate()
        
        lines = [
            "Hermes Team 实时监控报告",
            "=" * 60,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "【工作流执行状态】",
            f"  总任务数: {workflow_status['total']}",
            f"  已启用: {workflow_status['enabled']}",
            f"  已调度: {workflow_status['scheduled']}",
            f"  已完成: {workflow_status['completed']}",
            f"  失败: {workflow_status['failed']}",
            ""
        ]
        
        if workflow_status['recent_jobs']:
            lines.append("  最近执行:")
            for job in workflow_status['recent_jobs'][:3]:
                status_icon = "✓" if job.get("last_status") == "ok" else "✗"
                lines.append(f"    {status_icon} {job.get('name', 'N/A')} ({job.get('last_run_at', 'N/A')})")
            lines.append("")
        
        lines.extend([
            "【数据源健康度】",
            f"  总数: {data_source_health['total']}",
            f"  正常: {data_source_health['normal']}",
            f"  降级: {data_source_health['degraded']}",
            f"  失败: {data_source_health['failed']}",
            ""
        ])
        
        if data_source_health['degraded'] > 0 or data_source_health['failed'] > 0:
            lines.append("  异常数据源:")
            for source_name, source_info in data_source_health['sources'].items():
                if source_info['status'] in ['degraded', 'failed']:
                    icon = "⚠️" if source_info['status'] == 'degraded' else "✗"
                    lines.append(f"    {icon} {source_name}: {source_info['reason']}")
            lines.append("")
        
        lines.extend([
            "【审批统计】",
            f"  待审批: {approval_stats['pending']}",
            f"  已通过: {approval_stats['approved']}",
            f"  已驳回: {approval_stats['rejected']}",
            f"  自动审批率: {approval_stats['auto_rate']:.1f}%",
            "",
            "【去重统计】",
            f"  基线数量: {dedupe_stats['baselines']}",
            f"  报告类型: {', '.join(dedupe_stats['report_types']) if dedupe_stats['report_types'] else 'N/A'}",
            "",
            "【推送成功率】",
            f"  成功率: {push_success_rate:.1f}%",
            ""
        ])
        
        # 健康评分
        health_score = self._calculate_health_score(
            workflow_status,
            data_source_health,
            approval_stats,
            push_success_rate
        )
        
        lines.extend([
            "【整体健康评分】",
            f"  评分: {health_score}/100",
            f"  状态: {self._get_health_status(health_score)}",
            ""
        ])
        
        return "\n".join(lines)
    
    def _calculate_health_score(
        self,
        workflow_status: Dict,
        data_source_health: Dict,
        approval_stats: Dict,
        push_success_rate: float
    ) -> int:
        """计算健康评分"""
        score = 100
        
        # 工作流失败扣分
        if workflow_status['failed'] > 0:
            score -= workflow_status['failed'] * 10
        
        # 数据源异常扣分
        score -= data_source_health['degraded'] * 5
        score -= data_source_health['failed'] * 10
        
        # 推送成功率加分
        if push_success_rate >= 95:
            score += 0
        elif push_success_rate >= 80:
            score -= 5
        else:
            score -= 15
        
        # 审批积压扣分
        if approval_stats['pending'] > 5:
            score -= 10
        
        return max(0, min(100, score))
    
    def _get_health_status(self, score: int) -> str:
        """获取健康状态"""
        if score >= 90:
            return "✓ 优秀"
        elif score >= 75:
            return "⚠️ 良好"
        elif score >= 60:
            return "⚠️ 一般"
        else:
            return "✗ 需要关注"
    
    def check_alerts(self) -> List[str]:
        """检查告警"""
        alerts = []
        
        # 检查工作流失败
        workflow_status = self.get_workflow_status()
        if workflow_status['failed'] > 0:
            alerts.append(f"🔴 {workflow_status['failed']} 个工作流执行失败")
        
        # 检查数据源异常
        data_source_health = self.get_data_source_health()
        if data_source_health['failed'] > 0:
            alerts.append(f"🔴 {data_source_health['failed']} 个数据源失败")
        if data_source_health['degraded'] > 0:
            alerts.append(f"🟡 {data_source_health['degraded']} 个数据源降级")
        
        # 检查审批积压
        approval_stats = self.get_approval_stats()
        if approval_stats['pending'] > 5:
            alerts.append(f"🟡 {approval_stats['pending']} 个审批待处理")
        
        # 检查推送成功率
        push_success_rate = self.get_push_success_rate()
        if push_success_rate < 80:
            alerts.append(f"🔴 推送成功率过低: {push_success_rate:.1f}%")
        
        return alerts


def main():
    """生成监控报告"""
    monitor = TeamMonitor()
    
    # 生成报告
    report = monitor.generate_monitor_report()
    print(report)
    
    # 检查告警
    alerts = monitor.check_alerts()
    if alerts:
        print("【告警】")
        for alert in alerts:
            print(f"  {alert}")
        print()
    
    # 保存报告
    report_file = TEAM_STATE / f"monitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report)
    print(f"报告已保存到: {report_file}")


if __name__ == "__main__":
    main()

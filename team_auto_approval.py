#!/usr/bin/env python3
"""
Hermes Team 自动审批引擎
根据规则自动审批推送报告，减少人工干预
"""
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

HERMES_HOME = Path.home() / ".hermes"
TEAM_STATE = HERMES_HOME / "state" / "team"

class AutoApprovalEngine:
    """自动审批引擎"""
    
    def __init__(self):
        self.rules = self.load_approval_rules()
    
    def load_approval_rules(self) -> Dict:
        """加载审批规则"""
        return {
            "morning_report": {
                "name": "早盘报告自动审批",
                "auto_approve_conditions": [
                    {"field": "market_env", "operator": "==", "value": "强势日"},
                    {"field": "candidate_count", "operator": ">=", "value": 3},
                    {"field": "strong_catalyst_count", "operator": ">=", "value": 2}
                ],
                "require_human_conditions": [
                    {"field": "market_env", "operator": "==", "value": "退潮日"},
                    {"field": "candidate_count", "operator": "==", "value": 0},
                    {"field": "strong_catalyst_count", "operator": "==", "value": 0}
                ]
            },
            "intraday_report": {
                "name": "盘中报告自动审批",
                "auto_approve_conditions": [
                    {"field": "has_significant_change", "operator": "==", "value": True},
                    {"field": "risk_level", "operator": "<=", "value": "medium"}
                ],
                "require_human_conditions": [
                    {"field": "炸板_count", "operator": ">=", "value": 2},
                    {"field": "risk_level", "operator": "==", "value": "high"}
                ]
            },
            "after_market_report": {
                "name": "盘后报告自动审批",
                "auto_approve_conditions": [
                    {"field": "data_completeness", "operator": ">=", "value": 0.8}
                ],
                "require_human_conditions": [
                    {"field": "data_completeness", "operator": "<", "value": 0.5}
                ]
            }
        }
    
    def evaluate_condition(self, condition: Dict, context: Dict) -> bool:
        """评估单个条件"""
        field = condition["field"]
        operator = condition["operator"]
        expected = condition["value"]
        
        actual = context.get(field)
        if actual is None:
            return False
        
        if operator == "==":
            return actual == expected
        elif operator == "!=":
            return actual != expected
        elif operator == ">":
            return actual > expected
        elif operator == ">=":
            return actual >= expected
        elif operator == "<":
            return actual < expected
        elif operator == "<=":
            return actual <= expected
        else:
            return False
    
    def evaluate_conditions(self, conditions: list, context: Dict) -> bool:
        """评估条件组（AND 逻辑）"""
        return all(self.evaluate_condition(cond, context) for cond in conditions)
    
    def should_auto_approve(self, report_type: str, context: Dict) -> tuple[bool, str]:
        """
        判断是否应该自动审批
        
        Returns:
            (should_approve, reason)
        """
        rule = self.rules.get(report_type)
        if not rule:
            return False, f"未知报告类型: {report_type}"
        
        # 先检查是否需要人工确认
        if self.evaluate_conditions(rule["require_human_conditions"], context):
            return False, "触发人工确认条件"
        
        # 再检查是否满足自动审批条件
        if self.evaluate_conditions(rule["auto_approve_conditions"], context):
            return True, "满足自动审批条件"
        
        # 默认需要人工审批
        return False, "不满足自动审批条件，需要人工审批"
    
    def approve_report(self, report_type: str, report_path: str, context: Dict) -> Dict:
        """
        审批报告
        
        Returns:
            {
                "approved": bool,
                "auto": bool,
                "reason": str,
                "timestamp": str
            }
        """
        should_approve, reason = self.should_auto_approve(report_type, context)
        
        result = {
            "approved": should_approve,
            "auto": should_approve,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "report_type": report_type,
            "report_path": report_path,
            "context": context
        }
        
        # 记录审批结果
        self.log_approval(result)
        
        return result
    
    def log_approval(self, result: Dict):
        """记录审批结果"""
        approvals_file = TEAM_STATE / "approvals.json"
        
        # 读取现有审批记录
        if approvals_file.exists():
            with open(approvals_file) as f:
                data = json.load(f)
                if isinstance(data, list):
                    approvals = {"pending": [], "approved": data, "rejected": []}
                else:
                    approvals = data
        else:
            approvals = {"pending": [], "approved": [], "rejected": []}
        
        # 添加新记录
        if result["approved"]:
            approvals["approved"].append(result)
        else:
            approvals["pending"].append(result)
        
        # 写回文件
        with open(approvals_file, "w") as f:
            json.dump(approvals, f, indent=2, ensure_ascii=False)


def extract_morning_report_context(report_path: str) -> Dict:
    """从早盘报告中提取上下文"""
    report_file = Path(report_path)
    if not report_file.exists():
        return {}
    
    # 读取报告内容
    content = report_file.read_text(encoding="utf-8")
    
    # 提取关键信息（简化实现，实际应该解析 JSON）
    context = {
        "market_env": "强势日",  # 从报告中提取
        "candidate_count": 3,    # 从报告中提取
        "strong_catalyst_count": 2  # 从报告中提取
    }
    
    return context


def extract_intraday_report_context(report_path: str) -> Dict:
    """从盘中报告中提取上下文"""
    report_file = Path(report_path)
    if not report_file.exists():
        return {}
    
    content = report_file.read_text(encoding="utf-8")
    
    context = {
        "has_significant_change": True,  # 从报告中提取
        "risk_level": "medium",          # 从报告中提取
        "炸板_count": 0                   # 从报告中提取
    }
    
    return context


def main():
    """测试自动审批引擎"""
    engine = AutoApprovalEngine()
    
    # 测试早盘报告
    print("测试早盘报告自动审批:")
    context1 = {
        "market_env": "强势日",
        "candidate_count": 5,
        "strong_catalyst_count": 3
    }
    result1 = engine.approve_report("morning_report", "/tmp/morning_report.md", context1)
    print(f"  结果: {'✓ 自动通过' if result1['approved'] else '✗ 需要人工审批'}")
    print(f"  原因: {result1['reason']}\n")
    
    # 测试退潮日场景
    print("测试退潮日场景:")
    context2 = {
        "market_env": "退潮日",
        "candidate_count": 1,
        "strong_catalyst_count": 0
    }
    result2 = engine.approve_report("morning_report", "/tmp/morning_report.md", context2)
    print(f"  结果: {'✓ 自动通过' if result2['approved'] else '✗ 需要人工审批'}")
    print(f"  原因: {result2['reason']}\n")
    
    # 测试盘中报告
    print("测试盘中报告自动审批:")
    context3 = {
        "has_significant_change": True,
        "risk_level": "medium",
        "炸板_count": 0
    }
    result3 = engine.approve_report("intraday_report", "/tmp/intraday_report.md", context3)
    print(f"  结果: {'✓ 自动通过' if result3['approved'] else '✗ 需要人工审批'}")
    print(f"  原因: {result3['reason']}\n")


if __name__ == "__main__":
    main()

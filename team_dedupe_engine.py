#!/usr/bin/env python3
"""
Hermes Team 推送去重引擎
在推送前检查内容是否变化，推送成功后才提交基线
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

HERMES_HOME = Path.home() / ".hermes"
TEAM_STATE = HERMES_HOME / "state" / "team"
DEDUPE_STATE = TEAM_STATE / "dedupe_baselines"

class DedupeEngine:
    """去重引擎"""
    
    def __init__(self):
        DEDUPE_STATE.mkdir(parents=True, exist_ok=True)
    
    def normalize_content(self, content: str) -> str:
        """
        归一化内容（去除时间戳等动态字段）
        """
        lines = content.split("\n")
        normalized = []
        
        for line in lines:
            stripped = line.strip()
            # 跳过空行
            if not stripped:
                continue
            # 跳过时间戳行
            if any(x in stripped for x in ["生成时间:", "推送时间:", "timestamp:", "Generated at"]):
                continue
            normalized.append(stripped)
        
        return "\n".join(normalized)
    
    def compute_hash(self, content: str) -> str:
        """计算内容哈希"""
        normalized = self.normalize_content(content)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    
    def get_baseline_path(self, report_type: str) -> Path:
        """获取基线文件路径"""
        return DEDUPE_STATE / f"{report_type}_baseline.json"
    
    def load_baseline(self, report_type: str) -> Optional[Dict]:
        """加载基线"""
        baseline_path = self.get_baseline_path(report_type)
        if not baseline_path.exists():
            return None
        
        with open(baseline_path) as f:
            return json.load(f)
    
    def save_baseline(self, report_type: str, content_hash: str, metadata: Dict):
        """保存基线"""
        baseline_path = self.get_baseline_path(report_type)
        
        baseline = {
            "content_hash": content_hash,
            "last_delivered_at": datetime.now().isoformat(),
            "metadata": metadata
        }
        
        with open(baseline_path, "w") as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    def check_should_deliver(self, report_type: str, content: str) -> tuple[bool, str, str]:
        """
        检查是否应该推送
        
        Returns:
            (should_deliver, reason, content_hash)
        """
        content_hash = self.compute_hash(content)
        baseline = self.load_baseline(report_type)
        
        if baseline is None:
            return True, "首次推送", content_hash
        
        if baseline["content_hash"] == content_hash:
            return False, "内容未变化", content_hash
        
        return True, "内容已变化", content_hash
    
    def commit_delivery(self, report_type: str, content: str, metadata: Dict = None):
        """
        提交推送成功的基线
        只在推送成功后调用
        """
        content_hash = self.compute_hash(content)
        self.save_baseline(report_type, content_hash, metadata or {})


def check_report_change(report_type: str, report_path: str, commit: bool = False) -> Dict:
    """
    检查报告是否变化
    
    Args:
        report_type: 报告类型（morning_report/intraday_report/after_market_report）
        report_path: 报告文件路径
        commit: 是否提交基线（只在推送成功后设为 True）
    
    Returns:
        {
            "status": "CHANGED" | "UNCHANGED" | "MISSING",
            "content_hash": str,
            "reason": str,
            "state_committed": bool
        }
    """
    engine = DedupeEngine()
    
    # 检查报告文件是否存在
    report_file = Path(report_path)
    if not report_file.exists():
        return {
            "status": "MISSING",
            "content_hash": None,
            "reason": f"报告文件不存在: {report_path}",
            "state_committed": False
        }
    
    # 读取报告内容
    content = report_file.read_text(encoding="utf-8")
    
    # 检查是否应该推送
    should_deliver, reason, content_hash = engine.check_should_deliver(report_type, content)
    
    # 如果需要提交基线
    if commit and should_deliver:
        engine.commit_delivery(report_type, content, {"report_path": report_path})
        state_committed = True
    else:
        state_committed = False
    
    return {
        "status": "CHANGED" if should_deliver else "UNCHANGED",
        "content_hash": content_hash,
        "reason": reason,
        "state_committed": state_committed
    }


def main():
    """测试去重引擎"""
    import sys
    
    if len(sys.argv) < 3:
        print("用法: team_dedupe_engine.py <report_type> <report_path> [--commit]")
        sys.exit(1)
    
    report_type = sys.argv[1]
    report_path = sys.argv[2]
    commit = "--commit" in sys.argv
    
    result = check_report_change(report_type, report_path, commit)
    
    print(f"STATUS={result['status']}")
    print(f"CONTENT_HASH={result['content_hash']}")
    print(f"REASON={result['reason']}")
    print(f"STATE_COMMITTED={1 if result['state_committed'] else 0}")
    
    # 返回状态码
    sys.exit(0 if result['status'] == "CHANGED" else 1)


if __name__ == "__main__":
    main()

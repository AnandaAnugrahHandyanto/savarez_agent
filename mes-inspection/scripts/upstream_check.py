"""轻量 HTTP 上游端点存活检查器 — 心跳巡检专用。

只检查 HTTP 端点是否返回 2xx，不执行 SSH、不解析日志。
适用于高频心跳（2 分钟）场景。
"""

import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.base_checker import BaseChecker, CheckResult, ExitCode, InspectionReport


class UpstreamChecker(BaseChecker):

    @property
    def component_name(self) -> str:
        return "upstream"

    def check(self) -> InspectionReport:
        targets = self.config.get("targets", [])
        if not targets:
            return InspectionReport(
                component=self.component_name,
                timestamp=self._now_iso(),
                status=ExitCode.CRITICAL,
                checks=[self.make_check("配置", ExitCode.CRITICAL, value=None, message="未配置 upstream targets")],
                summary="未配置上游端点",
                metadata={"node_count": 0, "nodes": {}},
            )

        return self.check_all_targets()

    def check_node(self, target: Dict[str, Any]) -> InspectionReport:
        checks = [self._check_endpoint(target)]
        status = self.overall_status(checks)
        return InspectionReport(
            component=self.component_name,
            timestamp=self._now_iso(),
            status=status,
            checks=checks,
            summary=f"端点 {target.get('name', 'unknown')} {'正常' if status == ExitCode.NORMAL else '异常'}",
        )

    def _check_endpoint(self, target: Dict[str, Any]) -> CheckResult:
        url = target.get("url", "")
        name = target.get("name", url)
        timeout = self.config.get("timeout", 5)
        warn_time = self.config.get("response_time_warn", 2.0)
        crit_time = self.config.get("response_time_critical", 5.0)

        if not url:
            return self.make_check(
                f"端点 [{name}]", ExitCode.CRITICAL,
                value=None, message="URL 未配置",
            )

        start = time.time()
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                elapsed = time.time() - start

                if not (200 <= code < 300):
                    return self.make_check(
                        f"端点 [{name}]", ExitCode.CRITICAL,
                        value=code, threshold="2xx",
                        message=f"HTTP {code}，耗时 {elapsed:.3f}s",
                    )

                if elapsed >= crit_time:
                    status = ExitCode.CRITICAL
                elif elapsed >= warn_time:
                    status = ExitCode.WARNING
                else:
                    status = ExitCode.NORMAL

                return self.make_check(
                    f"端点 [{name}]", status,
                    value=round(elapsed, 3),
                    threshold=f"warn={warn_time}s,critical={crit_time}s",
                    message=f"HTTP {code}，耗时 {elapsed:.3f}s",
                )
        except Exception as e:
            elapsed = time.time() - start
            return self.make_check(
                f"端点 [{name}]", ExitCode.CRITICAL,
                value=None, message=f"连接失败: {e}，耗时 {elapsed:.3f}s",
            )

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    from config.config_manager import ConfigManager
    cfg = ConfigManager()
    cfg.load()
    checker = UpstreamChecker(cfg.get_component_config("upstream"))
    sys.exit(checker.run())

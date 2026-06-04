"""RabbitMQ 巡检脚本 — 检查服务存活、队列深度、消费者、内存与磁盘。"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

from scripts.base_checker import BaseChecker, CheckResult, ExitCode, InspectionReport
from datetime import datetime, timezone


class RabbitMQChecker(BaseChecker):

    @property
    def component_name(self) -> str:
        return "rabbitmq"

    def check(self) -> InspectionReport:
        checks: List[CheckResult] = []

        alive, alive_detail = self._check_alive()
        checks.append(alive)

        if alive.status == ExitCode.CRITICAL:
            return self._report(checks, "RabbitMQ 服务不可用", {"alive_detail": alive_detail})

        # 尝试 Management API，失败则 fallback 到 CLI
        use_api = self._api_available()
        if use_api:
            overview = self._api_overview()
            checks.extend(self._check_queues_api(overview))
            checks.append(self._check_memory_api(overview))
            checks.append(self._check_disk_api(overview))
        else:
            queues_info = self._cli_list_queues()
            checks.extend(self._check_queues_cli(queues_info))
            status_info = self._cli_status()
            checks.append(self._check_memory_cli(status_info))
            checks.append(self._check_disk_cli(status_info))

        return self._report(checks, self._build_summary(checks), {"mode": "api" if use_api else "cli"})

    # ── 服务存活 ──────────────────────────────────────────────

    def _check_alive(self) -> Tuple[CheckResult, str]:
        # 优先 systemctl
        r = self.run_command("systemctl is-active rabbitmq-server", timeout=10)
        if r.returncode == 0 and "active" in r.stdout.strip().lower():
            return self.make_check("服务存活", ExitCode.NORMAL, value="running", message="rabbitmq-server 运行中"), ""

        # fallback: rabbitmqctl status
        r = self.run_command("rabbitmqctl status", timeout=15)
        if r.returncode == 0:
            return self.make_check("服务存活", ExitCode.NORMAL, value="running", message="rabbitmqctl status 正常"), ""

        return (
            self.make_check("服务存活", ExitCode.CRITICAL, value="down", message="RabbitMQ 服务不可用"),
            r.stderr.strip() or r.stdout.strip(),
        )

    # ── Management API ────────────────────────────────────────

    def _api_available(self) -> bool:
        url = self.config.get("management_url", "http://localhost:15672")
        r = self.run_command(f"curl -s -o /dev/null -w '%{{http_code}}' {url}/api/overview", timeout=5)
        return r.returncode == 0 and "200" in r.stdout

    def _api_overview(self) -> dict:
        url = self.config.get("management_url", "http://localhost:15672")
        user = self.config.get("management_user", "guest")
        pw = self.config.get("management_password", "guest")
        r = self.run_command(f'curl -s -u {user}:{pw} {url}/api/overview', timeout=10)
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        return {}

    def _api_queue_list(self) -> list:
        url = self.config.get("management_url", "http://localhost:15672")
        user = self.config.get("management_user", "guest")
        pw = self.config.get("management_password", "guest")
        r = self.run_command(f'curl -s -u {user}:{pw} {url}/api/queues', timeout=15)
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        return []

    def _check_queues_api(self, overview: dict) -> List[CheckResult]:
        checks = []
        queues = self._api_queue_list()
        warn = self.config.get("queue_depth_warn", 1000)
        crit = self.config.get("queue_depth_critical", 10000)

        no_consumer_queues = []
        for q in queues:
            name = q.get("name", "?")
            msgs = q.get("messages", 0)
            consumers = q.get("consumers", 0)

            if msgs >= crit:
                status = ExitCode.CRITICAL
            elif msgs >= warn:
                status = ExitCode.WARNING
            else:
                status = ExitCode.NORMAL

            checks.append(self.make_check(
                f"队列深度: {name}", status, value=msgs, threshold=f"warn={warn},crit={crit}",
                message=f"{name}: {msgs} 条消息, {consumers} 个消费者",
            ))
            if consumers == 0 and msgs > 0:
                no_consumer_queues.append(name)

        if no_consumer_queues:
            checks.append(self.make_check(
                "无消费者队列", ExitCode.WARNING,
                value=len(no_consumer_queues),
                message=f"以下队列有消息但无消费者: {', '.join(no_consumer_queues)}",
            ))
        else:
            checks.append(self.make_check("无消费者队列", ExitCode.NORMAL, value=0, message="所有有消息的队列均有消费者"))

        return checks

    def _check_memory_api(self, overview: dict) -> CheckResult:
        mem_used = overview.get("object_totals", {}).get("channels", 0)  # placeholder
        # 从 /api/nodes 获取更准确的内存数据
        url = self.config.get("management_url", "http://localhost:15672")
        user = self.config.get("management_user", "guest")
        pw = self.config.get("management_password", "guest")
        r = self.run_command(f'curl -s -u {user}:{pw} {url}/api/nodes', timeout=10)
        if r.returncode == 0:
            try:
                nodes = json.loads(r.stdout)
                if nodes:
                    node = nodes[0]
                    mem_used = node.get("mem_used", 0)
                    mem_limit = node.get("mem_limit", 1)
                    pct = (mem_used / mem_limit * 100) if mem_limit else 0
                    return self._memory_result(pct, mem_used, mem_limit)
            except (json.JSONDecodeError, ZeroDivisionError):
                pass
        return self.make_check("节点内存", ExitCode.WARNING, message="无法通过 API 获取内存信息")

    def _check_disk_api(self, overview: dict) -> CheckResult:
        url = self.config.get("management_url", "http://localhost:15672")
        user = self.config.get("management_user", "guest")
        pw = self.config.get("management_password", "guest")
        r = self.run_command(f'curl -s -u {user}:{pw} {url}/api/nodes', timeout=10)
        if r.returncode == 0:
            try:
                nodes = json.loads(r.stdout)
                if nodes:
                    node = nodes[0]
                    disk_free = node.get("disk_free", 0)
                    disk_limit = node.get("disk_free_limit", 1)
                    if disk_limit > 0:
                        pct = disk_free / (disk_free + disk_limit) * 100 if (disk_free + disk_limit) > 0 else 100
                    else:
                        pct = 100
                    return self._disk_result(disk_free, disk_limit, pct)
            except (json.JSONDecodeError, ZeroDivisionError):
                pass
        return self.make_check("磁盘空间", ExitCode.WARNING, message="无法通过 API 获取磁盘信息")

    # ── CLI fallback ──────────────────────────────────────────

    def _cli_list_queues(self) -> str:
        r = self.run_command("rabbitmqctl list_queues name messages consumers", timeout=15)
        return r.stdout if r.returncode == 0 else ""

    def _cli_status(self) -> str:
        r = self.run_command("rabbitmqctl status", timeout=15)
        return r.stdout if r.returncode == 0 else ""

    def _check_queues_cli(self, raw: str) -> List[CheckResult]:
        checks = []
        warn = self.config.get("queue_depth_warn", 1000)
        crit = self.config.get("queue_depth_critical", 10000)
        no_consumer_queues = []

        for line in raw.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 3 or not parts[0] or parts[0] == "name":
                continue
            name, msgs_str, cons_str = parts[0], parts[1], parts[2]
            try:
                msgs = int(msgs_str)
                consumers = int(cons_str)
            except ValueError:
                continue

            if msgs >= crit:
                status = ExitCode.CRITICAL
            elif msgs >= warn:
                status = ExitCode.WARNING
            else:
                status = ExitCode.NORMAL

            checks.append(self.make_check(
                f"队列深度: {name}", status, value=msgs, threshold=f"warn={warn},crit={crit}",
                message=f"{name}: {msgs} 条消息, {consumers} 个消费者",
            ))
            if consumers == 0 and msgs > 0:
                no_consumer_queues.append(name)

        if no_consumer_queues:
            checks.append(self.make_check(
                "无消费者队列", ExitCode.WARNING,
                value=len(no_consumer_queues),
                message=f"以下队列有消息但无消费者: {', '.join(no_consumer_queues)}",
            ))
        else:
            checks.append(self.make_check("无消费者队列", ExitCode.NORMAL, value=0, message="所有有消息的队列均有消费者"))

        return checks

    def _check_memory_cli(self, raw: str) -> CheckResult:
        # rabbitmqctl status 输出含 {mem_used, ...} 或 memory 字段
        match = re.search(r"mem_used\s*,\s*(\d+)", raw)
        match_limit = re.search(r"mem_limit\s*,\s*(\d+)", raw)
        if match and match_limit:
            mem_used = int(match.group(1))
            mem_limit = int(match_limit.group(1))
            pct = (mem_used / mem_limit * 100) if mem_limit else 0
            return self._memory_result(pct, mem_used, mem_limit)
        return self.make_check("节点内存", ExitCode.WARNING, message="无法从 rabbitmqctl 解析内存信息")

    def _check_disk_cli(self, raw: str) -> CheckResult:
        match = re.search(r"disk_free\s*,\s*(\d+)", raw)
        match_limit = re.search(r"disk_free_limit\s*,\s*(\d+)", raw)
        if match:
            disk_free = int(match.group(1))
            disk_limit = int(match_limit.group(1)) if match_limit else 0
            # 简单用百分比阈值判断
            warn_pct = self.config.get("disk_free_warn_percent", 20.0)
            # 无总量信息时仅按绝对值告警
            return self._disk_result(disk_free, disk_limit, None)
        return self.make_check("磁盘空间", ExitCode.WARNING, message="无法从 rabbitmqctl 解析磁盘信息")

    # ── 公共判断逻辑 ─────────────────────────────────────────

    def _memory_result(self, pct: float, mem_used: int, mem_limit: int) -> CheckResult:
        warn = self.config.get("memory_usage_warn", 80.0)
        crit = self.config.get("memory_usage_critical", 95.0)
        if pct >= crit:
            status = ExitCode.CRITICAL
        elif pct >= warn:
            status = ExitCode.WARNING
        else:
            status = ExitCode.NORMAL
        return self.make_check(
            "节点内存", status,
            value=f"{pct:.1f}%",
            threshold=f"warn={warn}%,crit={crit}%",
            message=f"内存使用 {pct:.1f}% ({mem_used / (1024**3):.2f}/{mem_limit / (1024**3):.2f} GB)",
            mem_used_bytes=mem_used, mem_limit_bytes=mem_limit,
        )

    def _disk_result(self, disk_free: int, disk_limit: int, pct: float | None) -> CheckResult:
        warn_pct = self.config.get("disk_free_warn_percent", 20.0)
        free_gb = disk_free / (1024 ** 3)
        if pct is not None:
            status = ExitCode.WARNING if pct < warn_pct else ExitCode.NORMAL
            return self.make_check(
                "磁盘空间", status,
                value=f"剩余 {free_gb:.1f} GB ({pct:.1f}%)",
                threshold=f"剩余 < {warn_pct}% 告警",
                message=f"磁盘剩余 {free_gb:.1f} GB, 低于 {warn_pct}% 阈值" if status != ExitCode.NORMAL else f"磁盘剩余 {free_gb:.1f} GB",
            )
        # 无总量信息，仅判断是否低于限制
        status = ExitCode.WARNING if disk_free <= disk_limit else ExitCode.NORMAL
        return self.make_check(
            "磁盘空间", status,
            value=f"剩余 {free_gb:.1f} GB",
            message=f"磁盘剩余 {free_gb:.1f} GB, 低于最低限制" if status != ExitCode.NORMAL else f"磁盘剩余 {free_gb:.1f} GB",
        )

    # ── 报告 ─────────────────────────────────────────────────

    def _report(self, checks: List[CheckResult], summary: str, metadata: dict) -> InspectionReport:
        return InspectionReport(
            component=self.component_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=self.overall_status(checks),
            checks=checks,
            summary=summary,
            metadata=metadata,
        )

    def _build_summary(self, checks: List[CheckResult]) -> str:
        crits = sum(1 for c in checks if c.status == ExitCode.CRITICAL)
        warns = sum(1 for c in checks if c.status == ExitCode.WARNING)
        if crits:
            return f"发现 {crits} 项严重问题, {warns} 项告警"
        if warns:
            return f"发现 {warns} 项告警"
        return "所有检查项正常"


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config_manager import ConfigManager

    cfg = ConfigManager()
    cfg.load()
    checker = RabbitMQChecker(cfg.get_component_config("rabbitmq"))
    sys.exit(checker.run())

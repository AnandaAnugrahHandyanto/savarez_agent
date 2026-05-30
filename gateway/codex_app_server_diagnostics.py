"""Diagnostics and guarded cleanup for Hermes-owned Codex app-server processes."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

WARN_CODEX_APP_SERVER_COUNT = 10
CRITICAL_CODEX_APP_SERVER_COUNT = 20
HERMES_GATEWAY_SERVICE = "hermes-gateway.service"

_HERMES_CODEX_BIN = "/home/jenny/.hermes/node/bin/codex"
_HERMES_CODEX_NPM_PREFIX = (
    "/home/jenny/.hermes/node/lib/node_modules/@openai/codex/"
)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int
    cmdline: tuple[str, ...]
    rss_kb: int = 0

    @property
    def command(self) -> str:
        return " ".join(self.cmdline)


@dataclass(frozen=True)
class SystemdGatewayStatus:
    main_pid: int | None = None
    control_group: str | None = None
    memory_current: str | None = None
    memory_peak: str | None = None
    tasks_current: str | None = None


@dataclass(frozen=True)
class CodexProcessReport:
    gateway_pid: int | None
    gateway_cgroup_path: str | None
    systemd: SystemdGatewayStatus | None
    direct_children: tuple[ProcessInfo, ...]
    codex_processes: tuple[ProcessInfo, ...]
    current_gateway_codex: tuple[ProcessInfo, ...]
    stale_codex: tuple[ProcessInfo, ...]
    threshold_level: str
    threshold_message: str | None
    top_rss: tuple[ProcessInfo, ...]


def is_hermes_codex_app_server_command(cmdline: Sequence[str]) -> bool:
    """Return True only for the exact Hermes Codex app-server command family."""
    if len(cmdline) < 2 or cmdline[1] != "app-server":
        return False
    exe = cmdline[0]
    if exe == _HERMES_CODEX_BIN:
        return True
    return exe.startswith(_HERMES_CODEX_NPM_PREFIX) and exe.endswith("/bin/codex")


def threshold_status(
    count: int,
    *,
    warn_threshold: int = WARN_CODEX_APP_SERVER_COUNT,
    critical_threshold: int = CRITICAL_CODEX_APP_SERVER_COUNT,
) -> tuple[str, str | None]:
    if count > critical_threshold:
        return (
            "critical",
            f"CRITICAL: Hermes Codex app-server count {count} exceeds {critical_threshold}",
        )
    if count > warn_threshold:
        return (
            "warning",
            f"WARNING: Hermes Codex app-server count {count} exceeds {warn_threshold}",
        )
    return "ok", None


def descendants_of(processes: Iterable[ProcessInfo], root_pid: int | None) -> set[int]:
    if root_pid is None:
        return set()
    by_parent: dict[int, list[int]] = {}
    for proc in processes:
        by_parent.setdefault(proc.ppid, []).append(proc.pid)
    descendants: set[int] = set()
    stack = list(by_parent.get(root_pid, []))
    while stack:
        pid = stack.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        stack.extend(by_parent.get(pid, []))
    return descendants


def build_report(
    processes: Sequence[ProcessInfo],
    *,
    gateway_pid: int | None,
    systemd_status: SystemdGatewayStatus | None = None,
    warn_threshold: int = WARN_CODEX_APP_SERVER_COUNT,
    critical_threshold: int = CRITICAL_CODEX_APP_SERVER_COUNT,
) -> CodexProcessReport:
    descendants = descendants_of(processes, gateway_pid)
    direct_children = tuple(
        sorted(
            (proc for proc in processes if gateway_pid is not None and proc.ppid == gateway_pid),
            key=lambda proc: proc.pid,
        )
    )
    codex_processes = tuple(
        sorted(
            (proc for proc in processes if is_hermes_codex_app_server_command(proc.cmdline)),
            key=lambda proc: proc.pid,
        )
    )
    current_gateway_codex = tuple(
        proc for proc in codex_processes if proc.pid in descendants
    )
    stale_codex = tuple(
        proc for proc in codex_processes if proc.pid not in descendants
    )
    level, message = threshold_status(
        len(codex_processes),
        warn_threshold=warn_threshold,
        critical_threshold=critical_threshold,
    )
    top_rss = tuple(sorted(codex_processes, key=lambda proc: proc.rss_kb, reverse=True)[:10])
    return CodexProcessReport(
        gateway_pid=gateway_pid,
        gateway_cgroup_path=systemd_status.control_group if systemd_status else None,
        systemd=systemd_status,
        direct_children=direct_children,
        codex_processes=codex_processes,
        current_gateway_codex=current_gateway_codex,
        stale_codex=stale_codex,
        threshold_level=level,
        threshold_message=message,
        top_rss=top_rss,
    )


def collect_processes() -> list[ProcessInfo]:
    proc_root = Path("/proc")
    processes: list[ProcessInfo] = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            stat_parts = (entry / "stat").read_text().split()
            ppid = int(stat_parts[3])
            cmd_raw = (entry / "cmdline").read_bytes()
            cmdline = tuple(part.decode("utf-8", "replace") for part in cmd_raw.split(b"\0") if part)
            if not cmdline:
                continue
            rss_kb = 0
            for line in (entry / "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    fields = line.split()
                    if len(fields) >= 2:
                        rss_kb = int(fields[1])
                    break
            processes.append(ProcessInfo(pid=pid, ppid=ppid, cmdline=cmdline, rss_kb=rss_kb))
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, OSError):
            continue
    return processes


def read_systemd_gateway_status(
    *,
    unit: str = HERMES_GATEWAY_SERVICE,
    runner=subprocess.run,
) -> SystemdGatewayStatus | None:
    try:
        result = runner(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=MainPID,ControlGroup,MemoryCurrent,MemoryPeak,TasksCurrent",
                "--value",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.splitlines()
    if len(lines) < 5:
        return None
    main_pid = _parse_pid(lines[0])
    return SystemdGatewayStatus(
        main_pid=main_pid,
        control_group=lines[1].strip() or None,
        memory_current=lines[2].strip() or None,
        memory_peak=lines[3].strip() or None,
        tasks_current=lines[4].strip() or None,
    )


def _parse_pid(value: str) -> int | None:
    try:
        pid = int(value.strip())
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def diagnose(
    *,
    gateway_pid: int | None = None,
    include_systemd: bool = True,
    warn_threshold: int = WARN_CODEX_APP_SERVER_COUNT,
    critical_threshold: int = CRITICAL_CODEX_APP_SERVER_COUNT,
) -> CodexProcessReport:
    systemd_status = read_systemd_gateway_status() if include_systemd else None
    resolved_gateway_pid = gateway_pid
    if resolved_gateway_pid is None and systemd_status is not None:
        resolved_gateway_pid = systemd_status.main_pid
    return build_report(
        collect_processes(),
        gateway_pid=resolved_gateway_pid,
        systemd_status=systemd_status,
        warn_threshold=warn_threshold,
        critical_threshold=critical_threshold,
    )


def log_startup_codex_process_warning(gateway_pid: int | None = None) -> None:
    report = diagnose(gateway_pid=gateway_pid or os.getpid())
    if report.threshold_message:
        log_fn = logger.critical if report.threshold_level == "critical" else logger.warning
        log_fn("%s", report.threshold_message)
    if report.stale_codex:
        logger.warning(
            "Detected %d stale Hermes Codex app-server process(es) outside current gateway tree: %s",
            len(report.stale_codex),
            ", ".join(str(proc.pid) for proc in report.stale_codex),
        )


def kill_stale_codex(
    report: CodexProcessReport,
    *,
    execute: bool = False,
    killer=os.kill,
) -> list[int]:
    targeted: list[int] = []
    for proc in report.stale_codex:
        logger.warning(
            "%s stale Hermes Codex app-server PID %d: %s",
            "Killing" if execute else "Would kill",
            proc.pid,
            proc.command,
        )
        targeted.append(proc.pid)
        if execute:
            killer(proc.pid, signal.SIGTERM)
    return targeted


def report_to_dict(report: CodexProcessReport) -> dict:
    return {
        "gateway_pid": report.gateway_pid,
        "gateway_cgroup_path": report.gateway_cgroup_path,
        "systemd": None if report.systemd is None else {
            "main_pid": report.systemd.main_pid,
            "control_group": report.systemd.control_group,
            "memory_current": report.systemd.memory_current,
            "memory_peak": report.systemd.memory_peak,
            "tasks_current": report.systemd.tasks_current,
        },
        "direct_children": [_process_to_dict(proc) for proc in report.direct_children],
        "codex_app_server_count": len(report.codex_processes),
        "current_gateway_codex": [_process_to_dict(proc) for proc in report.current_gateway_codex],
        "stale_codex": [_process_to_dict(proc) for proc in report.stale_codex],
        "threshold_level": report.threshold_level,
        "threshold_message": report.threshold_message,
        "top_codex_app_server_by_rss": [_process_to_dict(proc) for proc in report.top_rss],
    }


def _process_to_dict(proc: ProcessInfo) -> dict:
    return {
        "pid": proc.pid,
        "ppid": proc.ppid,
        "rss_kb": proc.rss_kb,
        "cmdline": list(proc.cmdline),
        "command": proc.command,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report Hermes Codex app-server process health."
    )
    parser.add_argument("--gateway-pid", type=int, default=None)
    parser.add_argument("--warn-threshold", type=int, default=WARN_CODEX_APP_SERVER_COUNT)
    parser.add_argument("--critical-threshold", type=int, default=CRITICAL_CODEX_APP_SERVER_COUNT)
    parser.add_argument("--no-systemd", action="store_true")
    parser.add_argument(
        "--kill-stale-codex",
        action="store_true",
        help="Send SIGTERM to stale Hermes Codex app-server processes. Default is report-only.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    report = diagnose(
        gateway_pid=args.gateway_pid,
        include_systemd=not args.no_systemd,
        warn_threshold=args.warn_threshold,
        critical_threshold=args.critical_threshold,
    )
    print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
    kill_stale_codex(report, execute=args.kill_stale_codex)
    return 2 if report.threshold_level == "critical" else 1 if report.threshold_level == "warning" else 0


if __name__ == "__main__":
    raise SystemExit(main())

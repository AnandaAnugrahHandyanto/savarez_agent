"""Minimal terminal monitor dashboard for Hermes runtime state."""

from __future__ import annotations

import json
import time
from typing import Any

from gateway.status import is_gateway_running, read_runtime_status
from hermes_cli.config import get_hermes_home


def _load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_monitor_snapshot() -> dict[str, Any]:
    home = get_hermes_home()
    runtime = read_runtime_status() or {}
    sessions_data = _load_json(home / "sessions" / "sessions.json") or {}
    jobs_payload = _load_json(home / "cron" / "jobs.json") or {}
    jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []

    enabled_jobs = [job for job in jobs if job.get("enabled", True)]
    failing_jobs = [job for job in enabled_jobs if (job.get("last_status") or "").lower() not in ("", "ok", "success")]

    errors: list[dict[str, str]] = []
    for platform, detail in (runtime.get("platforms") or {}).items():
        if not isinstance(detail, dict):
            continue
        state = str(detail.get("state") or "").lower()
        message = detail.get("error_message") or detail.get("error_code")
        if state in {"error", "failed", "degraded"} or message:
            errors.append({
                "source": f"platform:{platform}",
                "message": str(message or state or "unknown error"),
            })
    for job in failing_jobs:
        errors.append({
            "source": f"cron:{job.get('id', 'unknown')}",
            "message": str(job.get("last_error") or job.get("last_status") or "failed"),
        })

    return {
        "gateway": {
            "running": bool(is_gateway_running()),
            "state": runtime.get("gateway_state") or "unknown",
            "active_agents": int(runtime.get("active_agents") or 0),
            "updated_at": runtime.get("updated_at") or "(unknown)",
        },
        "sessions": {
            "active": len(sessions_data) if isinstance(sessions_data, dict) else 0,
        },
        "cron": {
            "total": len(jobs),
            "enabled": len(enabled_jobs),
            "failing": len(failing_jobs),
        },
        "errors": errors[:8],
    }


def render_monitor_text(snapshot: dict[str, Any]) -> str:
    gateway = snapshot.get("gateway", {})
    sessions = snapshot.get("sessions", {})
    cron = snapshot.get("cron", {})
    errors = snapshot.get("errors", [])

    lines = [
        "Hermes Monitor",
        "",
        "Gateway",
        f"  running: {gateway.get('running')}",
        f"  state: {gateway.get('state')}",
        f"  active_agents: {gateway.get('active_agents')}",
        f"  updated_at: {gateway.get('updated_at')}",
        "",
        "Sessions",
        f"  active: {sessions.get('active', 0)}",
        "",
        "Cron",
        f"  total: {cron.get('total', 0)}",
        f"  enabled: {cron.get('enabled', 0)}",
        f"  failing: {cron.get('failing', 0)}",
        "",
        "Error Summary",
    ]
    if errors:
        for item in errors:
            lines.append(f"  - {item.get('source')}: {item.get('message')}")
    else:
        lines.append("  - none")
    return "\n".join(lines)


def monitor_command(args) -> None:
    once = bool(getattr(args, "once", False))
    iterations = max(1, int(getattr(args, "iterations", 1) or 1))
    interval = float(getattr(args, "interval", 2.0) or 2.0)

    count = 1 if once else iterations
    for index in range(count):
        if index:
            print("\n" + ("-" * 60) + "\n")
        print(render_monitor_text(build_monitor_snapshot()))
        if index < count - 1:
            time.sleep(interval)

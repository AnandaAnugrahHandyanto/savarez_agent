"""CLI helpers for managing the autonomous heartbeat."""

from __future__ import annotations

from hermes_cli.colors import Colors, color
from cron.heartbeat import (
    disable_heartbeat,
    enable_heartbeat,
    heartbeat_status,
    resume_heartbeat,
    run_heartbeat_now,
)


def heartbeat_command(args):
    subcmd = getattr(args, "heartbeat_command", None) or "status"

    if subcmd == "enable":
        job = enable_heartbeat(
            schedule=getattr(args, "schedule", None) or "every 2h",
            mission=getattr(args, "mission", None),
            deliver=getattr(args, "deliver", None),
        )
        print(color("Heartbeat enabled", Colors.GREEN))
        print(f"  Job: {job['name']} ({job['id']})")
        print(f"  Schedule: {job['schedule_display']}")
        print(f"  Next run: {job.get('next_run_at')}")
        return 0

    if subcmd == "disable":
        job = disable_heartbeat()
        if not job:
            print(color("Heartbeat is not configured.", Colors.YELLOW))
            return 1
        print(color("Heartbeat disabled", Colors.GREEN))
        print(f"  Job: {job['name']} ({job['id']})")
        return 0

    if subcmd == "resume":
        job = resume_heartbeat()
        if not job:
            print(color("Heartbeat is not configured.", Colors.YELLOW))
            return 1
        print(color("Heartbeat resumed", Colors.GREEN))
        print(f"  Next run: {job.get('next_run_at')}")
        return 0

    if subcmd == "run":
        job = run_heartbeat_now()
        if not job:
            print(color("Heartbeat is not configured.", Colors.YELLOW))
            return 1
        print(color("Heartbeat triggered", Colors.GREEN))
        print("  It will run on the next scheduler tick.")
        return 0

    status = heartbeat_status()
    print(color("Heartbeat status", Colors.CYAN))
    print(f"  Enabled: {status['enabled']}")
    print(f"  State: {status['state']}")
    print(f"  Job ID: {status['job_id']}")
    print(f"  Schedule: {status['schedule']}")
    print(f"  Next run: {status['next_run_at']}")
    if status.get("deliver"):
        print(f"  Deliver: {status['deliver']}")
    print(f"  Memory: {status.get('include_memory', False)}")
    return 0

"""
Cron job scheduling system for Hermes Agent.

This module provides scheduled task execution, allowing the agent to:
- Run automated tasks on schedules (cron expressions, intervals, one-shot)
- Self-schedule reminders and follow-up tasks
- Execute tasks in isolated sessions (no prior context)

Cron jobs are executed automatically by the gateway daemon:
    hermes gateway install    # Install as a user service
    sudo hermes gateway install --system  # Linux servers: boot-time system service
    hermes gateway            # Or run in foreground

The gateway ticks the scheduler every 60 seconds. A file lock prevents
duplicate execution if multiple processes overlap.
"""

from cron.jobs import (
    create_job,
    get_job,
    list_jobs,
    remove_job,
    update_job,
    pause_job,
    resume_job,
    trigger_job,
    JOBS_FILE,
)
from cron.scheduler import tick
from cron.heartbeat import (
    DEFAULT_HEARTBEAT_NAME,
    DEFAULT_HEARTBEAT_SCHEDULE,
    build_heartbeat_prompt,
    disable_heartbeat,
    enable_heartbeat,
    get_heartbeat_job,
    heartbeat_status,
    resume_heartbeat,
    run_heartbeat_now,
)

__all__ = [
    "create_job",
    "get_job", 
    "list_jobs",
    "remove_job",
    "update_job",
    "pause_job",
    "resume_job",
    "trigger_job",
    "tick",
    "JOBS_FILE",
    "DEFAULT_HEARTBEAT_NAME",
    "DEFAULT_HEARTBEAT_SCHEDULE",
    "build_heartbeat_prompt",
    "enable_heartbeat",
    "disable_heartbeat",
    "resume_heartbeat",
    "run_heartbeat_now",
    "get_heartbeat_job",
    "heartbeat_status",
]

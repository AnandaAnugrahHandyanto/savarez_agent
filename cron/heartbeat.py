"""First-class autonomous heartbeat support built on top of cron jobs."""

from __future__ import annotations

from typing import Any, Optional

from cron.jobs import create_job, list_jobs, pause_job, resume_job, update_job

DEFAULT_HEARTBEAT_NAME = "Hermes Heartbeat"
DEFAULT_HEARTBEAT_SCHEDULE = "every 2h"


def build_heartbeat_prompt(mission: Optional[str] = None) -> str:
    mission_text = (mission or "Make yourself as useful as possible without waiting for user input.").strip()
    return (
        "You are running a periodic autonomous heartbeat on behalf of the user. "
        "Do not wait passively for input. Use this wake-up cycle to make concrete progress.\n\n"
        "Primary mission:\n"
        f"- {mission_text}\n\n"
        "Behavior requirements:\n"
        "1. Start by using session_search() to inspect recent sessions and identify unfinished threads, promises,"
        " follow-ups, or work that can be advanced autonomously.\n"
        "2. Prefer quiet, concrete progress: research, drafting, implementation, verification, maintenance,"
        " cleanup, or preparing useful artifacts for the user.\n"
        "3. If a codebase or local files are relevant, inspect them and do real work with tools instead of only"
        " writing suggestions.\n"
        "4. Be selective about messaging. If you can make progress without interrupting the user, do that."
        " If a concise blocking question would unlock meaningful progress, ask it briefly in your final response.\n"
        "5. If there is genuinely nothing useful to do right now, respond with exactly [SILENT].\n"
        "6. When you do report back, summarize only the concrete progress or the specific blocker.\n"
    )


def get_heartbeat_job() -> Optional[dict[str, Any]]:
    jobs = list_jobs(include_disabled=True)
    heartbeat_jobs = [job for job in jobs if job.get("kind") == "heartbeat"]
    if not heartbeat_jobs:
        return None
    heartbeat_jobs.sort(key=lambda j: j.get("created_at") or "")
    return heartbeat_jobs[0]


def enable_heartbeat(
    *,
    schedule: str = DEFAULT_HEARTBEAT_SCHEDULE,
    mission: Optional[str] = None,
    deliver: Optional[str] = None,
    name: str = DEFAULT_HEARTBEAT_NAME,
) -> dict[str, Any]:
    prompt = build_heartbeat_prompt(mission)
    existing = get_heartbeat_job()
    if existing:
        updates = {
            "name": name,
            "prompt": prompt,
            "schedule_display": schedule,
            "schedule": existing["schedule"],
            "kind": "heartbeat",
            "include_memory": True,
            "enabled": True,
            "state": "scheduled",
            "paused_at": None,
            "paused_reason": None,
        }
        from cron.jobs import parse_schedule, compute_next_run

        parsed = parse_schedule(schedule)
        updates["schedule"] = parsed
        updates["schedule_display"] = parsed.get("display", schedule)
        updates["next_run_at"] = compute_next_run(parsed)
        if deliver is not None:
            updates["deliver"] = deliver
        updated = update_job(existing["id"], updates)
        if updated is None:
            raise RuntimeError("Failed to update existing heartbeat job")
        return updated

    created = create_job(
        prompt=prompt,
        schedule=schedule,
        name=name,
        deliver=deliver,
        kind="heartbeat",
        include_memory=True,
    )
    updated = update_job(created["id"], {"schedule_display": schedule})
    if updated is None:
        raise RuntimeError("Failed to finalize heartbeat job")
    return updated


def disable_heartbeat() -> Optional[dict[str, Any]]:
    existing = get_heartbeat_job()
    if not existing:
        return None
    return pause_job(existing["id"], reason="heartbeat disabled")


def heartbeat_status() -> dict[str, Any]:
    job = get_heartbeat_job()
    if not job:
        return {
            "enabled": False,
            "job_id": None,
            "name": DEFAULT_HEARTBEAT_NAME,
            "schedule": None,
            "next_run_at": None,
            "state": "absent",
        }
    return {
        "enabled": bool(job.get("enabled", True)) and job.get("state") != "paused",
        "job_id": job.get("id"),
        "name": job.get("name") or DEFAULT_HEARTBEAT_NAME,
        "schedule": job.get("schedule_display"),
        "next_run_at": job.get("next_run_at"),
        "state": job.get("state", "scheduled" if job.get("enabled", True) else "paused"),
        "deliver": job.get("deliver"),
        "include_memory": bool(job.get("include_memory")),
    }


def run_heartbeat_now() -> Optional[dict[str, Any]]:
    existing = get_heartbeat_job()
    if not existing:
        return None
    from cron.jobs import trigger_job

    return trigger_job(existing["id"])


def resume_heartbeat() -> Optional[dict[str, Any]]:
    existing = get_heartbeat_job()
    if not existing:
        return None
    return resume_job(existing["id"])

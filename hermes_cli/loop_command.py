"""Handle /loop slash command — persistent scheduled agent loops.

Creates cron jobs with loop=True that self-evaluate via judge_goal and
auto-pause after consecutive no-progress detections.
"""

import json
import logging
import re
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def handle_loop_command(
    text: str,
    cronjob_tool: Optional[Callable] = None,
    output_fn: Optional[Callable] = None,
) -> str:
    """Handle /loop slash command.

    Args:
        text: The raw command text after '/loop'.
        cronjob_tool: Optional callable for cron job operations.
            When None, imports cron.jobs directly.
        output_fn: Optional output function for CLI display (unused in
            gateway mode; CLI callers use _cprint directly).

    Returns:
        JSON string for tool integration, or human-readable status.
    """
    args = (text or "").strip()

    # Subcommand routing
    if not args:
        return _usage()

    lower = args.lower()

    if lower == "status":
        return _handle_status()

    # pause <id>
    m = re.match(r"^pause\s+(\S+)", args, re.IGNORECASE)
    if m:
        return _handle_pause_resume(m.group(1), "pause")

    # resume <id>
    m = re.match(r"^resume\s+(\S+)", args, re.IGNORECASE)
    if m:
        return _handle_pause_resume(m.group(1), "resume")

    # stop <id> (alias for remove)
    m = re.match(r"^stop\s+(\S+)", args, re.IGNORECASE)
    if m:
        return _handle_stop(m.group(1))

    # Parse as: <interval> <prompt> [--skills s1,s2] [--verify 'command']
    return _handle_create(args)


def _usage() -> str:
    return json.dumps({
        "success": False,
        "error": (
            "Usage: /loop <interval> <prompt> [--skills s1,s2] [--verify 'command']\n"
            "       /loop status\n"
            "       /loop pause <id>\n"
            "       /loop resume <id>\n"
            "       /loop stop <id>\n"
            "\n"
            "Examples:\n"
            "  /loop every 30m check the deployment status\n"
            "  /loop every 2h monitor disk usage --verify 'df -h / | awk \"{print $5}\"'\n"
            "  /loop status\n"
            "  /loop pause abc123def456"
        ),
    })


def _parse_create_args(text: str) -> dict:
    """Parse /loop create arguments.

    Expected format: <interval> <prompt> [--skills s1,s2] [--verify 'command']

    Returns dict with keys: schedule, prompt, skills, verify, error.
    """
    result = {"schedule": "", "prompt": "", "skills": None, "verify": None, "error": None}

    # Extract --skills and --verify flags first
    skills_list = None
    verify_cmd = None

    # --verify 'command' or --verify "command"
    verify_match = re.search(r"""--verify\s+(['"])(.*?)\1""", text, re.DOTALL)
    if verify_match:
        verify_cmd = verify_match.group(2).strip()
        text = text[:verify_match.start()] + text[verify_match.end():]
    else:
        # --verify command (no quotes, rest of line)
        verify_match = re.search(r"--verify\s+(\S+.*)", text)
        if verify_match:
            verify_cmd = verify_match.group(1).strip()
            text = text[:verify_match.start()]

    # --skills s1,s2 or --skills s1,s2,s3
    skills_match = re.search(r"--skills?\s+(\S+)", text)
    if skills_match:
        raw_skills = skills_match.group(1)
        skills_list = [s.strip() for s in raw_skills.split(",") if s.strip()]
        text = text[:skills_match.start()] + text[skills_match.end():]

    text = text.strip()

    # First token is the schedule/interval
    parts = text.split(None, 1)
    if not parts:
        result["error"] = "Missing interval and prompt"
        return result

    schedule = parts[0]
    # Handle "every X" as the first two tokens
    if schedule.lower() == "every" and len(parts) > 1:
        rest_parts = parts[1].split(None, 1)
        schedule = f"every {rest_parts[0]}"
        prompt = rest_parts[1] if len(rest_parts) > 1 else ""
    else:
        prompt = parts[1] if len(parts) > 1 else ""

    if not prompt.strip():
        result["error"] = "Missing prompt text"
        return result

    result["schedule"] = schedule
    result["prompt"] = prompt.strip()
    result["skills"] = skills_list
    result["verify"] = verify_cmd
    return result


def _handle_create(text: str) -> str:
    """Create a new loop cron job."""
    parsed = _parse_create_args(text)
    if parsed.get("error"):
        return json.dumps({"success": False, "error": parsed["error"]})

    try:
        from cron.jobs import create_job
        job = create_job(
            prompt=parsed["prompt"],
            schedule=parsed["schedule"],
            deliver="origin",
            loop=True,
            loop_verify=parsed.get("verify"),
            skills=parsed.get("skills"),
        )
        return json.dumps({
            "success": True,
            "action": "created",
            "job_id": job["id"],
            "schedule": job.get("schedule_display", parsed["schedule"]),
            "prompt": parsed["prompt"][:100],
            "next_run_at": job.get("next_run_at"),
            "skills": parsed.get("skills"),
            "verify": parsed.get("verify"),
            "message": (
                f"🔄 Loop created: {job['id']}\n"
                f"   Schedule: {job.get('schedule_display', parsed['schedule'])}\n"
                f"   Prompt: {parsed['prompt'][:80]}{'...' if len(parsed['prompt']) > 80 else ''}\n"
                f"   Next run: {job.get('next_run_at', 'unknown')}\n"
                f"   Auto-pause: after 3 consecutive no-progress detections"
            ),
        })
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _handle_status() -> str:
    """List all loop jobs."""
    try:
        from cron.jobs import list_jobs
        all_jobs = list_jobs(include_disabled=True)
        loop_jobs = [j for j in all_jobs if j.get("loop")]

        if not loop_jobs:
            return json.dumps({
                "success": True,
                "jobs": [],
                "message": "No loop jobs configured.",
            })

        lines = ["Active loop jobs:"]
        for j in loop_jobs:
            state = j.get("state", "unknown")
            name = j.get("name", j.get("id", "?"))
            schedule = j.get("schedule_display", "?")
            count = j.get("loop_no_progress_count", 0)
            threshold = j.get("loop_no_progress_threshold", 3)
            lines.append(
                f"  {'⏸' if state == 'paused' else '▶'} {j['id']} "
                f"({state}) [{schedule}] {name[:40]}"
            )
            lines.append(f"    no-progress: {count}/{threshold}")

        return json.dumps({
            "success": True,
            "jobs": [
                {
                    "id": j["id"],
                    "state": j.get("state", "unknown"),
                    "schedule": j.get("schedule_display", "?"),
                    "name": j.get("name", ""),
                    "no_progress_count": j.get("loop_no_progress_count", 0),
                    "threshold": j.get("loop_no_progress_threshold", 3),
                }
                for j in loop_jobs
            ],
            "message": "\n".join(lines),
        })
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _handle_pause_resume(job_ref: str, action: str) -> str:
    """Pause or resume a loop job."""
    try:
        from cron.jobs import pause_job, resume_job
        if action == "pause":
            job = pause_job(job_ref, reason="user-paused")
        else:
            job = resume_job(job_ref)

        if not job:
            return json.dumps({"success": False, "error": f"Job not found: {job_ref}"})

        return json.dumps({
            "success": True,
            "action": action + "d",
            "job_id": job["id"],
            "state": job.get("state"),
            "message": f"{'⏸' if action == 'pause' else '▶'} Loop {action}d: {job['id']}",
        })
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _handle_stop(job_ref: str) -> str:
    """Stop (remove) a loop job."""
    try:
        from cron.jobs import remove_job, resolve_job_ref
        resolved = resolve_job_ref(job_ref)
        if not resolved:
            return json.dumps({"success": False, "error": f"Job not found: {job_ref}"})

        removed = remove_job(resolved["id"])
        if removed:
            return json.dumps({
                "success": True,
                "action": "removed",
                "job_id": resolved["id"],
                "message": f"🗑 Loop stopped and removed: {resolved['id']}",
            })
        return json.dumps({"success": False, "error": f"Failed to remove job: {job_ref}"})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

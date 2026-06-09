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
    origin: Optional[dict] = None,
) -> str:
    """Handle /loop slash command.

    Args:
        text: The raw command text after '/loop'.
        cronjob_tool: Optional callable for cron job operations.
            When None, imports cron.jobs directly.
        output_fn: Optional output function for CLI display (unused in
            gateway mode; CLI callers use _cprint directly).
        origin: Optional origin dict with platform/chat_id/thread_id
            for delivery routing. Passed through to create_job.

    Returns:
        JSON string for tool integration, or human-readable status.
    """
    args = (text or "").strip()

    # Subcommand routing
    if not args:
        return _usage()

    lower = args.lower()

    # Aliases for status
    if lower in ("status", "list"):
        return _handle_status()

    # Help alias
    if lower == "help":
        return _usage()

    # pause <id> — catch bare "pause" without ID
    m = re.match(r"^pause\s+(\S+)", args, re.IGNORECASE)
    if m:
        return _handle_pause_resume(m.group(1), "pause")
    if lower == "pause":
        return json.dumps({"success": False, "error": "Usage: /loop pause <job_id>\n       (partial IDs work — you can use the first few characters)"})

    # resume <id> — catch bare "resume" without ID
    m = re.match(r"^resume\s+(\S+)", args, re.IGNORECASE)
    if m:
        return _handle_pause_resume(m.group(1), "resume")
    if lower == "resume":
        return json.dumps({"success": False, "error": "Usage: /loop resume <job_id>\n       (partial IDs work — you can use the first few characters)"})

    # stop/remove <id> — catch bare subcommands without ID
    m = re.match(r"^(?:stop|remove)\s+(\S+)", args, re.IGNORECASE)
    if m:
        return _handle_stop(m.group(1))
    if lower in ("stop", "remove"):
        return json.dumps({"success": False, "error": "Usage: /loop stop <job_id>\n       (partial IDs work — you can use the first few characters)"})

    # Parse as: <interval> <prompt> [--skills s1,s2] [--verify 'command'] [--name label]
    return _handle_create(args, origin=origin)


def _usage() -> str:
    return json.dumps({
        "success": True,
        "message": (
            "Usage: /loop <interval> <prompt> [--skills s1,s2] [--verify 'cmd'] [--name label]\n"
            "       /loop status\n"
            "       /loop pause <id>\n"
            "       /loop resume <id>\n"
            "       /loop stop <id>\n"
            "\n"
            "Partial IDs work — you can use the first few characters of a job ID.\n"
            "\n"
            "Examples:\n"
            "  /loop every 30m check the deployment status\n"
            "  /loop 2h monitor disk usage --verify 'df -h /' --name disk-watch\n"
            "  /loop status\n"
            "  /loop pause abc123"
        ),
    })


def _parse_create_args(text: str) -> dict:
    """Parse /loop create arguments.

    Expected format: <interval> <prompt> [--skills s1,s2] [--verify 'command'] [--name label]

    Returns dict with keys: schedule, prompt, skills, verify, name, error.
    """
    result = {"schedule": "", "prompt": "", "skills": None, "verify": None, "name": None, "error": None}

    # Extract flags in order: --name first (single token, won't eat others),
    # then --skills (single token), then --verify (greedy, captures rest).
    # This ordering prevents --verify from eating --skills or --name.

    # --name label
    name_match = re.search(r"--name\s+(\S+)", text)
    if name_match:
        result["name"] = name_match.group(1).strip()
        text = text[:name_match.start()] + text[name_match.end():]

    # --skills s1,s2 or --skills s1,s2,s3
    skills_match = re.search(r"--skills?\s+(\S+)", text)
    if skills_match:
        raw_skills = skills_match.group(1)
        result["skills"] = [s.strip() for s in raw_skills.split(",") if s.strip()]
        text = text[:skills_match.start()] + text[skills_match.end():]

    # --verify 'command' or --verify "command" (quoted — captures inside quotes)
    verify_match = re.search(r"""--verify\s+(['"])(.*?)\1""", text, re.DOTALL)
    if verify_match:
        result["verify"] = verify_match.group(2).strip()
        text = text[:verify_match.start()] + text[verify_match.end():]
    else:
        # --verify command (no quotes, rest of line — safe now because
        # --skills and --name are already extracted)
        verify_match = re.search(r"--verify\s+(\S+.*)", text)
        if verify_match:
            result["verify"] = verify_match.group(1).strip()
            text = text[:verify_match.start()]

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
    return result


def _handle_create(text: str, origin: Optional[dict] = None) -> str:
    """Create a new loop cron job."""
    parsed = _parse_create_args(text)
    if parsed.get("error"):
        return json.dumps({"success": False, "error": parsed["error"]})

    try:
        from cron.jobs import create_job
        job = create_job(
            prompt=parsed["prompt"],
            schedule=parsed["schedule"],
            name=parsed.get("name"),
            deliver="origin",
            origin=origin,
            loop=True,
            loop_verify=parsed.get("verify"),
            skills=parsed.get("skills"),
        )
        job_name = job.get("name", job["id"])
        verify_line = f"   Verify: {parsed['verify']}\n" if parsed.get("verify") else ""
        return json.dumps({
            "success": True,
            "action": "created",
            "job_id": job["id"],
            "schedule": job.get("schedule_display", parsed["schedule"]),
            "prompt": parsed["prompt"][:100],
            "next_run_at": job.get("next_run_at"),
            "skills": parsed.get("skills"),
            "verify": parsed.get("verify"),
            "name": parsed.get("name"),
            "message": (
                f"🔄 Loop created: {job['id']}\n"
                f"   Name: {job_name}\n"
                f"   Schedule: {job.get('schedule_display', parsed['schedule'])}\n"
                f"   Prompt: {parsed['prompt'][:80]}{'...' if len(parsed['prompt']) > 80 else ''}\n"
                f"{verify_line}"
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

        lines = ["Loop jobs:"]
        for j in loop_jobs:
            state = j.get("state", "unknown")
            name = j.get("name", j.get("id", "?"))
            schedule = j.get("schedule_display", "?")
            count = j.get("loop_no_progress_count", 0)
            threshold = j.get("loop_no_progress_threshold", 3)
            verify = j.get("loop_verify")
            verify_err = j.get("loop_last_verify_error")
            lines.append(
                f"  {'⏸' if state == 'paused' else '▶'} {j['id']} "
                f"({state}) [{schedule}] {name[:40]}"
            )
            lines.append(f"    no-progress: {count}/{threshold}")
            if verify:
                status_icon = "❌" if verify_err else "✓"
                lines.append(f"    verify: {status_icon} {verify[:60]}")

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
                    "verify": j.get("loop_verify"),
                    "verify_error": j.get("loop_last_verify_error"),
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
        from cron.jobs import remove_job
        removed = remove_job(job_ref)
        if removed:
            return json.dumps({
                "success": True,
                "action": "removed",
                "message": f"🗑 Loop stopped and removed: {job_ref}",
            })
        return json.dumps({"success": False, "error": f"Job not found: {job_ref}"})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})

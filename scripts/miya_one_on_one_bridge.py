from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_cli.env_loader import load_hermes_dotenv
from hermes_cli.profiles import get_profile_dir
from people_manager.prep_queue import claim_next_for_miya, mark_failed, mark_sent_by_miya
from people_manager.schedule_store import load_schedule_registry
from people_manager.storage import load_report

load_hermes_dotenv(project_env=None)

DEFAULT_MIYA_PROFILE = "miya"
DEFAULT_PROMPT_MODEL = None
BRIDGE_ACTOR = "miya-bridge"



def _parse_now(value: str | None, timezone_name: str) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed.astimezone(ZoneInfo(timezone_name))
    return datetime.now(ZoneInfo(timezone_name))



def resolve_bridge_delivery_target(event: dict[str, Any], explicit_target: str | None = None) -> str:
    if explicit_target:
        return explicit_target
    delivery_target = str(event.get("delivery_target") or "origin").strip()
    if delivery_target.startswith("telegram:"):
        return delivery_target
    env_target = os.getenv("MIYA_ONE_ON_ONE_DELIVERY_TARGET", "").strip()
    if env_target:
        return env_target
    raise RuntimeError(
        "Miya bridge needs an explicit founder-facing target. "
        "Set MIYA_ONE_ON_ONE_DELIVERY_TARGET or pass --miya-target telegram:<chat_id>."
    )



def build_miya_bridge_prompt(event: dict[str, Any], report: dict[str, Any], *, miya_target: str) -> str:
    event_payload = {
        "type": event.get("type"),
        "profile_slug": event.get("profile_slug"),
        "name": event.get("name"),
        "meeting_at": event.get("meeting_at"),
        "prep_due_at": event.get("prep_due_at"),
        "target_send_by_at": event.get("target_send_by_at"),
        "deadline_at": event.get("deadline_at"),
        "delivery_target": miya_target,
        "report_path": event.get("report_path"),
        "template_style": event.get("template_style"),
        "fallback_allowed": event.get("fallback_allowed"),
        "dedupe_key": event.get("dedupe_key"),
    }
    report_snapshot = {
        "name": report.get("name"),
        "slug": report.get("slug"),
        "role_title": report.get("role_title"),
        "prep_note_preference": report.get("prep_note_preference"),
        "upcoming_one_on_one": report.get("upcoming_one_on_one"),
        "one_on_one_cadence_notes": report.get("one_on_one_cadence_notes"),
        "relationship_note": report.get("relationship_note"),
        "role_charter": report.get("role_charter"),
        "open_loops": report.get("open_loops"),
        "management_strategy": report.get("management_strategy"),
    }
    return (
        "You are Miya handling a deterministic one_on_one_prep_due bridge event.\n"
        "This is an explicit transitional bridge: you are still the founder-facing author.\n"
        "Your job: read the event + profile context, write the prep note in your normal concise founder-facing style, "
        f"and send it to {miya_target} using the send_message tool.\n"
        "Do not ask the founder a question. Do not ask for clarification. Do not mention internal queueing, SLAs, or fallback.\n"
        "If context is sparse, keep it short and honest rather than overreaching.\n"
        "After you successfully send the message, your final response must be exactly:\n"
        f"SENT dedupe_key={event.get('dedupe_key')}\n"
        "If you could not send the message, explain briefly in plain text and do not claim success.\n\n"
        "Bridge event:\n"
        f"{json.dumps(event_payload, indent=2, sort_keys=True, ensure_ascii=False)}\n\n"
        "Report context:\n"
        f"{json.dumps(report_snapshot, indent=2, sort_keys=True, ensure_ascii=False)}\n"
    )



def invoke_miya_chat(prompt: str, *, profile: str, cwd: Path | None = None, model: str | None = DEFAULT_PROMPT_MODEL) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "hermes_cli.main", "chat", "-Q", "-q", prompt]
    if model:
        command.extend(["-m", model])
    env = os.environ.copy()
    env["HERMES_HOME"] = str(_resolve_profile_home(profile))
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd or Path(__file__).resolve().parents[1]),
        env=env,
    )



def _response_indicates_success(result: subprocess.CompletedProcess[str], dedupe_key: str) -> bool:
    if result.returncode != 0:
        return False
    stdout = result.stdout or ""
    return f"SENT dedupe_key={dedupe_key}" in stdout



def _resolve_profile_home(profile: str) -> Path:
    current_home_env = os.getenv("HERMES_HOME", "").strip()
    current_home = Path(current_home_env).expanduser() if current_home_env else None
    if current_home and current_home.name == profile:
        return current_home
    if current_home and current_home.parent.name == "profiles":
        return current_home.parent / profile

    candidates = []
    profiles_root_env = os.getenv("HERMES_PROFILES_ROOT", "").strip()
    if profiles_root_env:
        candidates.append(Path(profiles_root_env).expanduser() / profile)
    candidates.append(Path.home() / ".hermes" / "profiles" / profile)
    if current_home:
        for parent in current_home.parents:
            candidates.append(parent / ".hermes" / "profiles" / profile)
    candidates.append(get_profile_dir(profile))

    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else get_profile_dir(profile)



def _load_profile_env(profile: str) -> None:
    profile_dir = _resolve_profile_home(profile)
    load_hermes_dotenv(hermes_home=profile_dir, project_env=None)



def run_once(*, now: datetime, profile: str, miya_target: str | None = None) -> int:
    _load_profile_env(profile)
    event = claim_next_for_miya(now=now, actor=BRIDGE_ACTOR)
    if not event:
        print("No queued occurrences for Miya bridge")
        return 0

    report = load_report(event["profile_slug"])
    if not report:
        mark_failed(
            event["dedupe_key"],
            failed_at=now,
            actor=BRIDGE_ACTOR,
            note="Missing report while building Miya bridge prompt.",
        )
        print(f"Missing report for {event['profile_slug']}", file=sys.stderr)
        return 1

    try:
        resolved_target = resolve_bridge_delivery_target(event, explicit_target=miya_target)
    except Exception as exc:
        mark_failed(event["dedupe_key"], failed_at=now, actor=BRIDGE_ACTOR, note=str(exc))
        print(str(exc), file=sys.stderr)
        return 1

    prompt = build_miya_bridge_prompt(event, report, miya_target=resolved_target)
    result = invoke_miya_chat(prompt, profile=profile)
    if _response_indicates_success(result, event["dedupe_key"]):
        updated = mark_sent_by_miya(
            event["dedupe_key"],
            sent_at=now,
            actor=BRIDGE_ACTOR,
            note=f"Bridge confirmed Miya send via profile={profile} target={resolved_target}.",
        )
        print(f"sent_by_miya {updated['profile_slug']} dedupe_key={updated['dedupe_key']}")
        return 0

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    summary = stderr or stdout or f"bridge exited with code {result.returncode}"
    mark_failed(
        event["dedupe_key"],
        failed_at=now,
        actor=BRIDGE_ACTOR,
        note=f"Miya bridge did not confirm send: {summary[:500]}",
    )
    print(summary, file=sys.stderr)
    return 1



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transitional Miya bridge for NexusOS 1:1 prep queue")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once_parser = subparsers.add_parser("run-once")
    run_once_parser.add_argument("--now")
    run_once_parser.add_argument("--profile", default=DEFAULT_MIYA_PROFILE)
    run_once_parser.add_argument("--miya-target")
    run_once_parser.set_defaults(func=cmd_run_once)

    return parser



def cmd_run_once(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(args.now, timezone_name)
    return run_once(now=now, profile=args.profile, miya_target=args.miya_target)



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))



if __name__ == "__main__":
    raise SystemExit(main())

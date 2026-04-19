from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_cli.env_loader import load_hermes_dotenv
from people_manager.prep_renderer import render_prep_note
from people_manager.reminder_log import (
    append_reminder_log,
    claim_occurrence,
    release_occurrence_claim,
    was_sent_for_occurrence,
)
from people_manager.schedule_store import (
    DEFAULT_PREP_OFFSET_MINUTES,
    DEFAULT_TEMPLATE_STYLE,
    due_reminders,
    load_schedule_registry,
    next_meeting_occurrence,
    save_schedule_registry,
)
from people_manager.storage import get_people_manager_root, load_report

load_hermes_dotenv(project_env=None)



def _parse_now(value: str | None, timezone_name: str) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed.astimezone(ZoneInfo(timezone_name))
    return datetime.now(ZoneInfo(timezone_name))



def resolve_delivery_target(delivery_target: str) -> tuple[str, str]:
    target = (delivery_target or "origin").strip()
    if target == "origin":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_HOME_CHANNEL", "").strip()
        if not token or not chat_id:
            raise RuntimeError("origin delivery requires TELEGRAM_BOT_TOKEN and TELEGRAM_HOME_CHANNEL")
        return token, chat_id
    if target == "telegram":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_HOME_CHANNEL", "").strip()
        if not token or not chat_id:
            raise RuntimeError("telegram delivery requires TELEGRAM_BOT_TOKEN and TELEGRAM_HOME_CHANNEL")
        return token, chat_id
    if target.startswith("telegram:"):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = target.split(":", 1)[1].strip()
        if not token or not chat_id:
            raise RuntimeError("telegram:<chat_id> delivery requires TELEGRAM_BOT_TOKEN")
        return token, chat_id
    raise RuntimeError(f"Unsupported delivery target: {delivery_target}")



def send_telegram_message(text: str, delivery_target: str) -> dict[str, Any]:
    token, chat_id = resolve_delivery_target(delivery_target)
    from tools.send_message_tool import _send_telegram

    return asyncio.run(_send_telegram(token, chat_id, text))



def _render_due_entry(entry: dict[str, Any]) -> str:
    minutes_until = max(1, int((entry["meeting_at"] - entry["prep_at"]).total_seconds() // 60))
    return render_prep_note(entry["report"], minutes_until=minutes_until)



def cmd_list(_args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    print(f"Schedule registry: {get_people_manager_root() / 'schedules' / 'one_on_ones.json'}")
    for slug, schedule in sorted(registry.get("profiles", {}).items()):
        meeting = schedule.get("meeting", {})
        print(f"{slug}: enabled={schedule.get('enabled', True)} type={meeting.get('type')} target={schedule.get('delivery_target', 'origin')}")
    return 0



def cmd_show(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    print(json.dumps({args.slug: schedule}, indent=2, sort_keys=True))
    return 0



def cmd_preview(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    report = load_report(args.slug)
    if not report:
        print(f"Report not found for {args.slug}", file=sys.stderr)
        return 1
    now = _parse_now(args.now, timezone_name)
    meeting_at = next_meeting_occurrence(schedule["meeting"], now=now, timezone_name=timezone_name)
    prep_offset = int(schedule.get("prep_offset_minutes", DEFAULT_PREP_OFFSET_MINUTES))
    prep_at = meeting_at - timedelta(minutes=prep_offset)
    print(render_prep_note(report, minutes_until=prep_offset))
    print(f"meeting_at={meeting_at.isoformat()}")
    print(f"prep_at={prep_at.isoformat()}")
    return 0



def _due_entries(now: datetime) -> list[dict[str, Any]]:
    return due_reminders(now=now)



def cmd_due_now(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(args.now, timezone_name)
    for entry in _due_entries(now):
        print(f"{entry['profile_slug']} due at {entry['prep_at'].isoformat()} for meeting {entry['meeting_at'].isoformat()}")
    return 0



def cmd_run_once(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(args.now, timezone_name)
    entries = _due_entries(now)
    for entry in entries:
        profile_slug = entry["profile_slug"]
        meeting_at = entry["meeting_at"]
        if was_sent_for_occurrence(profile_slug, meeting_at):
            continue
        if not claim_occurrence(profile_slug, meeting_at):
            continue
        try:
            text = _render_due_entry(entry)
            if args.dry_run:
                print(text)
                continue
            try:
                result = send_telegram_message(text, entry["schedule"].get("delivery_target", "origin"))
            except Exception as exc:
                print(f"delivery failed for {profile_slug}: {exc}", file=sys.stderr)
                continue
            if not result.get("success"):
                print(f"delivery failed for {profile_slug}: {result}", file=sys.stderr)
                continue
            append_reminder_log(
                {
                    "profile_slug": profile_slug,
                    "meeting_at": meeting_at.isoformat(),
                    "prep_sent_at": now.isoformat(),
                    "delivery_target": entry["schedule"].get("delivery_target", "origin"),
                    "template_style": entry["schedule"].get("template_style", DEFAULT_TEMPLATE_STYLE),
                    "message_preview": text[:200],
                    "status": "sent",
                }
            )
            print(f"sent {profile_slug} for {meeting_at.isoformat()}")
        finally:
            release_occurrence_claim(profile_slug, meeting_at)
    return 0



def cmd_add(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    profiles = registry.setdefault("profiles", {})
    meeting: dict[str, Any]
    if args.weekly:
        meeting = {"type": "weekly", "weekday": _weekday_name_to_iso(args.weekly[0]), "time": args.weekly[1]}
    elif args.biweekly:
        if not args.anchor_date:
            print("anchor_date is required for biweekly schedules", file=sys.stderr)
            return 1
        meeting = {
            "type": "biweekly",
            "weekday": _weekday_name_to_iso(args.biweekly[0]),
            "time": args.biweekly[1],
            "anchor_date": args.anchor_date,
        }
    else:
        meeting = {
            "type": "monthly_nth_weekday",
            "weekday": _weekday_name_to_iso(args.monthly_nth_weekday[1]),
            "ordinal": int(args.monthly_nth_weekday[0]),
            "time": args.monthly_nth_weekday[2],
        }
    profiles[args.slug] = {
        "name": args.name or args.slug,
        "enabled": True,
        "delivery_target": args.delivery_target,
        "meeting": meeting,
        "prep_offset_minutes": args.prep_offset_minutes,
        "template_style": DEFAULT_TEMPLATE_STYLE,
    }
    save_schedule_registry(registry)
    print(f"Saved schedule for {args.slug}")
    return 0



def cmd_set_style(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    schedule["template_style"] = args.style
    save_schedule_registry(registry)
    print(f"Updated style for {args.slug} -> {args.style}")
    return 0



def _toggle_enabled(slug: str, enabled: bool) -> int:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).get(slug)
    if not schedule:
        print(f"Schedule not found for {slug}", file=sys.stderr)
        return 1
    schedule["enabled"] = enabled
    save_schedule_registry(registry)
    state = "enabled" if enabled else "disabled"
    print(f"{slug} {state}")
    return 0



def cmd_enable(args: argparse.Namespace) -> int:
    return _toggle_enabled(args.slug, True)



def cmd_disable(args: argparse.Namespace) -> int:
    return _toggle_enabled(args.slug, False)



def _weekday_name_to_iso(name: str) -> int:
    mapping = {
        "mon": 1,
        "monday": 1,
        "tue": 2,
        "tuesday": 2,
        "wed": 3,
        "wednesday": 3,
        "thu": 4,
        "thursday": 4,
        "fri": 5,
        "friday": 5,
        "sat": 6,
        "saturday": 6,
        "sun": 7,
        "sunday": 7,
    }
    key = name.strip().lower()
    if key not in mapping:
        raise ValueError(f"Unknown weekday: {name}")
    return mapping[key]



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic 1:1 prep service for NexusOS V1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("slug")
    show_parser.set_defaults(func=cmd_show)

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("slug")
    preview_parser.add_argument("--now")
    preview_parser.set_defaults(func=cmd_preview)

    due_parser = subparsers.add_parser("due-now")
    due_parser.add_argument("--now")
    due_parser.set_defaults(func=cmd_due_now)

    run_parser = subparsers.add_parser("run-once")
    run_parser.add_argument("--now")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.set_defaults(func=cmd_run_once)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--slug", required=True)
    add_parser.add_argument("--name")
    add_parser.add_argument("--delivery-target", default="origin")
    add_parser.add_argument("--prep-offset-minutes", type=int, default=DEFAULT_PREP_OFFSET_MINUTES)
    group = add_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--weekly", nargs=2, metavar=("WEEKDAY", "TIME"))
    group.add_argument("--biweekly", nargs=2, metavar=("WEEKDAY", "TIME"))
    group.add_argument("--monthly-nth-weekday", nargs=3, metavar=("ORDINAL", "WEEKDAY", "TIME"))
    add_parser.add_argument("--anchor-date")
    add_parser.set_defaults(func=cmd_add)

    style_parser = subparsers.add_parser("set-style")
    style_parser.add_argument("slug")
    style_parser.add_argument("style")
    style_parser.set_defaults(func=cmd_set_style)

    enable_parser = subparsers.add_parser("enable")
    enable_parser.add_argument("slug")
    enable_parser.set_defaults(func=cmd_enable)

    disable_parser = subparsers.add_parser("disable")
    disable_parser.add_argument("slug")
    disable_parser.set_defaults(func=cmd_disable)

    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

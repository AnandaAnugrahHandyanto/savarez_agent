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
from people_manager.prep_renderer import render_fallback_prep_note, render_prep_note
from people_manager.prep_queue import (
    acquire_transition_lock,
    claim_next_for_miya,
    enqueue_due_occurrence,
    fallback_candidates,
    load_queue_event,
    mark_fallback_sent,
    mark_sent_by_miya,
    queue_state_counts,
    release_transition_lock,
)
from people_manager.reminder_log import (
    append_reminder_log,
    claim_occurrence,
    load_reminder_entries,
    release_occurrence_claim,
    reminder_entry_timestamp,
    was_sent_for_occurrence,
)
from people_manager.schedule_store import (
    DEFAULT_PREP_OFFSET_MINUTES,
    DEFAULT_TEMPLATE_STYLE,
    cancel_override,
    consume_override_for_occurrence,
    create_reschedule_override,
    due_reminders,
    load_schedule_registry,
    next_schedule_times,
    resolve_schedule_occurrence,
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



def _minutes_until(entry: dict[str, Any]) -> int:
    return max(1, int((entry["meeting_at"] - entry["prep_at"]).total_seconds() // 60))



def _render_due_entry(entry: dict[str, Any]) -> str:
    return render_prep_note(entry["report"], minutes_until=_minutes_until(entry))



def _schedule_times_for_output(schedule: dict[str, Any], *, now: datetime, timezone_name: str) -> dict[str, str | None]:
    try:
        resolved = resolve_schedule_occurrence(schedule, now=now, timezone_name=timezone_name)
        return {
            "base_meeting_at": resolved["base_meeting_at"].isoformat(),
            "base_prep_at": resolved["base_prep_at"].isoformat(),
            "effective_meeting_at": resolved["meeting_at"].isoformat(),
            "effective_prep_at": resolved["prep_at"].isoformat(),
            "active_override": str((resolved.get("override") or {}).get("override_id") or "none"),
        }
    except Exception:
        return {
            "base_meeting_at": None,
            "base_prep_at": None,
            "effective_meeting_at": None,
            "effective_prep_at": None,
            "active_override": None,
        }



def _reports_root() -> Path:
    return get_people_manager_root() / "reports"


def _consume_override_from_event(event: dict[str, Any], *, sent_at: datetime) -> None:
    try:
        meeting_at = datetime.fromisoformat(str(event["meeting_at"]))
    except Exception:
        return
    consume_override_for_occurrence(str(event["profile_slug"]), meeting_at=meeting_at, consumed_at=sent_at)


def _default_reschedule_message(schedule: dict[str, Any], *, effective_meeting_at: str) -> str:
    name = str(schedule.get("name") or schedule.get("slug") or "1:1")
    return f"{name} 1:1 rescheduled (one-off) to {effective_meeting_at}"



def cmd_list(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(getattr(args, "now", None), timezone_name)
    print(f"Schedule registry: {get_people_manager_root() / 'schedules' / 'one_on_ones.json'}")
    for slug, schedule in sorted(registry.get("profiles", {}).items()):
        meeting = schedule.get("meeting", {})
        times = _schedule_times_for_output(schedule, now=now, timezone_name=timezone_name)
        print(
            f"{slug}: enabled={schedule.get('enabled', True)} type={meeting.get('type')} "
            f"target={schedule.get('delivery_target', 'origin')} "
            f"next_meeting_at={times['effective_meeting_at'] or 'invalid'} next_prep_at={times['effective_prep_at'] or 'invalid'} "
            f"base_meeting_at={times['base_meeting_at'] or 'invalid'} base_prep_at={times['base_prep_at'] or 'invalid'} "
            f"effective_meeting_at={times['effective_meeting_at'] or 'invalid'} effective_prep_at={times['effective_prep_at'] or 'invalid'} "
            f"active_override={times['active_override'] or 'none'}"
        )
    return 0



def cmd_show(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(getattr(args, "now", None), timezone_name)
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    times = _schedule_times_for_output(schedule, now=now, timezone_name=timezone_name)
    payload = dict(schedule)
    payload["next_meeting_at"] = times["effective_meeting_at"]
    payload["next_prep_at"] = times["effective_prep_at"]
    payload.update(times)
    print(json.dumps({args.slug: payload}, indent=2, sort_keys=True))
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
    resolved = resolve_schedule_occurrence(schedule, now=now, timezone_name=timezone_name)
    print(render_prep_note(report, minutes_until=_minutes_until({"meeting_at": resolved["meeting_at"], "prep_at": resolved["prep_at"]})))
    print(f"meeting_at={resolved['meeting_at'].isoformat()}")
    print(f"prep_at={resolved['prep_at'].isoformat()}")
    print(f"base_meeting_at={resolved['base_meeting_at'].isoformat()}")
    print(f"base_prep_at={resolved['base_prep_at'].isoformat()}")
    print(f"effective_meeting_at={resolved['meeting_at'].isoformat()}")
    print(f"effective_prep_at={resolved['prep_at'].isoformat()}")
    return 0



def _due_entries(now: datetime) -> list[dict[str, Any]]:
    return due_reminders(now=now)



def cmd_due_now(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(args.now, timezone_name)
    for entry in _due_entries(now):
        print(
            f"{entry['profile_slug']} due at {entry['prep_at'].isoformat()} for meeting {entry['meeting_at'].isoformat()} "
            f"base_meeting_at={entry['base_meeting_at'].isoformat()} effective_meeting_at={entry['meeting_at'].isoformat()}"
        )
    return 0



def cmd_enqueue_due(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(args.now, timezone_name)
    entries = _due_entries(now)
    for entry in entries:
        event, created = enqueue_due_occurrence(entry, detected_at=now)
        state = "queued" if created else "already-present"
        print(f"{state} {event['profile_slug']} dedupe_key={event['dedupe_key']} state={event['state']}")
    return 0



def cmd_miya_claim_next(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(getattr(args, "now", None), timezone_name)
    event = claim_next_for_miya(now=now)
    if not event:
        print("No queued occurrences for Miya")
        return 0
    print(json.dumps(event, indent=2, sort_keys=True))
    return 0



def cmd_miya_mark_sent(args: argparse.Namespace) -> int:
    event = load_queue_event(args.dedupe_key)
    if not event:
        print(f"Occurrence not found: {args.dedupe_key}", file=sys.stderr)
        return 1
    sent_at = datetime.fromisoformat(args.sent_at)
    updated = mark_sent_by_miya(args.dedupe_key, sent_at=sent_at)
    _consume_override_from_event(updated, sent_at=sent_at)
    print(f"{updated['state']} {updated['profile_slug']} dedupe_key={updated['dedupe_key']}")
    return 0



def cmd_run_fallback(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(args.now, timezone_name)
    for event in fallback_candidates(now=now):
        dedupe_key = str(event["dedupe_key"])
        if not acquire_transition_lock(dedupe_key, lock_name="fallback-send", owner="scheduler"):
            continue
        try:
            fresh = load_queue_event(dedupe_key)
            if not fresh or fresh.get("delivery_outcome"):
                continue
            report = load_report(fresh["profile_slug"])
            if not report:
                print(f"fallback failed for {fresh['profile_slug']}: missing report", file=sys.stderr)
                continue
            text = render_fallback_prep_note(report, minutes_until=int(fresh.get("minutes_until") or DEFAULT_PREP_OFFSET_MINUTES))
            try:
                result = send_telegram_message(text, fresh.get("delivery_target", "origin"))
            except Exception as exc:
                print(f"fallback failed for {fresh['profile_slug']}: {exc}", file=sys.stderr)
                continue
            if not result.get("success"):
                print(f"fallback failed for {fresh['profile_slug']}: {result}", file=sys.stderr)
                continue
            updated = mark_fallback_sent(
                dedupe_key,
                sent_at=now,
                note="Minimal deterministic fallback sent after Miya SLA miss.",
            )
            _consume_override_from_event(updated, sent_at=now)
            print(f"fallback-sent {updated['profile_slug']} dedupe_key={updated['dedupe_key']}")
        finally:
            release_transition_lock(dedupe_key, lock_name="fallback-send")
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
            consume_override_for_occurrence(profile_slug, meeting_at=meeting_at, consumed_at=now)
            print(f"sent {profile_slug} for {meeting_at.isoformat()}")
        finally:
            release_occurrence_claim(profile_slug, meeting_at)
    return 0



def _build_meeting_from_args(args: argparse.Namespace, existing: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if getattr(args, "weekly", None):
        return {"type": "weekly", "weekday": _weekday_name_to_iso(args.weekly[0]), "time": args.weekly[1]}
    if getattr(args, "biweekly", None):
        anchor_date = args.anchor_date or ((existing or {}).get("anchor_date") if (existing or {}).get("type") == "biweekly" else None)
        if not anchor_date:
            print("anchor_date is required for biweekly schedules", file=sys.stderr)
            return None
        return {
            "type": "biweekly",
            "weekday": _weekday_name_to_iso(args.biweekly[0]),
            "time": args.biweekly[1],
            "anchor_date": anchor_date,
        }
    if getattr(args, "monthly_nth_weekday", None):
        return {
            "type": "monthly_nth_weekday",
            "weekday": _weekday_name_to_iso(args.monthly_nth_weekday[1]),
            "ordinal": int(args.monthly_nth_weekday[0]),
            "time": args.monthly_nth_weekday[2],
        }
    return None



def cmd_add(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    profiles = registry.setdefault("profiles", {})
    meeting = _build_meeting_from_args(args)
    if meeting is None:
        return 1
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



def cmd_update(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    meeting = _build_meeting_from_args(args, existing=schedule.get("meeting", {}))
    if getattr(args, "weekly", None) or getattr(args, "biweekly", None) or getattr(args, "monthly_nth_weekday", None):
        if meeting is None:
            return 1
        schedule["meeting"] = meeting
    if args.name is not None:
        schedule["name"] = args.name
    if args.delivery_target is not None:
        schedule["delivery_target"] = args.delivery_target
    if args.prep_offset_minutes is not None:
        schedule["prep_offset_minutes"] = args.prep_offset_minutes
    save_schedule_registry(registry)
    print(f"Updated schedule for {args.slug}")
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



def cmd_remove(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).pop(args.slug, None)
    if schedule is None:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    if args.archive:
        registry.setdefault("archived_profiles", {})[args.slug] = schedule
    save_schedule_registry(registry)
    print(f"Removed schedule for {args.slug}")
    return 0



def cmd_reschedule_once(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(getattr(args, "now", None), timezone_name)
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    effective_meeting_at = _parse_now(args.effective_meeting_at, timezone_name)
    try:
        override = create_reschedule_override(
            args.slug,
            effective_meeting_at=effective_meeting_at,
            now=now,
            source={
                "platform": "local",
                "lane": "scripts.one_on_one_prep",
                "message_text": args.message_text or _default_reschedule_message(schedule, effective_meeting_at=effective_meeting_at.isoformat()),
            },
            override_id=args.override_id,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"saved override {override['override_id']} original_meeting_at={override['original_meeting_at']} effective_meeting_at={override['effective_meeting_at']}")
    return 0


def cmd_cancel_override(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = _parse_now(getattr(args, "now", None), timezone_name)
    try:
        override = cancel_override(args.slug, now=now, override_id=getattr(args, "override_id", None))
    except KeyError:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    if not override:
        print(f"No active override found for {args.slug}", file=sys.stderr)
        return 1
    print(f"cancelled override {override['override_id']} effective_meeting_at={override['effective_meeting_at']}")
    return 0


def cmd_overrides(args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    schedule = registry.get("profiles", {}).get(args.slug)
    if not schedule:
        print(f"Schedule not found for {args.slug}", file=sys.stderr)
        return 1
    overrides = schedule.get("overrides", []) or []
    if not overrides:
        print(f"{args.slug}: no overrides")
        return 0
    for override in overrides:
        print(
            f"{args.slug} override_id={override.get('override_id', 'none')} kind={override.get('kind')} status={override.get('status')} "
            f"original_meeting_at={override.get('original_meeting_at')} effective_meeting_at={override.get('effective_meeting_at')}"
        )
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    entries = load_reminder_entries(month=args.month, profile_slug=args.slug, limit=args.limit)
    for entry in entries:
        extras = []
        if entry.get("actor"):
            extras.append(f"actor={entry.get('actor')}")
        if entry.get("dedupe_key"):
            extras.append(f"dedupe_key={entry.get('dedupe_key')}")
        if entry.get("note"):
            extras.append(f"note={entry.get('note')}")
        suffix = f" {' '.join(extras)}" if extras else ""
        print(
            f"{reminder_entry_timestamp(entry)} {entry.get('profile_slug')} "
            f"status={entry.get('status')} meeting_at={entry.get('meeting_at')}{suffix}"
        )
    return 0



def cmd_audit(_args: argparse.Namespace) -> int:
    registry = load_schedule_registry()
    timezone_name = str(registry.get("timezone") or "Asia/Singapore")
    now = datetime.now(ZoneInfo(timezone_name))
    profiles = registry.get("profiles", {})
    report_root = _reports_root()
    report_slugs = sorted(path.stem for path in report_root.glob("*.json")) if report_root.exists() else []
    scheduled_without_report = [slug for slug in sorted(profiles) if slug not in report_slugs]
    unscheduled_reports = [slug for slug in report_slugs if slug not in profiles]
    sparse_prep = []
    malformed_schedules = []
    for slug, schedule in sorted(profiles.items()):
        report = load_report(slug)
        if report:
            if not report.get("prep_note_preference") and not (report.get("upcoming_one_on_one") or {}).get("topics") and not report.get("relationship_note"):
                sparse_prep.append(slug)
        try:
            next_schedule_times(schedule, now=now, timezone_name=timezone_name)
        except Exception:
            malformed_schedules.append(slug)
    print("Scheduled without report")
    for slug in scheduled_without_report or ["(none)"]:
        print(f"- {slug}")
    print("\nUnscheduled reports")
    for slug in unscheduled_reports or ["(none)"]:
        print(f"- {slug}")
    print("\nSparse prep metadata")
    for slug in sparse_prep or ["(none)"]:
        print(f"- {slug}")
    print("\nMalformed schedules")
    for slug in malformed_schedules or ["(none)"]:
        print(f"- {slug}")

    print("\nOccurrence queue state")
    counts = queue_state_counts()
    if counts:
        for state, count in counts.items():
            print(f"- {state}: {count}")
    else:
        print("- (none)")
    return 0



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
    list_parser.add_argument("--now")
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("slug")
    show_parser.add_argument("--now")
    show_parser.set_defaults(func=cmd_show)

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("slug")
    preview_parser.add_argument("--now")
    preview_parser.set_defaults(func=cmd_preview)

    due_parser = subparsers.add_parser("due-now")
    due_parser.add_argument("--now")
    due_parser.set_defaults(func=cmd_due_now)

    enqueue_parser = subparsers.add_parser("enqueue-due")
    enqueue_parser.add_argument("--now")
    enqueue_parser.set_defaults(func=cmd_enqueue_due)

    miya_claim_parser = subparsers.add_parser("miya-claim-next")
    miya_claim_parser.add_argument("--now")
    miya_claim_parser.set_defaults(func=cmd_miya_claim_next)

    miya_mark_sent_parser = subparsers.add_parser("miya-mark-sent")
    miya_mark_sent_parser.add_argument("--dedupe-key", required=True)
    miya_mark_sent_parser.add_argument("--sent-at", required=True)
    miya_mark_sent_parser.set_defaults(func=cmd_miya_mark_sent)

    fallback_parser = subparsers.add_parser("run-fallback")
    fallback_parser.add_argument("--now")
    fallback_parser.set_defaults(func=cmd_run_fallback)

    run_parser = subparsers.add_parser("run-once")
    run_parser.add_argument("--now")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.set_defaults(func=cmd_run_once)

    reschedule_parser = subparsers.add_parser("reschedule-once")
    reschedule_parser.add_argument("slug")
    reschedule_parser.add_argument("--effective-meeting-at", required=True)
    reschedule_parser.add_argument("--now")
    reschedule_parser.add_argument("--message-text")
    reschedule_parser.add_argument("--override-id")
    reschedule_parser.set_defaults(func=cmd_reschedule_once)

    cancel_override_parser = subparsers.add_parser("cancel-override")
    cancel_override_parser.add_argument("slug")
    cancel_override_parser.add_argument("--override-id")
    cancel_override_parser.add_argument("--now")
    cancel_override_parser.set_defaults(func=cmd_cancel_override)

    overrides_parser = subparsers.add_parser("overrides")
    overrides_parser.add_argument("slug")
    overrides_parser.set_defaults(func=cmd_overrides)

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

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--slug", required=True)
    update_parser.add_argument("--name")
    update_parser.add_argument("--delivery-target")
    update_parser.add_argument("--prep-offset-minutes", type=int)
    update_group = update_parser.add_mutually_exclusive_group(required=False)
    update_group.add_argument("--weekly", nargs=2, metavar=("WEEKDAY", "TIME"))
    update_group.add_argument("--biweekly", nargs=2, metavar=("WEEKDAY", "TIME"))
    update_group.add_argument("--monthly-nth-weekday", nargs=3, metavar=("ORDINAL", "WEEKDAY", "TIME"))
    update_parser.add_argument("--anchor-date")
    update_parser.set_defaults(func=cmd_update)

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

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("slug")
    remove_parser.add_argument("--archive", action="store_true")
    remove_parser.set_defaults(func=cmd_remove)

    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("--month")
    log_parser.add_argument("--slug")
    log_parser.add_argument("--limit", type=int, default=20)
    log_parser.set_defaults(func=cmd_log)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.set_defaults(func=cmd_audit)

    return parser



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
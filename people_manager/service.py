from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .constants import (
    ACTION_ASSESSMENT,
    ACTION_CHALLENGE,
    ACTION_NEW_REPORT,
    ACTION_ONE_ON_ONE,
    ACTION_PREP,
    ACTION_RESCHEDULE_ONCE,
    ACTION_REVIEW,
    ACTION_TEAM_QUESTION,
    ACTION_TEAM_SCAN,
    ACTION_TODO_MANAGER,
    ACTION_TODO_REPORT,
    ACTION_UPDATE,
    SUPPORTED_WORKSPACE,
)
from .ad_hoc_prep import build_ad_hoc_prep_note
from .merge import append_structured_log, apply_assessment, apply_one_on_one, apply_todo, apply_update
from .parser import parse_message
from .renderers import render_challenge, render_prep, render_review, render_team_scan
from .schedule_store import create_reschedule_override, load_schedule_registry
from .storage import (
    access_report,
    create_report,
    find_report_by_name,
    list_reports_by_recency,
    load_report,
    resolve_report_by_name,
    save_report,
    touch_report,
)


def _team_question_to_scan(prompt_variant: str, reports: list[dict]) -> str:
    base = render_team_scan(reports)
    prompts = {
        "under_managing": "\n\nChallenge lens\n- Look for people with repeated issues but no explicit manager intervention.",
        "over_scoped": "\n\nChallenge lens\n- Look for people carrying rising complexity without matching decision rights.",
        "too_generous": "\n\nChallenge lens\n- Check whether loyalty is being confused with current leverage.",
    }
    return base + prompts.get(prompt_variant, "")


def _load_reports_by_recency() -> list[dict]:
    reports = []
    for meta in list_reports_by_recency():
        report = load_report(meta["slug"])
        if report:
            reports.append(report)
    return reports


def _parse_reschedule_phrase(value: str, *, now: datetime, timezone_name: str) -> datetime:
    text = (value or "").strip()
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed.astimezone(ZoneInfo(timezone_name))
    except ValueError:
        pass
    match = re.match(r"(?i)^(today|tomorrow)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", text)
    if not match:
        raise ValueError(f"Unsupported reschedule time phrase: {value}")
    day_word, hour_text, minute_text, meridiem = match.groups()
    hour = int(hour_text)
    minute = int(minute_text or "00")
    if not (1 <= hour <= 12 and 0 <= minute <= 59):
        raise ValueError(f"Unsupported reschedule time phrase: {value}")
    hour_24 = hour % 12
    if meridiem.lower() == "pm":
        hour_24 += 12
    local_now = now.astimezone(ZoneInfo(timezone_name))
    target_day = local_now.date() + timedelta(days=1 if day_word.lower() == "tomorrow" else 0)
    return datetime(target_day.year, target_day.month, target_day.day, hour_24, minute, tzinfo=ZoneInfo(timezone_name))


def handle_people_message(text: str, lane_id: str, workspace: str, now: datetime | None = None) -> str | None:
    if workspace != SUPPORTED_WORKSPACE:
        return None

    parsed = parse_message(text)
    if parsed is None:
        return None

    if parsed.action == ACTION_NEW_REPORT:
        existing = find_report_by_name(parsed.report_name or "")
        if existing:
            return f"Report already exists for {existing['name']}. Use `Update {existing['name']}: ...` instead."
        report = create_report(
            name=parsed.report_name or "",
            role_title=parsed.role_title or "",
            mandate=parsed.body or "",
        )
        return f"Created report for {report['name']} ({report['role_title']}). Mandate: {report['role_charter']['mandate']}"

    if parsed.action == ACTION_TEAM_SCAN:
        return render_team_scan(_load_reports_by_recency())

    if parsed.action == ACTION_TEAM_QUESTION:
        reports = _load_reports_by_recency()
        return _team_question_to_scan(parsed.prompt_variant or "", reports)

    if parsed.action == ACTION_PREP:
        return build_ad_hoc_prep_note(parsed.report_name or "")

    meta, matches = resolve_report_by_name(parsed.report_name or "")
    if not meta:
        if matches:
            names = ", ".join(str(item.get("name") or item.get("slug") or "Unknown") for item in matches)
            return f"Multiple direct reports match `{parsed.report_name}`: {names}. Use full name."
        return f"No direct report found for `{parsed.report_name}`. Start with `New report: {parsed.report_name} - <role> - <mandate>`."
    report = load_report(meta["slug"])
    if not report:
        return f"Report record for `{parsed.report_name}` is missing on disk."

    if parsed.action == ACTION_RESCHEDULE_ONCE:
        registry = load_schedule_registry()
        timezone_name = str(registry.get("timezone") or "Asia/Singapore")
        local_now = now or datetime.now(ZoneInfo(timezone_name))
        try:
            effective_meeting_at = _parse_reschedule_phrase(parsed.body or "", now=local_now, timezone_name=timezone_name)
            override = create_reschedule_override(
                report["slug"],
                effective_meeting_at=effective_meeting_at,
                now=local_now,
                source={
                    "platform": lane_id.split(":", 1)[0] if ":" in lane_id else "local",
                    "lane": lane_id,
                    "message_text": text,
                },
            )
        except ValueError as exc:
            return str(exc)
        except KeyError:
            return f"No schedule found for `{report['name']}`. Add the recurring 1:1 schedule first."
        report = append_structured_log(
            report,
            entry_type="one_on_one_reschedule_override",
            lane_id=lane_id,
            raw_text=text,
            facts=[
                f"one-off 1:1 moved to {override['effective_meeting_at']}",
                f"recurring base remains {override['original_meeting_at']}",
            ],
            resulting_actions=[f"Created override {override['override_id']}"] if override.get("override_id") else None,
        )
        save_report(report)
        touch_report(report["slug"])
        return (
            f"One-off reschedule saved for {report['name']}: {override['original_meeting_at']} -> {override['effective_meeting_at']}. "
            "Recurring cadence unchanged."
        )

    if parsed.action == ACTION_UPDATE:
        report = apply_update(report, parsed.body or "", lane_id=lane_id)
        save_report(report)
        touch_report(report["slug"])
        return f"Profile updated for {report['name']}."
    if parsed.action == ACTION_ONE_ON_ONE:
        report = apply_one_on_one(report, parsed.body or "", lane_id=lane_id)
        save_report(report)
        touch_report(report["slug"])
        return f"1:1 notes saved for {report['name']}."
    if parsed.action == ACTION_ASSESSMENT:
        report = apply_assessment(report, parsed.body or "", lane_id=lane_id)
        save_report(report)
        touch_report(report["slug"])
        return f"Assessment updated for {report['name']}."
    if parsed.action == ACTION_TODO_REPORT:
        report = apply_todo(report, parsed.body or "", for_manager=False, lane_id=lane_id)
        save_report(report)
        touch_report(report["slug"])
        return f"Added todo for {report['name']}."
    if parsed.action == ACTION_TODO_MANAGER:
        report = apply_todo(report, parsed.body or "", for_manager=True, lane_id=lane_id)
        save_report(report)
        touch_report(report["slug"])
        return f"Added manager follow-up for {report['name']}."
    if parsed.action == ACTION_PREP:
        access_report(report["slug"])
        return render_prep(report)
    if parsed.action == ACTION_REVIEW:
        access_report(report["slug"])
        return render_review(report)
    if parsed.action == ACTION_CHALLENGE:
        access_report(report["slug"])
        return render_challenge(report)
    return None
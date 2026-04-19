from __future__ import annotations

from .constants import (
    ACTION_ASSESSMENT,
    ACTION_CHALLENGE,
    ACTION_NEW_REPORT,
    ACTION_ONE_ON_ONE,
    ACTION_PREP,
    ACTION_REVIEW,
    ACTION_TEAM_QUESTION,
    ACTION_TEAM_SCAN,
    ACTION_TODO_MANAGER,
    ACTION_TODO_REPORT,
    ACTION_UPDATE,
    SUPPORTED_WORKSPACE,
)
from .merge import apply_assessment, apply_one_on_one, apply_todo, apply_update
from .parser import parse_message
from .renderers import render_challenge, render_prep, render_review, render_team_scan
from .storage import (
    access_report,
    create_report,
    find_report_by_name,
    list_reports_by_recency,
    load_report,
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


def handle_people_message(text: str, lane_id: str, workspace: str) -> str | None:
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

    meta = find_report_by_name(parsed.report_name or "")
    if not meta:
        return f"No direct report found for `{parsed.report_name}`. Start with `New report: {parsed.report_name} - <role> - <mandate>`."
    report = load_report(meta["slug"])
    if not report:
        return f"Report record for `{parsed.report_name}` is missing on disk."

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

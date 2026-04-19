from __future__ import annotations

from typing import Iterable


def _last_entries(report: dict, count: int = 3) -> list[dict]:
    return list(report.get("interaction_log", [])[-count:])


def render_prep(report: dict) -> str:
    current_read = report.get("performance", {}).get("current_performance_read") or "No explicit performance read yet."
    recent = _last_entries(report)
    changed = "; ".join(entry["source"]["message_text"] for entry in recent) or "No recent updates captured."
    open_loops = report.get("open_loops", {})
    loops = open_loops.get("open_todos_for_them", []) + open_loops.get("open_todos_for_michael", [])
    loop_text = "; ".join(loops) or "No open loops captured."
    mandate = report.get("role_charter", {}).get("mandate") or "Mandate not yet captured."
    return (
        f"Prep brief — {report['name']}\n\n"
        f"Current read\n- {current_read}\n\n"
        f"What changed since last touchpoint\n- {changed}\n\n"
        f"Open loops\n- {loop_text}\n\n"
        f"Questions to ask\n- Where are you blocked against the mandate: {mandate}?\n\n"
        f"Message to land\n- Push for clearer ownership and proactive escalation where needed.\n\n"
        f"Management objective\n- Leave the meeting with one sharper management move and one explicit next step."
    )


def render_review(report: dict) -> str:
    role = report.get("role_title") or "Unknown role"
    mandate = report.get("role_charter", {}).get("mandate") or "Mandate not yet captured."
    performance = report.get("performance", {})
    strengths = report.get("strengths") or ["No strengths captured yet."]
    weaknesses = report.get("weaknesses") or report.get("failure_modes") or ["No weaknesses captured yet."]
    recommendation = report.get("management_strategy", {}).get("how_michael_should_manage_them") or ["Clarify expectations and gather more evidence."]
    evidence_basis = performance.get("evidence_basis") or []
    strongest_evidence = evidence_basis[-1] if evidence_basis else "Evidence base is still thin."
    unresolved_doubts = report.get("open_loops", {}).get("unresolved_questions") or ["Need more evidence on sustained leverage and scope fit."]
    return (
        f"Review memo — {report['name']}\n\n"
        f"Role and mandate\n- {role}\n- {mandate}\n\n"
        f"Current performance read\n- {performance.get('current_performance_read') or 'No explicit read yet.'}\n\n"
        f"Trajectory\n- {performance.get('trajectory', 'unclear')}\n\n"
        f"Strongest evidence\n- {strongest_evidence}\n\n"
        f"Unresolved doubts\n- " + "\n- ".join(unresolved_doubts) + "\n\n"
        f"Strengths\n- " + "\n- ".join(strengths) + "\n\n"
        f"Weaknesses / failure modes\n- " + "\n- ".join(weaknesses) + "\n\n"
        f"Managerial recommendation\n- " + "\n- ".join(recommendation) + "\n\n"
        f"Suggested next management move\n- {recommendation[0]}\n\n"
        f"Confidence and missing evidence\n- Confidence: {performance.get('confidence_level_in_read', 'low')}"
    )


def render_team_scan(reports: Iterable[dict]) -> str:
    reports = list(reports)
    if not reports:
        return "Team scan\n\nOverall org read\n- No direct reports captured yet."

    def _has_management_follow_through(report: dict) -> bool:
        strategy = report.get("management_strategy", {})
        open_loops = report.get("open_loops", {})
        return bool(strategy.get("current_manager_interventions") or open_loops.get("open_todos_for_michael"))

    def _has_concern_signal(report: dict) -> bool:
        performance = report.get("performance", {})
        open_loops = report.get("open_loops", {})
        return any(
            [
                performance.get("trajectory") in {"declining", "unclear"},
                bool(open_loops.get("active_risks")),
                bool(open_loops.get("unresolved_questions")),
                bool(open_loops.get("open_todos_for_them")),
            ]
        )

    names = ", ".join(report["name"] for report in reports)
    strongest = [report["name"] for report in reports if report.get("performance", {}).get("trajectory") == "rising"]
    fragile = [report["name"] for report in reports if report.get("performance", {}).get("trajectory") == "declining"]
    unclear = [report["name"] for report in reports if not report.get("role_charter", {}).get("mandate")]
    under_managed = [
        report["name"]
        for report in reports
        if len(report.get("interaction_log", [])) >= 2
        and _has_concern_signal(report)
        and not _has_management_follow_through(report)
    ]
    needing_stretch = [report["name"] for report in reports if report.get("performance", {}).get("trajectory") == "rising"]
    needing_support = [report["name"] for report in reports if report.get("performance", {}).get("trajectory") in {"declining", "unclear"}]
    return (
        "Team scan\n\n"
        f"Overall org read\n- Tracking {len(reports)} direct report(s): {names}.\n\n"
        f"Strongest people / leverage nodes\n- {', '.join(strongest) if strongest else 'No clear strongest node captured yet.'}\n\n"
        f"Fragile nodes\n- {', '.join(fragile) if fragile else 'No explicitly fragile node captured yet.'}\n\n"
        f"Under-managed people\n- {', '.join(under_managed) if under_managed else 'No clear under-managed pattern from stored data.'}\n\n"
        f"People with unclear mandate\n- {', '.join(unclear) if unclear else 'No unclear mandates flagged from stored data.'}\n\n"
        f"People needing stretch\n- {', '.join(needing_stretch) if needing_stretch else 'No clear stretch candidate captured yet.'}\n\n"
        f"People needing support\n- {', '.join(needing_support) if needing_support else 'No clear support-needed case captured yet.'}\n\n"
        "Management attention allocation advice\n- Focus attention where trajectory is weak or evidence is thin.\n\n"
        "Decisions Michael may be postponing\n- Review where repeated issues exist without a corresponding management intervention."
    )


def render_challenge(report: dict) -> str:
    evidence_count = len(report.get("interaction_log", []))
    current_read = report.get("performance", {}).get("current_performance_read") or "No explicit read yet."
    if evidence_count < 2:
        caveat = "The evidence is still thin, so any challenge here should be treated as provisional."
    else:
        caveat = "There is enough directional evidence to pressure-test your current read."
    return (
        f"Challenge memo — {report['name']}\n\n"
        f"Current read\n- {current_read}\n\n"
        f"Challenge\n- {caveat}\n- Ask whether you are reacting to trust/loyalty or to actual leverage and scope fit.\n\n"
        "Suggested next move\n- Gather one more concrete piece of evidence before hardening the judgment."
    )

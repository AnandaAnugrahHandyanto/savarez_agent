"""Internal application proposal generation for Wisdom captures."""

from __future__ import annotations

from wisdom.db import WisdomDB
from wisdom.models import ApplicationRecord, CaptureRecord


def create_application_proposals(db: WisdomDB, capture_id: int) -> list[ApplicationRecord]:
    capture = db.get_capture(capture_id)
    if capture is None:
        return []
    existing = db.list_applications(capture_id)
    if existing:
        return existing
    proposals = _proposals_for_capture(capture)
    return db.insert_applications(capture_id=capture_id, applications=proposals)


def _proposals_for_capture(capture: CaptureRecord) -> list[dict[str, object]]:
    text = (capture.cleaned_text or capture.original_text).strip()
    short = _short(text)
    if capture.category == "business":
        return [
            _app("client_language", "Client language", f"Use this wording as a draft client-facing line: {short}"),
            _app("principle", "Business principle", f"Preserve the underlying principle behind: {short}"),
            _app("task_proposal", "Task proposal", f"Consider turning this into an internal follow-up: {short}"),
        ]
    if capture.category == "investing":
        return [
            _app("investment_rule", "Investment rule", f"Translate this into an investment decision rule: {short}"),
            _app("checklist", "Checklist item", f"Add this as a pre-decision checklist candidate: {short}"),
            _app("decision_rule", "Decision rule", f"Use this to reduce avoidable investing mistakes: {short}"),
        ]
    if capture.category == "health":
        return [
            _app("health_experiment", "Health experiment", f"Design a small reversible experiment around: {short}"),
            _app("decision_rule", "Decision rule", f"Use this as a decision-quality guardrail: {short}"),
        ]
    if capture.category == "life":
        return [
            _app("principle", "Life principle", f"Capture the principle behind: {short}"),
            _app("writing_idea", "Writing idea", f"Use this as a writing seed: {short}"),
            _app("decision_rule", "Decision rule", f"Turn this into a personal decision rule: {short}"),
        ]
    return [
        _app("principle", "Principle candidate", f"Review whether this should become a principle: {short}"),
        _app("writing_idea", "Writing idea", f"Use this as a writing seed: {short}"),
    ]


def _app(application_type: str, title: str, body: str) -> dict[str, object]:
    return {
        "application_type": application_type,
        "title": title,
        "body": body,
        "status": "proposed",
        "metadata": {"generator_version": 1},
    }


def _short(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 180:
        return compact
    return compact[:177].rstrip() + "..."

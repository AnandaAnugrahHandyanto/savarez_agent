"""Hermes-owned Image2 visual/reviewer gate contract.

This module consumes a job-local reviewer result and the candidate selected by
the deterministic freshness/SHA gate. It does not call Gemini/OpenAI/vision APIs
itself. Missing reviewer output fails closed so a candidate cannot be delivered
just because it is fresh.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

PASS_DECISIONS = {"PASS", "PASS_WITH_P2"}
BLOCKING_SEVERITIES = {"P0", "P1"}
BRAND_LOGO_CODES = {
    "rendered_brand_text",
    "rendered_logo",
    "fake_logo",
    "logo_placeholder",
    "brand_wordmark",
    "firepalace_wordmark",
    "assistant_added_logo",
}


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _load_review_result(job_dir: Path) -> dict[str, Any] | None:
    path = Path(job_dir) / "review_result.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, Mapping) else None


def _issue_severity(issue: Mapping[str, Any]) -> str:
    return str(issue.get("severity") or issue.get("level") or "").strip().upper()


def _issue_code(issue: Mapping[str, Any]) -> str:
    return str(issue.get("code") or issue.get("type") or issue.get("rule") or "").strip().lower()


def _issue_list(review_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues = review_result.get("issues") or review_result.get("findings") or []
    if not isinstance(issues, list):
        return []
    return [dict(item) for item in issues if isinstance(item, Mapping)]


def evaluate_review_gate(
    *,
    job_dir: Path,
    candidate: Mapping[str, Any] | None,
    review_result: Mapping[str, Any] | None = None,
    write_result: bool = True,
) -> dict[str, Any]:
    """Evaluate final-image reviewer output before delivery.

    PASS and PASS_WITH_P2 are deliverable for a fast preview only when no P0/P1
    issue is present. Fire Palace rendered-logo/brand-mark issues are treated as
    hard blockers even if a reviewer accidentally labels them as lower priority.
    """
    root = Path(job_dir)
    candidate_record = dict(candidate or {})
    candidate_path = Path(str(candidate_record.get("path") or "")).expanduser() if candidate_record.get("path") else None
    loaded_review = dict(review_result) if isinstance(review_result, Mapping) else _load_review_result(root)
    reasons: list[str] = []

    if not candidate_path or not candidate_path.is_file():
        reasons.append("candidate_file_missing")

    if loaded_review is None:
        reasons.append("review_result_missing")
        decision = ""
        issues: list[dict[str, Any]] = []
    else:
        decision = str(loaded_review.get("decision") or loaded_review.get("status") or "").strip().upper()
        issues = _issue_list(loaded_review)
        if decision not in PASS_DECISIONS:
            reasons.append("review_decision_not_pass")
        if any(_issue_severity(issue) in BLOCKING_SEVERITIES for issue in issues):
            reasons.append("p1_or_p0_review_issue")
        if any(_issue_code(issue) in BRAND_LOGO_CODES for issue in issues):
            reasons.append("brand_or_logo_issue")

    # Stable/deduped reason order helps audit logs and tests.
    ordered_reasons = list(dict.fromkeys(reasons))
    result = {
        "status": "pass" if not ordered_reasons else "rejected",
        "reasons": ordered_reasons,
        "decision": decision,
        "candidate": candidate_record,
        "issues": issues,
        "note": "review-gate-only; no vision API or Feishu delivery side effect was run",
    }
    if write_result:
        root.mkdir(parents=True, exist_ok=True)
        (root / "review_gate_result.json").write_text(_safe_json(result), encoding="utf-8")
    return result

"""Lightweight visual review provider for Hermes-owned Image2 fast previews."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def review_candidate_image(
    *,
    job_dir: Path,
    candidate: Mapping[str, Any],
    prompt_text: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Produce a conservative fast-preview review result.

    The deterministic `evaluate_review_gate` remains the hard blocker. This
    provider intentionally returns PASS_WITH_P2 rather than a finished-production
    PASS, so the generated image can be delivered as a preview only after SHA,
    freshness, and no-P0/P1 gate checks. Live rounds should still add external
    vision/human review evidence to the audit when quality matters.
    """
    path = Path(str(candidate.get("path") or "")).expanduser()
    issues: list[dict[str, Any]] = []
    decision = "PASS_WITH_P2"
    if not path.is_file():
        decision = "REJECT"
        issues.append({"severity": "P1", "code": "candidate_file_missing", "detail": str(path)})
    else:
        issues.append({
            "severity": "P2",
            "code": "fast_preview_visual_review_required",
            "detail": "自动快审仅确认文件/队列/gate 条件；正式投放前仍需人工或外部视觉复核。",
        })
    result = {
        "decision": decision,
        "issues": issues,
        "reviewer": str((environ or {}).get("IMAGE2_REVIEWER_PROVIDER") or "heuristic-fast-preview"),
        "candidate_path": str(path),
        "candidate_sha256": str(candidate.get("sha256") or ""),
        "prompt_excerpt": str(prompt_text or "")[:240],
    }
    root = Path(job_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "review_result.json").write_text(_safe_json(result), encoding="utf-8")
    return result

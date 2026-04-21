from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep003/generated_fal_live_manifest_ep003.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_contains_hardened_qc_fields() -> None:
    manifest = _load_json(MANIFEST_PATH)
    for panel in manifest["panels"]:
        assert {
            "review_status",
            "candidate_count",
            "selected_candidate",
            "rejected_candidates",
            "selection_reason",
            "rerender_reason",
            "policy_sanitized",
            "final_prompt_changed",
            "candidates",
            "selected_scores",
            "generated_panel_path",
            "final_panel_path",
        } <= set(panel)


def test_non_reviewed_pilot_exceptions_have_explicit_reason_and_single_candidate() -> None:
    manifest = _load_json(MANIFEST_PATH)
    exception_panels = [panel for panel in manifest["panels"] if panel["review_status"] == "not_reviewed_pilot_exception"]
    assert exception_panels
    for panel in exception_panels:
        assert panel["candidate_count"] == len(panel["candidates"])
        assert panel["rerender_reason"]
        assert panel["selected_scores"] is None

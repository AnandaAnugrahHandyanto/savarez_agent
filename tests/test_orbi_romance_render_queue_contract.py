from __future__ import annotations

from pathlib import Path

from tests.orbi_romance_contract_helpers import load_yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/webtoon/ep003/render_queue.yaml"


def test_render_queue_stays_live_fal_only_and_hardened() -> None:
    queue = load_yaml(QUEUE_PATH)
    assert queue["render_mode"] == "live_fal_flux2_pro"
    assert queue["contract_versions"] == {"shot_spec": 2, "continuity_bible": 1, "qc_manifest": 1}
    assert queue["candidate_policy"]["selection_required"] is True


def test_review_required_panels_are_subset_of_jobs() -> None:
    queue = load_yaml(QUEUE_PATH)
    job_ids = {job["panel_id"] for job in queue["jobs"]}
    review_ids = set(queue["candidate_policy"]["review_required_panels"])
    assert review_ids <= job_ids

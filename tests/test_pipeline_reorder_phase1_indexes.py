from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_MANIFEST = REPO_ROOT / "projects/orbi-romance-20260421/manifest.json"
PIPELINE_INDEX = REPO_ROOT / "pipeline/INDEX.json"
EXPERIMENTS_INDEX = REPO_ROOT / "experiments/INDEX.json"
ARTIFACTS_INDEX = REPO_ROOT / "artifacts/INDEX.json"
LEGACY_DELIVERABLES_MANIFEST = (
    REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json"
)
LEGACY_PROJECT_ROOT = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_repo_relative_target_exists(rel_path: str) -> None:
    target = REPO_ROOT / rel_path
    assert target.exists(), f"Expected mapped target to exist: {rel_path}"


def test_phase1_canonical_indexes_exist() -> None:
    for path in (PROJECT_MANIFEST, PIPELINE_INDEX, EXPERIMENTS_INDEX, ARTIFACTS_INDEX):
        assert path.exists(), f"Missing Phase 1 canonical index: {path.relative_to(REPO_ROOT)}"


def test_pipeline_index_maps_runtime_entrypoints_to_real_legacy_files() -> None:
    index = _load_json(PIPELINE_INDEX)

    assert index["phase"] == "phase1_non_destructive_mapping"
    for entry in index["legacy_runtime_entrypoints"].values():
        _assert_repo_relative_target_exists(entry["legacy_path"])


def test_project_manifest_points_to_real_romance_legacy_sources() -> None:
    manifest = _load_json(PROJECT_MANIFEST)

    assert manifest["legacy_project_root"] == "docs/plans/orbi-romance-webtoon-20260421"
    _assert_repo_relative_target_exists(manifest["legacy_project_root"])

    for rel_path in manifest["source_documents"].values():
        _assert_repo_relative_target_exists(rel_path)

    for episode in manifest["episodes"]:
        _assert_repo_relative_target_exists(episode["novel"])
        _assert_repo_relative_target_exists(episode["webtoon_spec_dir"])
        _assert_repo_relative_target_exists(episode["render_artifacts"])


def test_experiments_index_points_to_real_dated_contexts() -> None:
    index = _load_json(EXPERIMENTS_INDEX)

    for experiment in index["experiments"].values():
        _assert_repo_relative_target_exists(experiment["legacy_path"])
        for rel_path in experiment["representative_files"]:
            _assert_repo_relative_target_exists(rel_path)


def test_artifacts_index_points_to_real_generated_outputs() -> None:
    index = _load_json(ARTIFACTS_INDEX)
    artifact_set = index["artifact_sets"]["orbi-romance-20260421"]

    _assert_repo_relative_target_exists(artifact_set["legacy_project_root"])
    for episode in artifact_set["episodes"]:
        _assert_repo_relative_target_exists(episode["longscroll"])
        _assert_repo_relative_target_exists(episode["panel_dir"])
        _assert_repo_relative_target_exists(episode["raw_generation_dir"])
        _assert_repo_relative_target_exists(episode["render_manifest"])


def test_legacy_deliverables_manifest_keeps_episode_entries_and_adds_canonical_mapping() -> None:
    manifest = _load_json(LEGACY_DELIVERABLES_MANIFEST)

    assert len(manifest["episodes"]) == 5
    assert manifest["episodes"][0]["episode"] == "ep001"
    assert manifest["episodes"][-1]["episode"] == "ep005"

    mappings = manifest["canonical_mappings"]
    assert mappings["phase"] == "phase1_non_destructive_mapping"

    for abs_path in mappings.values():
        if abs_path == "phase1_non_destructive_mapping":
            continue
        assert Path(abs_path).exists(), f"Canonical mapping target missing: {abs_path}"


def test_phase1_indexes_preserve_protected_legacy_root() -> None:
    assert LEGACY_PROJECT_ROOT.exists()
    assert (LEGACY_PROJECT_ROOT / "webtoon/render_webtoon_fal_live_episode.py").exists()
    assert (LEGACY_PROJECT_ROOT / "deliverables/manifest.json").exists()

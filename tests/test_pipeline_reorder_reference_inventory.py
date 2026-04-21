from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_INDEX = REPO_ROOT / "pipeline/INDEX.json"
PROJECT_MANIFEST = REPO_ROOT / "projects/orbi-romance-20260421/manifest.json"
EXPERIMENTS_INDEX = REPO_ROOT / "experiments/INDEX.json"
RUNTIME_INVENTORY = REPO_ROOT / "pipeline/runtime_inventory.json"
PROJECT_PATH_INVENTORY = REPO_ROOT / "projects/orbi-romance-20260421/path_inventory.json"
EXPERIMENTS_PATH_INVENTORY = REPO_ROOT / "experiments/path_inventory.json"
ARTIFACTS_PATH_INVENTORY = REPO_ROOT / "artifacts/orbi-romance-20260421/path_inventory.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _assert_repo_relative_target_exists(rel_path: str) -> None:
    target = REPO_ROOT / rel_path
    assert target.exists(), f"Expected repo-relative target to exist: {rel_path}"


def _assert_absolute_target_exists(abs_path: str) -> None:
    target = Path(abs_path)
    assert target.is_absolute(), f"Expected absolute path contract: {abs_path}"
    assert target.exists(), f"Expected absolute target to exist: {abs_path}"


def test_phase2_inventory_files_exist() -> None:
    for path in (
        RUNTIME_INVENTORY,
        PROJECT_PATH_INVENTORY,
        EXPERIMENTS_PATH_INVENTORY,
        ARTIFACTS_PATH_INVENTORY,
    ):
        assert path.exists(), f"Missing Phase 2 inventory: {path.relative_to(REPO_ROOT)}"


def test_runtime_inventory_matches_pipeline_index_and_protected_tests() -> None:
    runtime_inventory = _load_json(RUNTIME_INVENTORY)
    pipeline_index = _load_json(PIPELINE_INDEX)

    assert set(runtime_inventory["runtime_entrypoints"]) == set(pipeline_index["legacy_runtime_entrypoints"])
    for name, entry in runtime_inventory["runtime_entrypoints"].items():
        indexed = pipeline_index["legacy_runtime_entrypoints"][name]
        assert entry["legacy_path"] == indexed["legacy_path"]
        assert entry["kind"] == indexed["kind"]
        assert entry["canonical_role"] == indexed["canonical_role"]
        assert entry["path_style"] == "repo_relative"
        _assert_repo_relative_target_exists(entry["legacy_path"])

    expected_sites = {
        "tests/test_balloon_pipeline_ep001.py",
        "tests/test_balloon_pipeline_ep001_live.py",
        "tests/test_tail_less_contracts.py",
        "tests/test_webtoon_prompt_schema_ep001.py",
    }
    assert set(runtime_inventory["protected_test_sites"]) == expected_sites
    for test_path, entry in runtime_inventory["protected_test_sites"].items():
        assert (REPO_ROOT / test_path).exists()
        for rel_path in entry.get("module_imports", []):
            _assert_repo_relative_target_exists(rel_path)
        for rel_path in entry.get("data_inputs", []):
            _assert_repo_relative_target_exists(rel_path)


def test_project_inventory_covers_current_manifest_contracts() -> None:
    inventory = _load_json(PROJECT_PATH_INVENTORY)
    manifest = _load_json(PROJECT_MANIFEST)

    manifest_inventory = inventory["manifest_files"]["projects/orbi-romance-20260421/manifest.json"]
    assert manifest_inventory["legacy_project_root"]["path"] == manifest["legacy_project_root"]
    _assert_repo_relative_target_exists(manifest_inventory["legacy_project_root"]["path"])

    source_documents = {item["key"]: item["path"] for item in manifest_inventory["source_documents"]}
    assert source_documents == manifest["source_documents"]
    for rel_path in source_documents.values():
        _assert_repo_relative_target_exists(rel_path)

    assert [episode["episode"] for episode in manifest_inventory["episodes"]] == [
        episode["episode"] for episode in manifest["episodes"]
    ]
    for episode_inventory, episode_manifest in zip(manifest_inventory["episodes"], manifest["episodes"], strict=True):
        assert episode_inventory["novel"]["path"] == episode_manifest["novel"]
        assert episode_inventory["webtoon_spec_dir"]["path"] == episode_manifest["webtoon_spec_dir"]
        assert episode_inventory["render_artifacts"]["path"] == episode_manifest["render_artifacts"]
        _assert_repo_relative_target_exists(episode_inventory["novel"]["path"])
        _assert_repo_relative_target_exists(episode_inventory["webtoon_spec_dir"]["path"])
        _assert_repo_relative_target_exists(episode_inventory["render_artifacts"]["path"])

    deliverables_inventory = inventory["manifest_files"][
        "docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json"
    ]
    for mapping in deliverables_inventory["canonical_mappings"]:
        if mapping["path_style"] == "literal":
            assert mapping["key"] == "phase"
            continue
        _assert_absolute_target_exists(mapping["path"])
    for episode in deliverables_inventory["episodes"]:
        for field in episode["fields"]:
            _assert_absolute_target_exists(field["path"])


def test_experiments_inventory_matches_phase1_index() -> None:
    inventory = _load_json(EXPERIMENTS_PATH_INVENTORY)
    experiments_index = _load_json(EXPERIMENTS_INDEX)

    assert set(inventory["experiments"]) == set(experiments_index["experiments"])
    for name, entry in inventory["experiments"].items():
        indexed = experiments_index["experiments"][name]
        assert entry["canonical_role"] == indexed["canonical_role"]
        assert entry["legacy_path"]["path"] == indexed["legacy_path"]
        _assert_repo_relative_target_exists(entry["legacy_path"]["path"])
        assert [item["path"] for item in entry["representative_files"]] == indexed["representative_files"]
        for item in entry["representative_files"]:
            _assert_repo_relative_target_exists(item["path"])


def test_artifact_inventory_covers_render_queues_generated_manifests_and_writer_sites() -> None:
    inventory = _load_json(ARTIFACTS_PATH_INVENTORY)

    expected_episodes = [f"ep{index:03d}" for index in range(1, 6)]
    assert [entry["episode"] for entry in inventory["render_queues"]] == expected_episodes
    assert [entry["episode"] for entry in inventory["generated_manifests"]] == expected_episodes

    for queue_entry in inventory["render_queues"]:
        _assert_repo_relative_target_exists(queue_entry["path"])
        queue = _load_yaml(REPO_ROOT / queue_entry["path"])
        for output in queue_entry["outputs"]:
            assert output["path_style"] == "repo_relative"
            assert queue["output"][output["key"]] == output["path"]
            _assert_repo_relative_target_exists(output["path"])

    for manifest_entry in inventory["generated_manifests"]:
        _assert_repo_relative_target_exists(manifest_entry["path"])
        generated_manifest = _load_json(REPO_ROOT / manifest_entry["path"])
        for field in manifest_entry["root_fields"]:
            assert generated_manifest[field["key"]] == field["path"]
            _assert_absolute_target_exists(field["path"])
        for panel in generated_manifest["panels"]:
            for field in manifest_entry["panel_path_fields"]:
                _assert_absolute_target_exists(panel[field["key"]])

    for rel_path, manifest_entry in inventory["supplemental_manifests"].items():
        _assert_repo_relative_target_exists(rel_path)
        manifest = _load_json(REPO_ROOT / rel_path)
        for field in manifest_entry["root_fields"]:
            assert manifest[field["key"]] == field["path"]
            _assert_absolute_target_exists(field["path"])
        for panel in manifest["panels"]:
            for field in manifest_entry["panel_path_fields"]:
                _assert_absolute_target_exists(panel[field["key"]])

    for rel_path, entry in inventory["writer_sites"].items():
        writer_path = REPO_ROOT / rel_path
        assert writer_path.exists()
        source = writer_path.read_text(encoding="utf-8")
        for marker in entry["contract_markers"]:
            assert marker in source, f"Missing writer contract marker {marker!r} in {rel_path}"

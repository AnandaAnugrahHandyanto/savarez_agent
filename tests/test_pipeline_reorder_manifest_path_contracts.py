from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_MANIFEST = REPO_ROOT / "projects/orbi-romance-20260421/manifest.json"
DELIVERABLES_MANIFEST = REPO_ROOT / "docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json"
PROJECT_PATH_INVENTORY = REPO_ROOT / "projects/orbi-romance-20260421/path_inventory.json"
ARTIFACTS_PATH_INVENTORY = REPO_ROOT / "artifacts/orbi-romance-20260421/path_inventory.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_project_manifest_repo_relative_contract_matches_inventory() -> None:
    manifest = _load_json(PROJECT_MANIFEST)
    inventory = _load_json(PROJECT_PATH_INVENTORY)["manifest_files"][
        "projects/orbi-romance-20260421/manifest.json"
    ]

    assert not Path(manifest["legacy_project_root"]).is_absolute()
    assert inventory["legacy_project_root"]["path_style"] == "repo_relative"
    assert inventory["legacy_project_root"]["path"] == manifest["legacy_project_root"]

    inventory_source_documents = {item["key"]: item for item in inventory["source_documents"]}
    assert set(inventory_source_documents) == set(manifest["source_documents"])
    for key, rel_path in manifest["source_documents"].items():
        assert not Path(rel_path).is_absolute()
        assert inventory_source_documents[key]["path"] == rel_path
        assert inventory_source_documents[key]["path_style"] == "repo_relative"

    for inventory_episode, manifest_episode in zip(inventory["episodes"], manifest["episodes"], strict=True):
        for field in ("novel", "webtoon_spec_dir", "render_artifacts"):
            assert not Path(manifest_episode[field]).is_absolute()
            assert inventory_episode[field]["path"] == manifest_episode[field]
            assert inventory_episode[field]["path_style"] == "repo_relative"


def test_deliverables_manifest_absolute_contract_matches_inventory() -> None:
    manifest = _load_json(DELIVERABLES_MANIFEST)
    inventory = _load_json(PROJECT_PATH_INVENTORY)["manifest_files"][
        "docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json"
    ]

    inventory_mappings = {item["key"]: item for item in inventory["canonical_mappings"]}
    for key, value in manifest["canonical_mappings"].items():
        if key == "phase":
            assert inventory_mappings[key]["path_style"] == "literal"
            assert inventory_mappings[key]["path"] == value
            continue
        assert Path(value).is_absolute()
        assert inventory_mappings[key]["path_style"] == "absolute"
        assert inventory_mappings[key]["path"] == value

    for inventory_episode, manifest_episode in zip(inventory["episodes"], manifest["episodes"], strict=True):
        assert inventory_episode["episode"] == manifest_episode["episode"]
        assert inventory_episode["render_mode"] == manifest_episode["render_mode"]
        inventory_fields = {item["key"]: item for item in inventory_episode["fields"]}
        for key, value in manifest_episode.items():
            if key in {"episode", "render_mode"}:
                continue
            assert Path(value).is_absolute()
            assert inventory_fields[key]["path_style"] == "absolute"
            assert inventory_fields[key]["path"] == value


def test_render_queue_outputs_remain_repo_relative_and_match_inventory() -> None:
    inventory = _load_json(ARTIFACTS_PATH_INVENTORY)

    for queue_entry in inventory["render_queues"]:
        queue = _load_yaml(REPO_ROOT / queue_entry["path"])
        for output in queue_entry["outputs"]:
            actual_value = queue["output"][output["key"]]
            assert not Path(actual_value).is_absolute()
            assert output["path_style"] == "repo_relative"
            assert output["path"] == actual_value


def test_generated_render_manifests_remain_absolute_and_match_inventory() -> None:
    inventory = _load_json(ARTIFACTS_PATH_INVENTORY)

    for manifest_entry in inventory["generated_manifests"]:
        manifest = _load_json(REPO_ROOT / manifest_entry["path"])
        for field in manifest_entry["root_fields"]:
            actual_value = manifest[field["key"]]
            assert Path(actual_value).is_absolute()
            assert field["path_style"] == "absolute"
            assert field["path"] == actual_value
        for panel in manifest["panels"]:
            for field in manifest_entry["panel_path_fields"]:
                assert Path(panel[field["key"]]).is_absolute()
                assert field["path_style"] == "absolute"

    for rel_path, manifest_entry in inventory["supplemental_manifests"].items():
        manifest = _load_json(REPO_ROOT / rel_path)
        for field in manifest_entry["root_fields"]:
            actual_value = manifest[field["key"]]
            assert Path(actual_value).is_absolute()
            assert field["path_style"] == "absolute"
            assert field["path"] == actual_value
        for panel in manifest["panels"]:
            for field in manifest_entry["panel_path_fields"]:
                assert Path(panel[field["key"]]).is_absolute()
                assert field["path_style"] == "absolute"

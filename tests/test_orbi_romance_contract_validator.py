from __future__ import annotations

import json
from pathlib import Path
import shutil

from tests.orbi_romance_contract_helpers import PROJECT_ROOT, load_contracts_module

CONTRACTS = load_contracts_module("orbi_romance_webtoon_contracts")


def test_strict_validator_passes_for_ep003_hardened_bundle() -> None:
    errors = CONTRACTS.validate_episode_contracts(PROJECT_ROOT, "ep003", strict=True)
    assert errors == []


def test_strict_validator_rejects_v1_shot_spec_inputs(tmp_path: Path) -> None:
    project_copy = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT, project_copy)
    panel_prompts = project_copy / "webtoon/ep003/panel_prompts.yaml"
    payload = panel_prompts.read_text(encoding="utf-8").replace("prompt_schema_version: 2", "prompt_schema_version: 1", 1)
    panel_prompts.write_text(payload, encoding="utf-8")
    errors = CONTRACTS.validate_episode_contracts(project_copy, "ep003", strict=True)
    assert any("strict mode requires prompt_schema_version 2" in error for error in errors)


def test_manifest_and_queue_are_hardened_for_ep003() -> None:
    manifest = json.loads((PROJECT_ROOT / "webtoon/ep003/generated_fal_live_manifest_ep003.json").read_text(encoding="utf-8"))
    queue = CONTRACTS.load_yaml(PROJECT_ROOT / "webtoon/ep003/render_queue.yaml")
    assert manifest["contract_versions"] == queue["contract_versions"]
    assert manifest["prompt_schema_version"] == 2
    assert queue["candidate_policy"]["selection_required"] is True

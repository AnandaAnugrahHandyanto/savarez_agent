from __future__ import annotations

from tests.orbi_romance_contract_helpers import PROJECT_ROOT, load_contracts_module, load_yaml

CONTRACTS = load_contracts_module("orbi_romance_version_contracts")


def test_strict_mode_requires_v2() -> None:
    errors = CONTRACTS.validate_episode_contracts(PROJECT_ROOT, "ep003", strict=True)
    assert errors == []


def test_all_romance_episodes_other_than_ep003_remain_v1() -> None:
    for episode in ("ep001", "ep002", "ep004", "ep005"):
        panel_data = load_yaml(PROJECT_ROOT / f"webtoon/{episode}/panel_prompts.yaml")
        assert panel_data["prompt_schema_version"] == 1


def test_ep003_v2_no_longer_carries_legacy_prompt_field() -> None:
    panel_data = load_yaml(PROJECT_ROOT / "webtoon/ep003/panel_prompts.yaml")
    assert all("prompt" not in panel for panel in panel_data["panels"])

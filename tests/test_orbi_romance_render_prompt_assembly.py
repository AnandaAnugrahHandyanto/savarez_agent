from __future__ import annotations

from tests.orbi_romance_contract_helpers import PROJECT_ROOT, load_contracts_module

CONTRACTS = load_contracts_module("orbi_romance_prompt_contracts")


def test_build_prompt_parts_exposes_structured_sections() -> None:
    bundle = CONTRACTS.load_episode_bundle(PROJECT_ROOT, "ep003")
    panel = bundle["panel_data"]["panels"][1]
    parts = CONTRACTS.build_prompt_parts(bundle["panel_data"], panel, bundle["continuity"])
    assert set(parts) == {"style", "shot_design", "acting", "blocking", "continuity", "lettering", "negative"}


def test_flattened_prompt_avoids_storyboard_wording() -> None:
    bundle = CONTRACTS.load_episode_bundle(PROJECT_ROOT, "ep003")
    for panel in bundle["panel_data"]["panels"]:
        prompt = CONTRACTS.flatten_prompt_parts(
            CONTRACTS.build_prompt_parts(bundle["panel_data"], panel, bundle["continuity"])
        )
        normalized = CONTRACTS.normalize_text(prompt)
        assert "storyboard" not in normalized
        assert "shot list" not in normalized
        assert "placeholder composition" not in normalized

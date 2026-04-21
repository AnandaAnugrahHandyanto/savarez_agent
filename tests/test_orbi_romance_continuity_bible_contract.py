from __future__ import annotations

from pathlib import Path

from tests.orbi_romance_contract_helpers import PROJECT_ROOT, load_contracts_module, load_yaml

CONTRACTS = load_contracts_module("orbi_romance_continuity_contracts")
CONTINUITY_PATH = PROJECT_ROOT / "webtoon/continuity_bible.yaml"


def test_continuity_bible_has_required_top_level_sections() -> None:
    continuity = load_yaml(CONTINUITY_PATH)
    assert {
        "contract_version",
        "series_id",
        "characters",
        "outfit_states",
        "location_states",
        "scene_links",
        "reference_priority",
        "drift_policy",
    } <= set(continuity)


def test_continuity_bible_validates_without_cross_reference_failures() -> None:
    continuity = load_yaml(CONTINUITY_PATH)
    errors: list[str] = []
    CONTRACTS.validate_schema(
        continuity,
        CONTRACTS.load_yaml(PROJECT_ROOT / "webtoon/contracts/continuity_bible.schema.yaml"),
        "continuity_bible.schema",
        errors,
    )
    CONTRACTS.validate_continuity_bible(continuity, errors)
    assert errors == []


def test_shot_spec_visible_characters_exist_in_continuity_bible() -> None:
    continuity = load_yaml(CONTINUITY_PATH)
    panel_data = load_yaml(PROJECT_ROOT / "webtoon/ep003/panel_prompts.yaml")
    characters = set(continuity["characters"])
    for panel in panel_data["panels"]:
        assert set(panel["visible_characters"]) <= characters

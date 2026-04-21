from __future__ import annotations

from tests.orbi_romance_contract_helpers import PROJECT_ROOT, load_contracts_module, load_yaml

CONTRACTS = load_contracts_module("orbi_romance_shot_contracts")


def test_ep003_shot_spec_uses_v2_and_continuity_ref() -> None:
    panel_data = load_yaml(PROJECT_ROOT / "webtoon/ep003/panel_prompts.yaml")
    assert panel_data["prompt_schema_version"] == 2
    assert panel_data["continuity_bible_ref"].endswith("/webtoon/continuity_bible.yaml")


def test_each_visible_character_has_gesture_micro_expression_and_outfit_state() -> None:
    panel_data = load_yaml(PROJECT_ROOT / "webtoon/ep003/panel_prompts.yaml")
    for panel in panel_data["panels"]:
        for character in panel["visible_characters"]:
            assert panel["gesture"][character]
            assert panel["micro_expression"][character]
            assert panel["continuity_refs"]["outfit_states"][character]


def test_no_banned_storyboard_wording_in_authored_fields_or_derived_prompt() -> None:
    bundle = CONTRACTS.load_episode_bundle(PROJECT_ROOT, "ep003")
    panel_data = bundle["panel_data"]
    continuity = bundle["continuity"]
    for panel in panel_data["panels"]:
        authored_strings = CONTRACTS.collect_strings(panel) + CONTRACTS.collect_strings(panel_data["style_anchor"])
        errors: list[str] = []
        CONTRACTS.ensure_no_banned_terms(authored_strings, panel["panel_id"], errors)
        prompt = CONTRACTS.flatten_prompt_parts(CONTRACTS.build_prompt_parts(panel_data, panel, continuity))
        CONTRACTS.ensure_no_banned_terms([prompt], f"{panel['panel_id']}:prompt", errors)
        assert errors == []

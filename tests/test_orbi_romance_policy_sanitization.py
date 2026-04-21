from __future__ import annotations

from tests.orbi_romance_contract_helpers import load_contracts_module

CONTRACTS = load_contracts_module("orbi_romance_sanitization_contracts")


def test_sanitizer_keeps_safe_visual_substitutions() -> None:
    prompt = "약대 입결표와 장학 조건, 단톡방 메시지를 보는 강시윤"
    sanitized = CONTRACTS.sanitize_prompt_for_policy(prompt)
    normalized = CONTRACTS.normalize_text(sanitized)
    assert "abstract admissions chart" in normalized
    assert "scholarship-board blocks" in normalized
    assert "unreadable study-app ui" in normalized


def test_sanitizer_removes_named_character_specificity() -> None:
    prompt = "강시윤과 윤서하가 계약학과 건물 앞에서 마주 본다"
    sanitized = CONTRACTS.sanitize_prompt_for_policy(prompt)
    normalized = CONTRACTS.normalize_text(sanitized)
    assert "강시윤" not in sanitized
    assert "윤서하" not in sanitized
    assert "department-building shapes" in normalized

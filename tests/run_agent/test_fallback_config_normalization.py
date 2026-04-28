from run_agent import _normalize_fallback_chain_config


def test_normalizes_compact_provider_model_fallback_string():
    assert _normalize_fallback_chain_config(
        ["google-gemini-cli:gemini-3-flash-preview"]
    ) == [
        {"provider": "google-gemini-cli", "model": "gemini-3-flash-preview"}
    ]


def test_normalizes_dict_and_preserves_extra_fields():
    assert _normalize_fallback_chain_config([
        {"provider": " openrouter ", "model": " google/gemini-3-flash-preview ", "key_env": "OPENROUTER_API_KEY"}
    ]) == [
        {"provider": "openrouter", "model": "google/gemini-3-flash-preview", "key_env": "OPENROUTER_API_KEY"}
    ]


def test_ignores_invalid_fallback_entries():
    assert _normalize_fallback_chain_config(["missing-model", {}, None, {"provider": "x"}]) == []

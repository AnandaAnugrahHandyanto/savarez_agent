"""Regression tests for named custom providers in /model picker.

Root cause: list_authenticated_providers() only surfaced the singular
custom_providers[].model field and ignored the optional custom_providers[].models
mapping, so gateway /model menus showed only one model even when the config
explicitly declared multiple models.
"""

from hermes_cli.model_switch import list_authenticated_providers


def test_custom_provider_picker_merges_default_model_and_models_map():
    """Custom provider entries should surface all configured models in picker data."""
    providers = list_authenticated_providers(
        current_provider="custom:local-(127.0.0.1:8317)",
        custom_providers=[
            {
                "name": "Local (127.0.0.1:8317)",
                "base_url": "http://127.0.0.1:8317/v1",
                "model": "gpt-5.4",
                "models": {
                    "gpt-5.4": {},
                    "gpt-5.3-codex": {},
                },
            }
        ],
        max_models=10,
    )

    local = next((p for p in providers if p["name"] == "Local (127.0.0.1:8317)"), None)
    assert local is not None
    assert local["models"] == ["gpt-5.4", "gpt-5.3-codex"]
    assert local["total_models"] == 2
    assert local["is_current"] is True


def test_custom_provider_picker_avoids_duplicate_default_model_when_also_in_models_map():
    """Default custom provider model should not be duplicated when already in models map."""
    providers = list_authenticated_providers(
        current_provider="openrouter",
        custom_providers=[
            {
                "name": "Local (127.0.0.1:8317)",
                "base_url": "http://127.0.0.1:8317/v1",
                "model": "gpt-5.4",
                "models": {
                    "gpt-5.4": {},
                    "gpt-5.3-codex": {},
                    "gpt-5.4-mini": {},
                },
            }
        ],
        max_models=2,
    )

    local = next((p for p in providers if p["name"] == "Local (127.0.0.1:8317)"), None)
    assert local is not None
    assert local["models"] == ["gpt-5.4", "gpt-5.3-codex"]
    assert local["total_models"] == 3


def test_custom_provider_picker_supports_models_map_without_default_model():
    """Named custom providers should still expose configured models when only models map is present."""
    providers = list_authenticated_providers(
        current_provider="openrouter",
        custom_providers=[
            {
                "name": "Local (127.0.0.1:8317)",
                "base_url": "http://127.0.0.1:8317/v1",
                "models": {
                    "gpt-5.3-codex": {},
                    "gpt-5.4": {},
                },
            }
        ],
        max_models=10,
    )

    local = next((p for p in providers if p["name"] == "Local (127.0.0.1:8317)"), None)
    assert local is not None
    assert local["models"] == ["gpt-5.3-codex", "gpt-5.4"]
    assert local["total_models"] == 2

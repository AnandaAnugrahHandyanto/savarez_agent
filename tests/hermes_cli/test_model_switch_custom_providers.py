"""Regression tests for /model support of config.yaml custom_providers.

The terminal `hermes model` flow already exposes `custom_providers`, but the
shared slash-command pipeline (`/model` in CLI/gateway/Telegram) historically
only looked at `providers:`.
"""

import hermes_cli.providers as providers_mod
from hermes_cli.model_switch import list_authenticated_providers, switch_model
from hermes_cli.providers import resolve_provider_full


_MOCK_VALIDATION = {
    "accepted": True,
    "persist": True,
    "recognized": True,
    "message": None,
}


def test_list_authenticated_providers_includes_custom_providers(monkeypatch):
    """No-args /model menus should include saved custom_providers entries."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})

    providers = list_authenticated_providers(
        current_provider="openai-codex",
        user_providers={},
        custom_providers=[
            {
                "name": "Local (127.0.0.1:4141)",
                "base_url": "http://127.0.0.1:4141/v1",
                "model": "rotator-openrouter-coding",
            }
        ],
        max_models=50,
    )

    assert any(
        p["slug"] == "custom:local-(127.0.0.1:4141)"
        and p["name"] == "Local (127.0.0.1:4141)"
        and p["models"] == ["rotator-openrouter-coding"]
        and p["api_url"] == "http://127.0.0.1:4141/v1"
        for p in providers
    )


def test_resolve_provider_full_finds_named_custom_provider():
    """Explicit /model --provider should resolve saved custom_providers entries."""
    resolved = resolve_provider_full(
        "custom:local-(127.0.0.1:4141)",
        user_providers={},
        custom_providers=[
            {
                "name": "Local (127.0.0.1:4141)",
                "base_url": "http://127.0.0.1:4141/v1",
            }
        ],
    )

    assert resolved is not None
    assert resolved.id == "custom:local-(127.0.0.1:4141)"
    assert resolved.name == "Local (127.0.0.1:4141)"
    assert resolved.base_url == "http://127.0.0.1:4141/v1"
    assert resolved.source == "user-config"


def test_switch_model_accepts_explicit_named_custom_provider(monkeypatch):
    """Shared /model switch pipeline should accept --provider for custom_providers."""
    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda requested: {
            "api_key": "no-key-required",
            "base_url": "http://127.0.0.1:4141/v1",
            "api_mode": "chat_completions",
        },
    )
    monkeypatch.setattr("hermes_cli.models.validate_requested_model", lambda *a, **k: _MOCK_VALIDATION)
    monkeypatch.setattr("hermes_cli.model_switch.get_model_info", lambda *a, **k: None)
    monkeypatch.setattr("hermes_cli.model_switch.get_model_capabilities", lambda *a, **k: None)

    result = switch_model(
        raw_input="rotator-openrouter-coding",
        current_provider="openai-codex",
        current_model="gpt-5.4",
        current_base_url="https://chatgpt.com/backend-api/codex",
        current_api_key="",
        explicit_provider="custom:local-(127.0.0.1:4141)",
        user_providers={},
        custom_providers=[
            {
                "name": "Local (127.0.0.1:4141)",
                "base_url": "http://127.0.0.1:4141/v1",
                "model": "rotator-openrouter-coding",
            }
        ],
    )

    assert result.success is True
    assert result.target_provider == "custom:local-(127.0.0.1:4141)"
    assert result.provider_label == "Local (127.0.0.1:4141)"
    assert result.new_model == "rotator-openrouter-coding"
    assert result.base_url == "http://127.0.0.1:4141/v1"
    assert result.api_key == "no-key-required"


def test_list_authenticated_providers_groups_same_endpoint(monkeypatch):
    """Multiple custom_providers entries sharing a base_url must be returned
    as a single provider group with all their models merged."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})

    providers = list_authenticated_providers(
        current_provider="custom",
        current_base_url="http://localhost:11434/v1",
        user_providers={},
        custom_providers=[
            {"name": "Ollama — MiniMax M2.7", "base_url": "http://localhost:11434/v1",
             "api_key": "key123", "model": "minimax-m2.7:cloud"},
            {"name": "Ollama — GLM 5.1",      "base_url": "http://localhost:11434/v1",
             "api_key": "key123", "model": "glm-5.1:cloud"},
            {"name": "Ollama — Qwen 3.5",     "base_url": "http://localhost:11434/v1",
             "api_key": "key123", "model": "qwen3.5:cloud"},
        ],
        max_models=50,
    )

    # All three entries share the same endpoint → exactly one group
    custom_groups = [p for p in providers if p.get("is_user_defined")]
    assert len(custom_groups) == 1, (
        f"Expected 1 group for shared endpoint, got {len(custom_groups)}: "
        + str([p["slug"] for p in custom_groups])
    )
    group = custom_groups[0]
    assert set(group["models"]) == {"minimax-m2.7:cloud", "glm-5.1:cloud", "qwen3.5:cloud"}
    assert group["total_models"] == 3


def test_list_authenticated_providers_current_endpoint_slug_and_is_current(monkeypatch):
    """When current_base_url matches a custom_providers entry, the group slug
    must equal current_provider and is_current must be True."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})

    providers = list_authenticated_providers(
        current_provider="custom",
        current_base_url="http://localhost:11434/v1",
        user_providers={},
        custom_providers=[
            {"name": "Ollama — GLM 5.1", "base_url": "http://localhost:11434/v1",
             "api_key": "key123", "model": "glm-5.1:cloud"},
        ],
        max_models=50,
    )

    matches = [p for p in providers if p.get("is_user_defined")]
    assert len(matches) == 1
    group = matches[0]
    assert group["slug"] == "custom", (
        f"Slug should equal current_provider ('custom'), got '{group['slug']}'"
    )
    assert group["is_current"] is True, "is_current should be True for active endpoint"


def test_list_authenticated_providers_max_models_cap_after_merge(monkeypatch):
    """After merging two custom_providers entries into one group, the models
    list must not exceed max_models, while total_models reflects the full count."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})

    entries = [
        {"name": f"Ollama — Model {i}", "base_url": "http://localhost:11434/v1",
         "api_key": "k", "model": f"model-{i}:cloud"}
        for i in range(6)
    ]
    providers = list_authenticated_providers(
        current_provider="custom",
        current_base_url="http://localhost:11434/v1",
        user_providers={},
        custom_providers=entries,
        max_models=4,
    )

    groups = [p for p in providers if p.get("is_user_defined")]
    assert len(groups) == 1
    group = groups[0]
    assert len(group["models"]) <= 4, "models list must be capped at max_models"
    assert group["total_models"] == 6, "total_models must reflect the full count"

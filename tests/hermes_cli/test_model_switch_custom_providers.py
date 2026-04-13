"""Regression tests for /model support of config.yaml custom_providers.

The terminal `hermes model` flow already exposes `custom_providers`, but the
shared slash-command pipeline (`/model` in CLI/gateway/Telegram) historically
only looked at `providers:`.
"""

import hermes_cli.providers as providers_mod
from hermes_cli.model_switch import list_authenticated_providers, switch_model
from hermes_cli.models import provider_model_ids
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


def test_list_authenticated_providers_prefers_custom_provider_model_mapping(monkeypatch):
    """Picker should prefer custom_providers[].models keys and count them correctly."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})
    monkeypatch.setattr("hermes_cli.models.fetch_api_models", lambda *a, **k: [])

    providers = list_authenticated_providers(
        current_provider="openai-codex",
        user_providers={},
        custom_providers=[
            {
                "name": "My Router",
                "base_url": "https://router.example.com/v1",
                "model": "fallback-model",
                "models": {
                    "model-alpha": {"context_length": 32000},
                    "model-beta": {},
                },
            }
        ],
        max_models=50,
    )

    provider = next(p for p in providers if p["slug"] == "custom:my-router")
    assert provider["models"] == ["model-alpha", "model-beta"]
    assert provider["total_models"] == 2


def test_list_authenticated_providers_probes_named_custom_provider_and_dedupes(monkeypatch):
    """Without configured models, picker should probe /models and de-duplicate results."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})

    calls = []

    def _fake_fetch(api_key, base_url, timeout=0.0):
        calls.append((api_key, base_url, timeout))
        return ["live-a", "live-a", "live-b"]

    monkeypatch.setattr("hermes_cli.models.fetch_api_models", _fake_fetch)

    providers = list_authenticated_providers(
        current_provider="openai-codex",
        user_providers={},
        custom_providers=[
            {
                "name": "Probe Me",
                "base_url": "https://probe.example.com/v1",
                "api_key": "sk-probe",
                "model": "fallback-model",
            }
        ],
        max_models=1,
    )

    provider = next(p for p in providers if p["slug"] == "custom:probe-me")
    assert provider["models"] == ["live-a"]
    assert provider["total_models"] == 2
    assert calls == [("sk-probe", "https://probe.example.com/v1", 1.5)]


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


def test_provider_model_ids_supports_named_custom_provider_from_config(monkeypatch):
    """CLI picker model stage should discover models for custom:<slug> providers."""
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {
            "custom_providers": [
                {
                    "name": "Named Endpoint",
                    "base_url": "https://named.example.com/v1",
                    "models": {
                        "mapped-a": {},
                        "mapped-b": {},
                    },
                    "model": "fallback-model",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "hermes_cli.models.fetch_api_models",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not probe when models mapping exists")),
    )

    assert provider_model_ids("custom:named-endpoint") == ["mapped-a", "mapped-b"]


def test_list_authenticated_providers_skips_custom_model_probe_when_max_models_zero(monkeypatch):
    """Slug-only discovery should not probe custom endpoints for model metadata."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})
    monkeypatch.setattr(
        "hermes_cli.models.fetch_api_models",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not probe when max_models=0")),
    )

    providers = list_authenticated_providers(
        current_provider="openai-codex",
        user_providers={},
        custom_providers=[
            {
                "name": "Silent Endpoint",
                "base_url": "https://silent.example.com/v1",
                "model": "saved-model",
            }
        ],
        max_models=0,
    )

    provider = next(p for p in providers if p["slug"] == "custom:silent-endpoint")
    assert provider["models"] == []
    assert provider["total_models"] == 0


def test_provider_model_ids_named_custom_provider_falls_back_to_saved_model(monkeypatch):
    """Named custom providers should fall back to entry.model when probing is empty."""
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {
            "custom_providers": [
                {
                    "name": "Fallback Endpoint",
                    "base_url": "https://fallback.example.com/v1",
                    "api_key": "sk-fallback",
                    "model": "saved-model",
                }
            ]
        },
    )

    calls = []

    def _fake_fetch(api_key, base_url, timeout=0.0):
        calls.append((api_key, base_url, timeout))
        return []

    monkeypatch.setattr("hermes_cli.models.fetch_api_models", _fake_fetch)

    assert provider_model_ids("custom:fallback-endpoint") == ["saved-model"]
    assert calls == [("sk-fallback", "https://fallback.example.com/v1", 1.5)]


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

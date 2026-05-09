"""Bare ``--provider ollama`` resolves to the local Ollama daemon.

Regression for #21524: without a user-defined ``custom_providers`` entry
named ``ollama``, ``resolve_runtime_provider(requested='ollama')`` used to
fall through to the OpenRouter path, surfacing
``Provider resolver returned an empty API key`` even on a fully local setup.
"""
import pytest


@pytest.fixture(autouse=True)
def _empty_config(monkeypatch):
    """Force load_config() to return an empty dict so no user
    custom_providers entry can satisfy the resolver."""
    from hermes_cli import runtime_provider as rp
    monkeypatch.setattr(rp, "load_config", lambda: {})


def _clear_ollama_env(monkeypatch):
    for var in ("OLLAMA_BASE_URL", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_bare_ollama_default_resolves_to_localhost(monkeypatch):
    _clear_ollama_env(monkeypatch)
    from hermes_cli.runtime_provider import _resolve_named_custom_runtime

    result = _resolve_named_custom_runtime(requested_provider="ollama")

    assert result is not None
    assert result["provider"] == "custom"
    assert result["base_url"] == "http://localhost:11434/v1"
    assert result["api_key"] == "no-key-required"
    assert result["source"] == "ollama-default-localhost"
    assert result["api_mode"] == "chat_completions"


def test_bare_ollama_honors_OLLAMA_BASE_URL_env(monkeypatch):
    _clear_ollama_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://10.0.0.5:11434/v1")
    from hermes_cli.runtime_provider import _resolve_named_custom_runtime

    result = _resolve_named_custom_runtime(requested_provider="ollama")

    assert result is not None
    assert result["base_url"] == "http://10.0.0.5:11434/v1"


def test_bare_ollama_honors_explicit_base_url(monkeypatch):
    _clear_ollama_env(monkeypatch)
    from hermes_cli.runtime_provider import _resolve_named_custom_runtime

    result = _resolve_named_custom_runtime(
        requested_provider="ollama",
        explicit_base_url="http://192.168.1.10:11434/v1",
    )

    assert result is not None
    assert result["base_url"] == "http://192.168.1.10:11434/v1"


def test_bare_ollama_does_not_overwrite_named_custom_provider(monkeypatch):
    """When a user configured a custom_providers entry called ``ollama``
    pointing somewhere non-default, that entry must win."""
    from hermes_cli import runtime_provider as rp

    monkeypatch.setattr(rp, "load_config", lambda: {
        "providers": {
            "ollama": {
                "name": "ollama",
                "base_url": "http://my-rig.example:11434/v1",
                "api": "http://my-rig.example:11434/v1",
                "key_env": "",
                "default_model": "qwen3:8b",
            }
        }
    })
    _clear_ollama_env(monkeypatch)

    result = rp._resolve_named_custom_runtime(requested_provider="ollama")

    assert result is not None
    assert result["base_url"] == "http://my-rig.example:11434/v1"
    assert result.get("source") != "ollama-default-localhost"


def test_other_unknown_provider_still_returns_none(monkeypatch):
    """The new ollama branch must not affect other unknown provider names."""
    _clear_ollama_env(monkeypatch)
    from hermes_cli.runtime_provider import _resolve_named_custom_runtime

    assert _resolve_named_custom_runtime(requested_provider="my-unconfigured-thing") is None

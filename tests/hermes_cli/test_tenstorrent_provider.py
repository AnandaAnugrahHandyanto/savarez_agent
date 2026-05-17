"""Tests for the Tenstorrent AI provider plugin."""

from hermes_cli.models import (
    list_available_providers,
    normalize_provider,
    parse_model_input,
    provider_model_ids,
)
from providers import get_provider_profile


def test_tenstorrent_provider_profile():
    profile = get_provider_profile("tenstorrent")

    assert profile is not None
    assert profile.display_name == "Tenstorrent AI"
    assert profile.base_url == "https://console.tenstorrent.com/v1"
    assert profile.env_vars == ("TENSTORRENT_API_KEY", "TENSTORRENT_BASE_URL")
    assert profile.default_aux_model == "Qwen/Qwen3-32B"
    assert profile.fallback_models == (
        "deepseek-ai/DeepSeek-R1-0528",
        "Qwen/Qwen3-32B",
        "Qwen/Qwen3-VL-32B-Instruct",
    )


def test_tenstorrent_aliases_resolve_in_models_module():
    assert normalize_provider("tt") == "tenstorrent"
    assert normalize_provider("tt-ai") == "tenstorrent"
    assert normalize_provider("tenstorrent-ai") == "tenstorrent"


def test_tenstorrent_parse_model_input_supports_alias_prefix():
    provider, model = parse_model_input("tt:Qwen/Qwen3-32B", "openrouter")

    assert provider == "tenstorrent"
    assert model == "Qwen/Qwen3-32B"


def test_tenstorrent_appears_in_provider_picker_catalog():
    providers = {p["id"]: p for p in list_available_providers()}

    assert "tenstorrent" in providers
    assert providers["tenstorrent"]["label"] == "Tenstorrent AI"
    assert "tt" in providers["tenstorrent"]["aliases"]


def test_tenstorrent_static_model_fallbacks(monkeypatch):
    monkeypatch.delenv("TENSTORRENT_API_KEY", raising=False)
    assert provider_model_ids("tenstorrent") == [
        "deepseek-ai/DeepSeek-R1-0528",
        "Qwen/Qwen3-32B",
        "Qwen/Qwen3-VL-32B-Instruct",
    ]


def test_tenstorrent_live_models_use_custom_base_url(monkeypatch):
    monkeypatch.setenv("TENSTORRENT_API_KEY", "tt-key")
    monkeypatch.setenv("TENSTORRENT_BASE_URL", "https://custom.tenstorrent.example/v1")
    profile = get_provider_profile("tenstorrent")
    seen = {}

    def fake_fetch_models(*, api_key=None, base_url=None, timeout=8.0):
        seen["api_key"] = api_key
        seen["base_url"] = base_url
        return ["custom/model"]

    monkeypatch.setattr(profile, "fetch_models", fake_fetch_models)

    assert provider_model_ids("tenstorrent") == ["custom/model"]
    assert seen == {
        "api_key": "tt-key",
        "base_url": "https://custom.tenstorrent.example/v1",
    }

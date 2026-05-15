"""Smoke tests for the Luma video gen plugin — load & register surface."""

from __future__ import annotations

import pytest

from agent import video_gen_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    video_gen_registry._reset_for_tests()
    yield
    video_gen_registry._reset_for_tests()


def test_luma_provider_registers():
    from plugins.video_gen.luma import LumaProvider

    provider = LumaProvider()
    video_gen_registry.register_provider(provider)

    assert video_gen_registry.get_provider("luma") is provider
    assert provider.display_name == "Luma Dream Machine"
    assert provider.default_model() == "dream-machine-1.6"


def test_luma_capabilities_text_and_image():
    from plugins.video_gen.luma import LumaProvider

    caps = LumaProvider().capabilities()
    assert caps["modalities"] == ["text", "image"]
    assert "16:9" in caps["aspect_ratios"]
    assert "9:16" in caps["aspect_ratios"]
    assert caps["min_duration"] == 5
    assert caps["max_duration"] == 10


def test_luma_models():
    from plugins.video_gen.luma import LumaProvider

    models = LumaProvider().list_models()
    assert len(models) == 2
    model_ids = {m["id"] for m in models}
    assert "dream-machine-1.6" in model_ids
    assert "photon-1" in model_ids


def test_luma_unavailable_without_key(monkeypatch):
    from plugins.video_gen.luma import LumaProvider

    monkeypatch.delenv("LUMA_API_KEY", raising=False)
    assert LumaProvider().is_available() is False


def test_luma_generate_requires_key(monkeypatch):
    from plugins.video_gen.luma import LumaProvider

    monkeypatch.delenv("LUMA_API_KEY", raising=False)
    result = LumaProvider().generate("a beautiful landscape")
    assert result["success"] is False
    assert result["error_type"] == "missing_api_key"


def test_luma_setup_schema():
    from plugins.video_gen.luma import LumaProvider

    schema = LumaProvider().get_setup_schema()
    assert schema["name"] == "Luma Dream Machine"
    assert schema["badge"] == "paid"
    assert schema["env_vars"][0]["key"] == "LUMA_API_KEY"

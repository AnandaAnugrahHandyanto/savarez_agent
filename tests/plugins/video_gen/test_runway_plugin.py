"""Smoke tests for the Runway video gen plugin — load & register surface."""

from __future__ import annotations

import pytest

from agent import video_gen_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    video_gen_registry._reset_for_tests()
    yield
    video_gen_registry._reset_for_tests()


def test_runway_provider_registers():
    from plugins.video_gen.runway import RunwayProvider

    provider = RunwayProvider()
    video_gen_registry.register_provider(provider)

    assert video_gen_registry.get_provider("runway") is provider
    assert provider.display_name == "RunwayML"
    assert provider.default_model() == "gen3a-turbo"


def test_runway_capabilities_text_and_image():
    """Runway supports text-to-video and image-to-video."""
    from plugins.video_gen.runway import RunwayProvider

    caps = RunwayProvider().capabilities()
    assert caps["modalities"] == ["text", "image"]
    assert "16:9" in caps["aspect_ratios"]
    assert "9:16" in caps["aspect_ratios"]
    assert caps["min_duration"] == 5
    assert caps["max_duration"] == 10
    assert caps["supports_audio"] is False
    assert caps["supports_negative_prompt"] is False
    assert caps["max_reference_images"] == 0


def test_runway_models():
    """Runway ships two model families."""
    from plugins.video_gen.runway import RunwayProvider

    models = RunwayProvider().list_models()
    assert len(models) == 2
    model_ids = {m["id"] for m in models}
    assert "gen3a-turbo" in model_ids
    assert "gen3a-standard" in model_ids


def test_runway_unavailable_without_key(monkeypatch):
    from plugins.video_gen.runway import RunwayProvider

    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)
    assert RunwayProvider().is_available() is False


def test_runway_generate_requires_key(monkeypatch):
    from plugins.video_gen.runway import RunwayProvider

    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)
    result = RunwayProvider().generate("a cinematic sunset")
    assert result["success"] is False
    assert result["error_type"] == "missing_api_key"


def test_runway_no_operation_kwarg():
    """The ABC's generate() signature no longer accepts 'operation'.
    Passing it through **kwargs should be ignored (forward-compat)."""
    from plugins.video_gen.runway import RunwayProvider

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)

    # Will fail with missing_api_key, but should NOT fail with TypeError.
    result = RunwayProvider().generate("x", operation="generate")
    assert result["success"] is False
    assert result["error_type"] == "missing_api_key"


def test_runway_resolve_model_precedence(monkeypatch):
    """Test model resolution precedence: arg > env > config > default."""
    from plugins.video_gen.runway import RunwayProvider, RUNWAY_MODELS

    provider = RunwayProvider()

    # 1. Direct arg wins
    assert provider._resolve_model("gen3a-standard") == "gen3a-standard"

    # 2. Env var wins over default
    monkeypatch.setenv("RUNWAY_VIDEO_MODEL", "gen3a-standard")
    assert provider._resolve_model(None) == "gen3a-standard"
    monkeypatch.delenv("RUNWAY_VIDEO_MODEL", raising=False)

    # 3. Invalid model falls back to default
    assert provider._resolve_model("nonexistent-model") == "gen3a-turbo"


def test_runway_setup_schema():
    """Setup schema should advertise RUNWAY_API_KEY requirement."""
    from plugins.video_gen.runway import RunwayProvider

    schema = RunwayProvider().get_setup_schema()
    assert schema["name"] == "RunwayML"
    assert schema["badge"] == "paid"
    assert len(schema["env_vars"]) == 1
    assert schema["env_vars"][0]["key"] == "RUNWAY_API_KEY"

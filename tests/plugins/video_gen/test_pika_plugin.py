"""Smoke tests for the Pika video gen plugin — load & register surface."""

from __future__ import annotations

import pytest

from agent import video_gen_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    video_gen_registry._reset_for_tests()
    yield
    video_gen_registry._reset_for_tests()


def test_pika_provider_registers():
    from plugins.video_gen.pika import PikaProvider

    provider = PikaProvider()
    video_gen_registry.register_provider(provider)

    assert video_gen_registry.get_provider("pika") is provider
    assert provider.display_name == "Pika Labs"
    assert provider.default_model() == "pika-2.0"


def test_pika_capabilities():
    from plugins.video_gen.pika import PikaProvider

    caps = PikaProvider().capabilities()
    assert caps["modalities"] == ["text", "image"]
    assert caps["min_duration"] == 3
    assert caps["max_duration"] == 15
    assert caps["supports_audio"] is True
    assert caps["supports_negative_prompt"] is True


def test_pika_models():
    from plugins.video_gen.pika import PikaProvider

    models = PikaProvider().list_models()
    assert len(models) == 2
    model_ids = {m["id"] for m in models}
    assert "pika-2.0" in model_ids
    assert "pika-1.5" in model_ids


def test_pika_unavailable_without_key(monkeypatch):
    from plugins.video_gen.pika import PikaProvider

    monkeypatch.delenv("PIKA_API_KEY", raising=False)
    assert PikaProvider().is_available() is False


def test_pika_generate_requires_key(monkeypatch):
    from plugins.video_gen.pika import PikaProvider

    monkeypatch.delenv("PIKA_API_KEY", raising=False)
    result = PikaProvider().generate("an animated character running")
    assert result["success"] is False
    assert result["error_type"] == "missing_api_key"


def test_pika_setup_schema():
    from plugins.video_gen.pika import PikaProvider

    schema = PikaProvider().get_setup_schema()
    assert schema["name"] == "Pika Labs"
    assert schema["badge"] == "paid"
    assert schema["env_vars"][0]["key"] == "PIKA_API_KEY"

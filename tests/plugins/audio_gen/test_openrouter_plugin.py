"""Tests for the OpenRouter audio gen plugin — register, payload, response handling."""

from __future__ import annotations

import base64
import json

import pytest

from agent import audio_gen_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    audio_gen_registry._reset_for_tests()
    yield
    audio_gen_registry._reset_for_tests()


@pytest.fixture(autouse=True)
def _stub_models(monkeypatch):
    """Avoid live /models network calls in unit tests."""
    from plugins.audio_gen import openrouter as ora

    models = [
        {
            "id": "google/lyria-3-pro-preview",
            "display": "Lyria 3 Pro",
            "strengths": "Music with vocals",
            "kinds": ["music"],
            "supports_lyrics": True,
        },
        {
            "id": "openai/gpt-audio",
            "display": "GPT-Audio",
            "strengths": "General audio",
            "kinds": ["music", "sfx"],
            "supports_lyrics": False,
        },
    ]
    monkeypatch.setattr(ora, "_fetch_models", lambda: models)
    return models


def _provider(monkeypatch, api_key="sk-or-test"):
    from plugins.audio_gen import openrouter as ora

    monkeypatch.setattr(
        ora, "_resolve_credentials",
        lambda: (api_key, "https://openrouter.ai/api/v1"),
    )
    return ora.OpenRouterAudioGenProvider()


def test_registers_and_basic_surface(monkeypatch):
    from plugins.audio_gen.openrouter import OpenRouterAudioGenProvider, DEFAULT_MODEL

    provider = _provider(monkeypatch)
    audio_gen_registry.register_provider(provider)

    assert audio_gen_registry.get_provider("openrouter") is provider
    assert provider.name == "openrouter"
    assert provider.display_name == "OpenRouter"
    assert provider.default_model() == DEFAULT_MODEL == "google/lyria-3-pro-preview"


def test_is_available_requires_key(monkeypatch):
    assert _provider(monkeypatch, api_key="").is_available() is False
    assert _provider(monkeypatch, api_key="sk-or-x").is_available() is True


def test_setup_schema_declares_openrouter_key(monkeypatch):
    schema = _provider(monkeypatch).get_setup_schema()
    assert schema["name"] == "OpenRouter Audio"
    assert [e["key"] for e in schema["env_vars"]] == ["OPENROUTER_API_KEY"]


def test_capabilities_report_lyrics(monkeypatch):
    caps = _provider(monkeypatch).capabilities()
    assert "music" in caps["kinds"]
    assert caps["supports_lyrics"] is True  # Lyria in catalog
    assert set(caps["formats"]) == {"mp3", "wav"}


def test_generate_requires_key(monkeypatch):
    out = _provider(monkeypatch, api_key="").generate("a jingle")
    assert out["success"] is False
    assert out["error_type"] == "auth_required"


def test_generate_requires_prompt(monkeypatch):
    out = _provider(monkeypatch).generate("   ")
    assert out["success"] is False
    assert out["error_type"] == "missing_prompt"


# ---------------------------------------------------------------------------
# Synchronous chat/completions flow — mock httpx.post + file save
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=self)

    def json(self):
        return self._payload


def test_generate_success_writes_audio(monkeypatch, tmp_path):
    from plugins.audio_gen import openrouter as ora

    provider = _provider(monkeypatch)
    captured: dict = {}
    b64 = base64.b64encode(b"FAKEAUDIOBYTES").decode()

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse({
            "choices": [{"message": {"audio": {"data": b64, "transcript": "la la"}}}],
            "usage": {"cost": 0.02},
        })

    saved = {}

    def _fake_save(data, *, prefix="audio", extension="mp3"):
        saved["data"] = data
        saved["ext"] = extension
        out = tmp_path / f"{prefix}.{extension}"
        out.write_bytes(base64.b64decode(data))
        return out

    monkeypatch.setattr(ora.httpx, "post", _fake_post)
    monkeypatch.setattr(ora, "save_b64_audio", _fake_save)

    out = provider.generate("upbeat lo-fi beat", duration=20, lyrics="hello world", audio_format="mp3")
    assert out["success"] is True
    assert out["provider"] == "openrouter"
    assert out["format"] == "mp3"
    assert out["duration"] == 20
    assert out["transcript"] == "la la"
    assert out["usage"] == {"cost": 0.02}
    # Audio path written and decodes
    assert out["audio"].endswith(".mp3")

    # Payload shape: modalities + audio format + lyrics folded into the message
    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["modalities"] == ["audio"]
    assert captured["json"]["audio"] == {"format": "mp3"}
    assert captured["json"]["model"] == "google/lyria-3-pro-preview"
    msg = captured["json"]["messages"][0]["content"]
    assert "upbeat lo-fi beat" in msg
    assert "hello world" in msg
    assert saved["ext"] == "mp3"


def test_generate_no_audio_in_response_errors(monkeypatch):
    from plugins.audio_gen import openrouter as ora

    provider = _provider(monkeypatch)
    monkeypatch.setattr(
        ora.httpx, "post",
        lambda *a, **k: _FakeResponse({"choices": [{"message": {"content": "no audio here"}}]}),
    )

    out = provider.generate("a song")
    assert out["success"] is False
    assert out["error_type"] == "empty_response"


def test_generate_http_error_surfaces(monkeypatch):
    from plugins.audio_gen import openrouter as ora

    provider = _provider(monkeypatch)
    monkeypatch.setattr(
        ora.httpx, "post",
        lambda *a, **k: _FakeResponse({"error": "rate limited"}, status_code=429),
    )

    out = provider.generate("a song")
    assert out["success"] is False
    assert out["error_type"] == "api_error"


def test_unsupported_format_clamps_to_mp3(monkeypatch):
    from plugins.audio_gen import openrouter as ora

    provider = _provider(monkeypatch)
    captured: dict = {}
    b64 = base64.b64encode(b"x").decode()

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResponse({"choices": [{"message": {"audio": {"data": b64}}}]})

    monkeypatch.setattr(ora.httpx, "post", _fake_post)
    monkeypatch.setattr(ora, "save_b64_audio", lambda data, *, prefix="a", extension="mp3": __import__("pathlib").Path(f"/tmp/x.{extension}"))

    out = provider.generate("a song", audio_format="ogg")
    assert out["success"] is True
    assert captured["json"]["audio"] == {"format": "mp3"}

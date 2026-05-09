#!/usr/bin/env python3
"""Tests for Gemini / Nano Banana image generation provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "NANO_BANANA_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NANO_BANANA_API_KEY", "test-gemini-key")


class TestGeminiImageGenProvider:
    def test_name_and_display(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        provider = GeminiImageGenProvider()
        assert provider.name == "gemini"
        assert provider.display_name == "Gemini / Nano Banana"

    def test_is_available_with_alias_key(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().is_available() is True

    def test_is_available_without_any_key(self, monkeypatch):
        for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "NANO_BANANA_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().is_available() is False

    def test_list_models(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        models = GeminiImageGenProvider().list_models()
        ids = {m["id"] for m in models}
        assert "gemini-2.5-flash-image" in ids
        assert "gemini-3-pro-image-preview" in ids

    def test_default_model(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().default_model() == "gemini-2.5-flash-image"

    def test_get_setup_schema_uses_conventional_google_key(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        schema = GeminiImageGenProvider().get_setup_schema()
        assert schema["name"] == "Gemini / Nano Banana"
        assert schema["env_vars"][0]["key"] == "GEMINI_API_KEY"


class TestGeminiConfig:
    def test_resolve_api_key_prefers_gemini(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini")
        monkeypatch.setenv("GOOGLE_API_KEY", "google")
        monkeypatch.setenv("NANO_BANANA_API_KEY", "banana")
        from plugins.image_gen.gemini import _resolve_api_key

        value, name = _resolve_api_key()
        assert value == "gemini"
        assert name == "GEMINI_API_KEY"

    def test_resolve_api_key_accepts_nano_banana_alias(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("NANO_BANANA_API_KEY", "banana")
        from plugins.image_gen.gemini import _resolve_api_key

        value, name = _resolve_api_key()
        assert value == "banana"
        assert name == "NANO_BANANA_API_KEY"

    def test_env_model_override(self, monkeypatch):
        monkeypatch.setenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
        from plugins.image_gen.gemini import _resolve_model

        model_id, _ = _resolve_model()
        assert model_id == "gemini-3-pro-image-preview"


class TestGeminiGenerate:
    def test_missing_api_key(self, monkeypatch):
        for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "NANO_BANANA_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        from plugins.image_gen.gemini import GeminiImageGenProvider

        result = GeminiImageGenProvider().generate(prompt="test")
        assert result["success"] is False
        assert result["error_type"] == "auth_required"
        assert "NANO_BANANA_API_KEY" in result["error"]

    def test_successful_generation_saves_inline_data(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "done"},
                            {"inlineData": {"mimeType": "image/png", "data": "dGVzdA=="}},
                        ]
                    }
                }
            ]
        }

        with patch("plugins.image_gen.gemini.requests.post", return_value=mock_resp) as mock_post:
            with patch("plugins.image_gen.gemini.save_b64_image", return_value="/tmp/gemini.png"):
                result = GeminiImageGenProvider().generate(prompt="A tiny blue banana", aspect_ratio="square")

        assert result["success"] is True
        assert result["image"] == "/tmp/gemini.png"
        assert result["provider"] == "gemini"
        assert result["model"] == "gemini-2.5-flash-image"
        assert result["text"] == "done"

        _, kwargs = mock_post.call_args
        assert "key=" not in kwargs["url"] if "url" in kwargs else "key=" not in mock_post.call_args.args[0]
        assert kwargs["headers"]["x-goog-api-key"] == "test-gemini-key"
        assert kwargs["json"]["generationConfig"]["imageConfig"]["aspectRatio"] == "1:1"

    def test_api_error_does_not_include_key(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "API key not valid"}}
        mock_resp.text = "API key not valid"

        with patch("plugins.image_gen.gemini.requests.post", return_value=mock_resp):
            result = GeminiImageGenProvider().generate(prompt="test")

        assert result["success"] is False
        assert result["error_type"] == "api_error"
        assert "test-gemini-key" not in result["error"]

    def test_empty_response(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]}

        with patch("plugins.image_gen.gemini.requests.post", return_value=mock_resp):
            result = GeminiImageGenProvider().generate(prompt="test")

        assert result["success"] is False
        assert result["error_type"] == "empty_response"

    def test_register_calls_context(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider, register

        class Ctx:
            def __init__(self):
                self.provider = None

            def register_image_gen_provider(self, provider):
                self.provider = provider

        ctx = Ctx()
        register(ctx)
        assert isinstance(ctx.provider, GeminiImageGenProvider)

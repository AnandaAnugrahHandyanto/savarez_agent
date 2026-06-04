from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _fake_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")


class TestGeminiImageGenProvider:
    def test_name_and_default_model(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        provider = GeminiImageGenProvider()
        assert provider.name == "gemini"
        assert provider.default_model() == "gemini-2.5-flash-image"

    def test_is_available_with_key(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        assert GeminiImageGenProvider().is_available() is True

    def test_is_available_without_key(self, monkeypatch):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with patch("plugins.image_gen.gemini._get_env_value", return_value=None):
            assert GeminiImageGenProvider().is_available() is False

    def test_list_models(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        ids = {model["id"] for model in GeminiImageGenProvider().list_models()}
        assert "gemini-2.5-flash-image" in ids
        assert "gemini-3.1-flash-image-preview" in ids

    def test_setup_schema_prompts_for_gemini_key(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        schema = GeminiImageGenProvider().get_setup_schema()
        assert schema["name"] == "Google Gemini Image"
        assert schema["env_vars"][0]["key"] == "GEMINI_API_KEY"


class TestGeminiGenerate:
    def _mock_success_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "done"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(b"fake-image").decode("ascii"),
                                }
                            },
                        ]
                    }
                }
            ]
        }
        return mock_resp

    def test_successful_text_to_image_payload_and_response(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        with patch("plugins.image_gen.gemini.requests.post", return_value=self._mock_success_response()) as mock_post, \
             patch("plugins.image_gen.gemini.save_b64_image", return_value="/tmp/gemini.png"):
            result = GeminiImageGenProvider().generate("a cinematic product photo", aspect_ratio="landscape")

        assert result["success"] is True
        assert result["image"] == "/tmp/gemini.png"
        assert result["provider"] == "gemini"
        assert result["model"] == "gemini-2.5-flash-image"
        assert result["mode"] == "generate"

        payload = mock_post.call_args.kwargs["json"]
        assert payload["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
        assert payload["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
        assert payload["contents"][0]["parts"] == [{"text": "a cinematic product photo"}]
        assert mock_post.call_args.kwargs["params"] == {"key": "test-gemini-key"}

    def test_input_image_is_sent_as_inline_data(self, tmp_path):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        source = tmp_path / "source.png"
        source.write_bytes(b"source-image")

        with patch("plugins.image_gen.gemini.requests.post", return_value=self._mock_success_response()) as mock_post, \
             patch("plugins.image_gen.gemini.save_b64_image", return_value="/tmp/gemini-edit.png"):
            result = GeminiImageGenProvider().generate(
                "turn this into a clean studio product shot",
                aspect_ratio="square",
                input_image=str(source),
            )

        assert result["success"] is True
        assert result["mode"] == "edit"
        assert result["input_images"] == 1
        parts = mock_post.call_args.kwargs["json"]["contents"][0]["parts"]
        assert parts[0]["text"].startswith("turn this")
        assert parts[1]["inlineData"]["mimeType"] == "image/png"
        assert base64.b64decode(parts[1]["inlineData"]["data"]) == b"source-image"

    def test_invalid_input_image_returns_clear_error(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        result = GeminiImageGenProvider().generate("edit it", input_image="/does/not/exist.png")
        assert result["success"] is False
        assert result["error_type"] == "invalid_image_input"
        assert "input image path does not exist" in result["error"]

    def test_missing_key(self, monkeypatch):
        from plugins.image_gen.gemini import GeminiImageGenProvider

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with patch("plugins.image_gen.gemini._get_env_value", return_value=None):
            result = GeminiImageGenProvider().generate("test")
        assert result["success"] is False
        assert result["error_type"] == "auth_required"


class TestRegistration:
    def test_register(self):
        from plugins.image_gen.gemini import GeminiImageGenProvider, register

        mock_ctx = MagicMock()
        register(mock_ctx)
        mock_ctx.register_image_gen_provider.assert_called_once()
        provider = mock_ctx.register_image_gen_provider.call_args[0][0]
        assert isinstance(provider, GeminiImageGenProvider)
        assert provider.name == "gemini"

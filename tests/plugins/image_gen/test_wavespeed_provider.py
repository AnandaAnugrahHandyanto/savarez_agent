"""Tests for the bundled WaveSpeed image generation provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import plugins.image_gen.wavespeed as wavespeed_plugin


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("WAVESPEED_API_KEY", "ws-test-key")
    return wavespeed_plugin.WaveSpeedImageGenProvider()


class TestMetadata:
    def test_name(self, provider):
        assert provider.name == "wavespeed"

    def test_default_model(self, provider):
        assert provider.default_model() == "wavespeed-ai/flux-2-klein-9b/text-to-image"

    def test_list_models(self, provider):
        ids = [entry["id"] for entry in provider.list_models()]
        assert "wavespeed-ai/flux-2-klein-9b/text-to-image" in ids
        assert "google/nano-banana-pro/text-to-image" in ids

    def test_setup_schema(self, provider):
        schema = provider.get_setup_schema()
        assert schema["name"] == "WaveSpeed"
        assert schema["env_vars"][0]["key"] == "WAVESPEED_API_KEY"


class TestAvailability:
    def test_available_with_key(self, monkeypatch):
        monkeypatch.setenv("WAVESPEED_API_KEY", "ws-key")
        assert wavespeed_plugin.WaveSpeedImageGenProvider().is_available() is True

    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
        assert wavespeed_plugin.WaveSpeedImageGenProvider().is_available() is False


class TestModelResolution:
    def test_default_model(self):
        model_id, _meta = wavespeed_plugin._resolve_model()
        assert model_id == wavespeed_plugin.DEFAULT_MODEL

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv(
            "WAVESPEED_IMAGE_MODEL",
            "google/nano-banana-pro/text-to-image",
        )
        model_id, _meta = wavespeed_plugin._resolve_model()
        assert model_id == "google/nano-banana-pro/text-to-image"


class TestPayloadMapping:
    def test_flux_uses_size_mapping(self):
        payload = wavespeed_plugin._build_payload(
            "wavespeed-ai/flux-2-klein-9b/text-to-image",
            "draw a fox",
            "landscape",
        )
        assert payload["size"] == "1360*768"
        assert payload["enable_sync_mode"] is True
        assert "aspect_ratio" not in payload

    def test_nano_banana_uses_aspect_ratio_mapping(self):
        payload = wavespeed_plugin._build_payload(
            "google/nano-banana-pro/text-to-image",
            "draw a fox",
            "portrait",
        )
        assert payload["aspect_ratio"] == "9:16"
        assert payload["resolution"] == "1k"
        assert payload["output_format"] == "png"


class TestResponseParsing:
    def test_extracts_nested_image_url(self):
        image_ref, error = wavespeed_plugin._extract_image_result(
            {
                "outputs": [
                    {
                        "image": {
                            "url": "https://cdn.wavespeed.ai/nested.png",
                        }
                    }
                ]
            }
        )
        assert image_ref == "https://cdn.wavespeed.ai/nested.png"
        assert error is None

    def test_prediction_result_url_uses_direct_result_field(self):
        result_url = wavespeed_plugin._prediction_result_url(
            {"result_url": "https://api.wavespeed.ai/api/v3/predictions/pred-123/result"}
        )
        assert result_url == "https://api.wavespeed.ai/api/v3/predictions/pred-123/result"


class TestGenerate:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
        result = wavespeed_plugin.WaveSpeedImageGenProvider().generate("test")
        assert result["success"] is False
        assert result["error_type"] == "auth_required"

    def test_empty_prompt(self, provider):
        result = provider.generate("")
        assert result["success"] is False
        assert result["error_type"] == "invalid_argument"

    def test_successful_sync_response(self, provider):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "data": {
                "status": "completed",
                "outputs": ["https://cdn.wavespeed.ai/out.png"],
            }
        }

        with patch("plugins.image_gen.wavespeed.requests.post", return_value=response) as mock_post:
            result = provider.generate("a cat astronaut", aspect_ratio="square")

        assert result["success"] is True
        assert result["image"] == "https://cdn.wavespeed.ai/out.png"
        assert result["provider"] == "wavespeed"
        sent = mock_post.call_args.kwargs["json"]
        assert sent["size"] == "1024*1024"
        assert sent["enable_sync_mode"] is True

    def test_processing_response_polls_until_complete(self, provider):
        post_response = MagicMock()
        post_response.raise_for_status = MagicMock()
        post_response.json.return_value = {
            "data": {
                "id": "pred-123",
                "status": "processing",
                "urls": {
                    "get": "https://api.wavespeed.ai/api/v3/predictions/pred-123/result",
                },
            }
        }

        get_response = MagicMock()
        get_response.raise_for_status = MagicMock()
        get_response.json.return_value = {
            "data": {
                "id": "pred-123",
                "status": "completed",
                "outputs": ["https://cdn.wavespeed.ai/polled.png"],
            }
        }

        with patch("plugins.image_gen.wavespeed.requests.post", return_value=post_response):
            with patch("plugins.image_gen.wavespeed.requests.get", return_value=get_response):
                with patch("plugins.image_gen.wavespeed.time.sleep", lambda *_args, **_kwargs: None):
                    result = provider.generate("a cat astronaut")

        assert result["success"] is True
        assert result["image"] == "https://cdn.wavespeed.ai/polled.png"

    def test_api_error(self, provider):
        import requests as req_lib

        response = MagicMock()
        response.status_code = 401
        response.text = "Unauthorized"
        response.json.return_value = {"message": "bad key"}
        response.raise_for_status.side_effect = req_lib.HTTPError(response=response)

        with patch("plugins.image_gen.wavespeed.requests.post", return_value=response):
            result = provider.generate("test")

        assert result["success"] is False
        assert result["error_type"] == "api_error"
        assert "401" in result["error"]

    def test_timeout(self, provider):
        import requests as req_lib

        with patch("plugins.image_gen.wavespeed.requests.post", side_effect=req_lib.Timeout()):
            result = provider.generate("test")

        assert result["success"] is False
        assert result["error_type"] == "timeout"


class TestRegistration:
    def test_register(self):
        mock_ctx = MagicMock()
        wavespeed_plugin.register(mock_ctx)
        mock_ctx.register_image_gen_provider.assert_called_once()
        provider = mock_ctx.register_image_gen_provider.call_args[0][0]
        assert isinstance(provider, wavespeed_plugin.WaveSpeedImageGenProvider)

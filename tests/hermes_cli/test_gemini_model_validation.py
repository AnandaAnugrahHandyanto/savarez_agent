"""Tests for Gemini model validation via the static provider catalog.

Google AI Studio's native Gemini API does not expose an OpenAI-compatible
``/models`` listing, so ``validate_requested_model()`` must not reject valid
Gemini model switches just because the old probe path is unreachable.
"""

from unittest.mock import patch

import pytest

from hermes_cli.models import validate_requested_model


class TestGeminiModelValidation:
    @pytest.fixture(autouse=True)
    def _isolate_gemini(self):
        probe_payload = {
            "models": None,
            "probed_url": "https://generativelanguage.googleapis.com/v1beta/models",
            "resolved_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "suggested_base_url": None,
            "used_fallback": False,
        }
        with patch("hermes_cli.models.fetch_api_models", return_value=None), \
             patch("hermes_cli.models.probe_api_models", return_value=probe_payload):
            yield

    def test_known_gemini_model_accepted_via_catalog_when_api_probe_unavailable(self):
        result = validate_requested_model("gemini-3.1-pro-preview", "gemini")

        assert result["accepted"] is True
        assert result["persist"] is True
        assert result["recognized"] is True
        assert result["message"] is None

    def test_unknown_gemini_model_warns_but_does_not_block_switch(self):
        result = validate_requested_model("gemini-4-experimental-preview", "gemini")

        assert result["accepted"] is True
        assert result["persist"] is True
        assert result["recognized"] is False
        assert "Google AI Studio" in result["message"]
        assert "does not expose a /models endpoint" in result["message"]

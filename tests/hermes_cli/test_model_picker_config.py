"""Tests for hermes_cli.model_picker_config module."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestOllamaCloudLiveModels:
    """Tests for _ollama_cloud_live_models_with_note function."""

    def test_returns_none_when_no_api_key(self):
        """Should return None when OLLAMA_CLOUD_API_KEY is not set."""
        with patch.dict("os.environ", {}, clear=True):
            from hermes_cli.model_picker_config import (
                _ollama_cloud_live_models_with_note,
            )

            result = _ollama_cloud_live_models_with_note()
            assert result == (None, None)

    def test_returns_none_on_api_failure(self):
        """Should return fallback note on API failure."""
        with patch.dict("os.environ", {"OLLAMA_CLOUD_API_KEY": "test-key"}):
            with patch(
                "urllib.request.urlopen", side_effect=Exception("Network error")
            ):
                from hermes_cli.model_picker_config import (
                    _ollama_cloud_live_models_with_note,
                )

                result = _ollama_cloud_live_models_with_note()
                assert result[0] is None
                assert result[1] == "Fallback local models"

    def test_returns_sorted_models_on_success(self):
        """Should return sorted model list on successful API call."""
        mock_data = {
            "models": [
                {"name": "llama3"},
                {"name": "mistral"},
                {"name": "codellama"},
            ]
        }
        with patch.dict("os.environ", {"OLLAMA_CLOUD_API_KEY": "test-key"}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.return_value.__enter__ = MagicMock(
                    return_value=MagicMock(
                        read=lambda: b'{"models": [{"name": "llama3"}, {"name": "mistral"}]}'
                    )
                )
                mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
                with patch("json.loads", return_value=mock_data):
                    from hermes_cli.model_picker_config import (
                        _ollama_cloud_live_models_with_note,
                    )

                    result = _ollama_cloud_live_models_with_note()
                    assert result[0] == ["codellama", "llama3", "mistral"]
                    assert result[1] == "Live cloud models"


class TestCodexLiveModels:
    """Tests for _codex_live_models_with_note function."""

    def test_returns_none_when_no_token(self):
        """Should return None when Codex token is not available."""
        with patch(
            "hermes_cli.auth.resolve_codex_runtime_credentials",
            return_value={"api_key": ""},
        ):
            from hermes_cli.model_picker_config import _codex_live_models_with_note

            result = _codex_live_models_with_note()
            assert result == (None, None)

    def test_returns_none_on_failure(self):
        """Should return fallback note on exception."""
        with patch(
            "hermes_cli.auth.resolve_codex_runtime_credentials",
            side_effect=Exception("Auth failed"),
        ):
            from hermes_cli.model_picker_config import _codex_live_models_with_note

            result = _codex_live_models_with_note()
            assert result[0] is None
            assert result[1] == "Fallback local models"


class TestIsProviderConfigured:
    """Tests for is_provider_configured function."""

    def test_returns_false_on_exception(self):
        """Should return False when resolve_runtime_provider raises."""
        with patch(
            "hermes_cli.model_picker_config.resolve_runtime_provider",
            side_effect=Exception("Provider not found"),
        ):
            from hermes_cli.model_picker_config import is_provider_configured

            result = is_provider_configured("unknown-provider")
            assert result is False


class TestLoadModelPickerConfig:
    """Tests for load_model_picker_config function."""

    def test_returns_empty_config_when_file_not_exists(self):
        """Should return default config when models.yaml doesn't exist."""
        with patch(
            "hermes_cli.model_picker_config.models_yaml_path",
            return_value=Path("/nonexistent/models.yaml"),
        ):
            from hermes_cli.model_picker_config import load_model_picker_config

            result = load_model_picker_config()
            assert result == {"providers": []}

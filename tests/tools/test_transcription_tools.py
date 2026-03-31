"""
Tests for tools/transcription_tools.py

Focuses on the config/env-var resolution logic added to fix:
  https://github.com/NousResearch/hermes-agent/issues/4102

  stt.openai.api_key and base_url from config were silently ignored;
  only VOICE_TOOLS_OPENAI_KEY env var was consulted, causing
  local/compatible endpoints to always fail.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

from tools.transcription_tools import (
    _resolve_api_key,
    _resolve_base_url,
    _load_stt_config,
    transcribe_audio,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_STT_MODEL,
)


# ---------------------------------------------------------------------------
# _resolve_api_key
# ---------------------------------------------------------------------------

class TestResolveApiKey:
    def test_env_var_wins_over_config(self, monkeypatch):
        """VOICE_TOOLS_OPENAI_KEY env var takes precedence over config value."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "env-key-123")
        stt_config = {"openai": {"api_key": "config-key-456"}}
        assert _resolve_api_key(stt_config) == "env-key-123"

    def test_config_key_used_when_no_env(self, monkeypatch):
        """stt.openai.api_key is used when VOICE_TOOLS_OPENAI_KEY is absent."""
        monkeypatch.delenv("VOICE_TOOLS_OPENAI_KEY", raising=False)
        stt_config = {"openai": {"api_key": "config-key-456"}}
        assert _resolve_api_key(stt_config) == "config-key-456"

    def test_returns_none_when_both_absent(self, monkeypatch):
        """Returns None when neither env var nor config key is present."""
        monkeypatch.delenv("VOICE_TOOLS_OPENAI_KEY", raising=False)
        assert _resolve_api_key({}) is None
        assert _resolve_api_key({"openai": {}}) is None

    def test_empty_config_key_falls_through_to_none(self, monkeypatch):
        """An empty string in config.openai.api_key is treated as absent."""
        monkeypatch.delenv("VOICE_TOOLS_OPENAI_KEY", raising=False)
        assert _resolve_api_key({"openai": {"api_key": ""}}) is None

    def test_empty_env_var_falls_back_to_config(self, monkeypatch):
        """Empty env var string is treated as absent; config key is used."""
        monkeypatch.delenv("VOICE_TOOLS_OPENAI_KEY", raising=False)
        stt_config = {"openai": {"api_key": "config-key"}}
        assert _resolve_api_key(stt_config) == "config-key"


# ---------------------------------------------------------------------------
# _resolve_base_url
# ---------------------------------------------------------------------------

class TestResolveBaseUrl:
    def test_default_when_no_config(self):
        """Falls back to DEFAULT_OPENAI_BASE_URL when no config override."""
        assert _resolve_base_url({}) == DEFAULT_OPENAI_BASE_URL
        assert _resolve_base_url({"openai": {}}) == DEFAULT_OPENAI_BASE_URL

    def test_config_base_url_used(self):
        """stt.openai.base_url overrides the default endpoint."""
        local_url = "http://127.0.0.1:8001/v1"
        stt_config = {"openai": {"base_url": local_url}}
        assert _resolve_base_url(stt_config) == local_url

    def test_empty_config_base_url_uses_default(self):
        """Empty string in config.openai.base_url falls back to default."""
        assert _resolve_base_url({"openai": {"base_url": ""}}) == DEFAULT_OPENAI_BASE_URL

    def test_whitespace_config_base_url_uses_default(self):
        """Whitespace-only base_url is treated as absent."""
        assert _resolve_base_url({"openai": {"base_url": "  "}}) == DEFAULT_OPENAI_BASE_URL


# ---------------------------------------------------------------------------
# transcribe_audio — error paths (no real I/O)
# ---------------------------------------------------------------------------

class TestTranscribeAudioErrors:
    def test_missing_api_key_returns_error(self, monkeypatch, tmp_path):
        """Returns error dict when no API key is available."""
        monkeypatch.delenv("VOICE_TOOLS_OPENAI_KEY", raising=False)

        # Patch load_config to return empty stt config (no config key either)
        with patch("tools.transcription_tools._load_stt_config", return_value={}):
            result = transcribe_audio(str(tmp_path / "audio.mp3"))

        assert result["success"] is False
        assert "api_key" in result["error"].lower() or "key" in result["error"].lower()
        assert result["transcript"] == ""

    def test_missing_file_returns_error(self, monkeypatch, tmp_path):
        """Returns error dict when the audio file does not exist."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "test-key")
        nonexistent = str(tmp_path / "missing.mp3")

        result = transcribe_audio(nonexistent)

        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["transcript"] == ""

    def test_unsupported_format_returns_error(self, monkeypatch, tmp_path):
        """Returns error dict for unsupported audio formats."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "test-key")
        bad_file = tmp_path / "audio.xyz"
        bad_file.write_bytes(b"data")

        result = transcribe_audio(str(bad_file))

        assert result["success"] is False
        assert "Unsupported" in result["error"]
        assert result["transcript"] == ""

    def test_file_too_large_returns_error(self, monkeypatch, tmp_path):
        """Returns error dict when the audio file exceeds the 25 MB limit."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "test-key")
        large_file = tmp_path / "big.mp3"
        large_file.write_bytes(b"x" * (26 * 1024 * 1024))  # 26 MB

        result = transcribe_audio(str(large_file))

        assert result["success"] is False
        assert "too large" in result["error"]
        assert result["transcript"] == ""


# ---------------------------------------------------------------------------
# transcribe_audio — successful path using config key + local base_url
# ---------------------------------------------------------------------------

class TestTranscribeAudioSuccess:
    def test_uses_config_key_and_local_base_url(self, monkeypatch, tmp_path):
        """
        Regression test for issue #4102:
        When VOICE_TOOLS_OPENAI_KEY is absent but stt.openai.api_key and
        stt.openai.base_url are set in config, transcription should succeed
        and use the local endpoint — not api.openai.com.
        """
        monkeypatch.delenv("VOICE_TOOLS_OPENAI_KEY", raising=False)

        audio_file = tmp_path / "voice.ogg"
        audio_file.write_bytes(b"fake-ogg-data")

        stt_config = {
            "model": "whisper-large-v3-turbo",
            "openai": {
                "api_key": "local-token",
                "base_url": "http://127.0.0.1:8001/v1",
            },
        }

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "Hello world"

        with patch("tools.transcription_tools._load_stt_config", return_value=stt_config):
            with patch("tools.transcription_tools.OpenAI", return_value=mock_client) as mock_openai_cls:
                result = transcribe_audio(str(audio_file))

        # Should succeed
        assert result["success"] is True
        assert result["transcript"] == "Hello world"

        # OpenAI client must be instantiated with the local key and URL
        mock_openai_cls.assert_called_once_with(
            api_key="local-token",
            base_url="http://127.0.0.1:8001/v1",
        )

        # Model from config should be passed to the API
        mock_client.audio.transcriptions.create.assert_called_once()
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs.get("model") == "whisper-large-v3-turbo"

    def test_env_key_overrides_config_key(self, monkeypatch, tmp_path):
        """Env var VOICE_TOOLS_OPENAI_KEY always wins over config api_key."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "env-key")

        audio_file = tmp_path / "voice.mp3"
        audio_file.write_bytes(b"fake-mp3-data")

        stt_config = {
            "openai": {
                "api_key": "config-key-should-be-ignored",
                "base_url": "http://127.0.0.1:8001/v1",
            },
        }

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "Hi there"

        with patch("tools.transcription_tools._load_stt_config", return_value=stt_config):
            with patch("tools.transcription_tools.OpenAI", return_value=mock_client) as mock_openai_cls:
                result = transcribe_audio(str(audio_file))

        assert result["success"] is True
        # Env key must be used, not the config key
        mock_openai_cls.assert_called_once_with(
            api_key="env-key",
            base_url="http://127.0.0.1:8001/v1",
        )

    def test_default_model_when_not_in_config(self, monkeypatch, tmp_path):
        """Falls back to DEFAULT_STT_MODEL when stt.model is absent from config."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "test-key")

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake-wav")

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "transcript"

        with patch("tools.transcription_tools._load_stt_config", return_value={}):
            with patch("tools.transcription_tools.OpenAI", return_value=mock_client):
                result = transcribe_audio(str(audio_file))

        assert result["success"] is True
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs.get("model") == DEFAULT_STT_MODEL

    def test_caller_model_overrides_config(self, monkeypatch, tmp_path):
        """Explicit model argument overrides both config and default."""
        monkeypatch.setenv("VOICE_TOOLS_OPENAI_KEY", "test-key")

        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-m4a")

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = "transcript"

        with patch("tools.transcription_tools._load_stt_config", return_value={"model": "whisper-1"}):
            with patch("tools.transcription_tools.OpenAI", return_value=mock_client):
                result = transcribe_audio(str(audio_file), model="gpt-4o-transcribe")

        assert result["success"] is True
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs.get("model") == "gpt-4o-transcribe"

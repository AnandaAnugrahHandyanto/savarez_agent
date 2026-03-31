#!/usr/bin/env python3
"""
Transcription Tools Module

Provides speech-to-text transcription using OpenAI's Whisper API.
Used by the messaging gateway to automatically transcribe voice messages
sent by users on Telegram, Discord, WhatsApp, and Slack.

Supported models:
  - whisper-1        (cheapest, good quality)
  - gpt-4o-mini-transcribe  (better quality, higher cost)
  - gpt-4o-transcribe       (best quality, highest cost)

Supported input formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg

Usage:
    from tools.transcription_tools import transcribe_audio

    result = transcribe_audio("/path/to/audio.ogg")
    if result["success"]:
        print(result["transcript"])
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# Default STT model -- cheapest and widely available
DEFAULT_STT_MODEL = "whisper-1"

# Default OpenAI base URL
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

# Supported audio formats
SUPPORTED_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}

# Maximum file size (25MB - OpenAI limit)
MAX_FILE_SIZE = 25 * 1024 * 1024


def _load_stt_config() -> Dict[str, Any]:
    """
    Load STT configuration from ~/.hermes/config.yaml.

    Returns a dict with STT settings. Falls back to defaults
    for any missing fields.
    """
    try:
        from hermes_cli.config import load_config
        config = load_config()
        return config.get("stt", {})
    except Exception:
        return {}


def _resolve_api_key(stt_config: Dict[str, Any]) -> Optional[str]:
    """
    Resolve the OpenAI API key for STT.

    Priority order:
    1. ``VOICE_TOOLS_OPENAI_KEY`` environment variable
    2. ``stt.openai.api_key`` in config.yaml

    This lets users with local OpenAI-compatible endpoints (whisper.cpp,
    LocalAI, oMLX) store their key in config rather than as an env var,
    while env vars still take precedence for CI/production deployments.
    """
    # 1. Environment variable wins
    env_key = os.getenv("VOICE_TOOLS_OPENAI_KEY")
    if env_key:
        return env_key

    # 2. Fall back to config value
    openai_cfg = stt_config.get("openai", {})
    config_key = openai_cfg.get("api_key", "")
    if config_key:
        return config_key

    return None


def _resolve_base_url(stt_config: Dict[str, Any]) -> str:
    """
    Resolve the base URL for the OpenAI-compatible STT endpoint.

    Priority order:
    1. ``stt.openai.base_url`` in config.yaml (explicit override)
    2. ``DEFAULT_OPENAI_BASE_URL`` constant

    Users running local Whisper endpoints (whisper.cpp HTTP server,
    LocalAI, oMLX) set ``stt.openai.base_url: http://127.0.0.1:8001/v1``
    in their config.yaml.  Without this, requests always went to
    api.openai.com regardless of config.
    """
    openai_cfg = stt_config.get("openai", {})
    configured_url = openai_cfg.get("base_url", "").strip()
    return configured_url if configured_url else DEFAULT_OPENAI_BASE_URL


def transcribe_audio(file_path: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Transcribe an audio file using an OpenAI-compatible Whisper endpoint.

    Reads provider settings from ``~/.hermes/config.yaml`` (``stt`` section)
    so that local endpoints (whisper.cpp, LocalAI, oMLX, etc.) work
    without requiring environment variables:

    .. code-block:: yaml

        stt:
          provider: openai
          openai:
            model: whisper-large-v3-turbo
            base_url: http://127.0.0.1:8001/v1
            api_key: "local-token"

    Environment variables (``VOICE_TOOLS_OPENAI_KEY``) still take
    precedence over config values, so existing deployments are unaffected.

    Args:
        file_path: Absolute path to the audio file to transcribe.
        model:     Whisper model to use. Overrides config when provided;
                   defaults to ``stt.model`` in config or ``"whisper-1"``.

    Returns:
        dict with keys:

        - ``"success"`` (bool): Whether transcription succeeded.
        - ``"transcript"`` (str): The transcribed text (empty on failure).
        - ``"error"`` (str, optional): Error message if success is False.
    """
    stt_config = _load_stt_config()

    api_key = _resolve_api_key(stt_config)
    if not api_key:
        return {
            "success": False,
            "transcript": "",
            "error": (
                "No API key configured for STT. Set VOICE_TOOLS_OPENAI_KEY "
                "or add stt.openai.api_key to ~/.hermes/config.yaml"
            ),
        }

    base_url = _resolve_base_url(stt_config)

    audio_path = Path(file_path)

    # Validate file exists
    if not audio_path.exists():
        return {
            "success": False,
            "transcript": "",
            "error": f"Audio file not found: {file_path}",
        }

    if not audio_path.is_file():
        return {
            "success": False,
            "transcript": "",
            "error": f"Path is not a file: {file_path}",
        }

    # Validate file extension
    if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
        return {
            "success": False,
            "transcript": "",
            "error": (
                f"Unsupported file format: {audio_path.suffix}. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
            ),
        }

    # Validate file size
    try:
        file_size = audio_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return {
                "success": False,
                "transcript": "",
                "error": (
                    f"File too large: {file_size / (1024*1024):.1f}MB "
                    f"(max {MAX_FILE_SIZE / (1024*1024)}MB)"
                ),
            }
    except OSError as e:
        logger.error("Failed to get file size for %s: %s", file_path, e, exc_info=True)
        return {
            "success": False,
            "transcript": "",
            "error": f"Failed to access file: {e}",
        }

    # Resolve model: caller > config > default
    if model is None:
        model = stt_config.get("model", DEFAULT_STT_MODEL)

    try:
        from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

        client = OpenAI(api_key=api_key, base_url=base_url)

        with open(file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="text",
            )

        # The response is a plain string when response_format="text"
        transcript_text = str(transcription).strip()

        logger.info("Transcribed %s (%d chars)", audio_path.name, len(transcript_text))

        return {
            "success": True,
            "transcript": transcript_text,
        }

    except PermissionError:
        logger.error("Permission denied accessing file: %s", file_path, exc_info=True)
        return {
            "success": False,
            "transcript": "",
            "error": f"Permission denied: {file_path}",
        }
    except APIConnectionError as e:
        logger.error("API connection error during transcription: %s", e, exc_info=True)
        return {
            "success": False,
            "transcript": "",
            "error": f"Connection error: {e}",
        }
    except APITimeoutError as e:
        logger.error("API timeout during transcription: %s", e, exc_info=True)
        return {
            "success": False,
            "transcript": "",
            "error": f"Request timeout: {e}",
        }
    except APIError as e:
        logger.error("OpenAI API error during transcription: %s", e, exc_info=True)
        return {
            "success": False,
            "transcript": "",
            "error": f"API error: {e}",
        }
    except Exception as e:
        logger.error("Unexpected error during transcription: %s", e, exc_info=True)
        return {
            "success": False,
            "transcript": "",
            "error": f"Transcription failed: {e}",
        }

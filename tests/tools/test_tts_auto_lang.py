"""Tests for TTS automatic language-to-voice selection."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from tools import tts_tool


def test_detect_tts_language_from_unicode_scripts():
    assert tts_tool._detect_tts_language("Hello world") == "en"
    assert tts_tool._detect_tts_language("Привет мир") == "ru"
    assert tts_tool._detect_tts_language("你好世界") == "zh"
    assert tts_tool._detect_tts_language("こんにちは") == "ja"


def test_auto_lang_global_voice_map_applies_provider_voice():
    config = {
        "auto_lang": True,
        "voices": {
            "en": "alloy",
            "zh": "nova",
            "fallback": "echo",
        },
    }

    updated = tts_tool._with_auto_lang_voice(config, "openai", "你好")

    assert updated["openai"]["voice"] == "nova"
    assert "openai" not in config


def test_auto_lang_provider_voice_map_overrides_global_map():
    config = {
        "auto_lang": True,
        "voices": {"ru": "global-ru"},
        "edge": {
            "voices": {
                "ru": "ru-RU-SvetlanaNeural",
                "fallback": "en-US-AvaNeural",
            },
        },
    }

    updated = tts_tool._with_auto_lang_voice(config, "edge", "Привет")

    assert updated["edge"]["voice"] == "ru-RU-SvetlanaNeural"


def test_auto_lang_updates_command_provider_voice_without_mutating_original():
    config = {
        "provider": "local-tts",
        "auto_lang": True,
        "voices": {"zh": "zh-voice", "fallback": "en-voice"},
        "providers": {
            "local-tts": {
                "type": "command",
                "command": "local-tts --voice {voice}",
            },
        },
    }

    updated = tts_tool._with_auto_lang_voice(config, "local-tts", "你好")

    assert updated["providers"]["local-tts"]["voice"] == "zh-voice"
    assert "voice" not in config["providers"]["local-tts"]


def test_text_to_speech_tool_selects_edge_voice_from_language(
    tmp_path,
    monkeypatch,
):
    config = {
        "provider": "edge",
        "auto_lang": True,
        "voices": {
            "ru": "ru-RU-SvetlanaNeural",
            "fallback": "en-US-AvaNeural",
        },
    }
    monkeypatch.setattr(tts_tool, "_load_tts_config", lambda: config)
    monkeypatch.setattr(tts_tool, "DEFAULT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(tts_tool, "_convert_to_opus", lambda _path: None)

    mock_comm = MagicMock()

    async def save_audio(path):
        Path(path).write_bytes(b"mp3")

    mock_comm.save = AsyncMock(side_effect=save_audio)
    mock_edge = MagicMock()
    mock_edge.Communicate = MagicMock(return_value=mock_comm)
    monkeypatch.setattr(tts_tool, "_import_edge_tts", lambda: mock_edge)

    result = json.loads(tts_tool.text_to_speech_tool("Привет мир"))

    assert result["success"] is True
    assert mock_edge.Communicate.call_args.args[0] == "Привет мир"
    assert mock_edge.Communicate.call_args.kwargs["voice"] == "ru-RU-SvetlanaNeural"

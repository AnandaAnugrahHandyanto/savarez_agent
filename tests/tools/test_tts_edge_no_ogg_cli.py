"""Regression tests for Edge TTS keeping MP3 on non-Telegram platforms (#26404).

Edge TTS writes MP3 natively. Pre-fix, `text_to_speech_tool` unconditionally
re-encoded that MP3 to OGG/Opus regardless of the delivery platform, which
broke local playback via `afplay` on macOS CLI (and any other tool that
expects the original MP3).

These tests assert that the post-generation `_convert_to_opus` call is
gated on the Telegram delivery predicate (``want_opus``).
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools import tts_tool
from tools.tts_tool import text_to_speech_tool


@pytest.fixture
def edge_stub(monkeypatch):
    """Stub Edge TTS so it writes a fake MP3 at the output path without
    network access."""
    mock_comm = MagicMock()

    async def _fake_save(output_path):
        Path(output_path).write_bytes(b"ID3fake-mp3-bytes")

    mock_comm.save = AsyncMock(side_effect=_fake_save)
    mock_edge = MagicMock()
    mock_edge.Communicate = MagicMock(return_value=mock_comm)
    monkeypatch.setattr(tts_tool, "_import_edge_tts", lambda: mock_edge)

    cfg = {"provider": "edge"}
    monkeypatch.setattr(tts_tool, "_load_tts_config", lambda: cfg)


class TestEdgeTtsOpusGating:
    def test_cli_platform_keeps_mp3_and_skips_conversion(self, edge_stub, tmp_path, monkeypatch):
        """When HERMES_SESSION_PLATFORM is unset (CLI), Edge TTS output
        must stay as `.mp3` and `_convert_to_opus` must NOT be invoked."""
        monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)

        out = tmp_path / "clip.mp3"

        def fake_convert(mp3_path):
            # If this is invoked at all, the gating regressed. Produce a real
            # .ogg sidecar so the rest of the function continues and the
            # post-condition assertions surface the regression cleanly instead
            # of masking it as a JSON-serialisation error.
            ogg_path = mp3_path.rsplit(".", 1)[0] + ".ogg"
            Path(ogg_path).write_bytes(b"OggS-fake-opus")
            return ogg_path

        with patch.object(tts_tool, "_convert_to_opus", side_effect=fake_convert) as mock_convert:
            result = text_to_speech_tool(text="hello", output_path=str(out))

        data = json.loads(result)
        assert data["success"] is True, data
        assert data["provider"] == "edge"
        mock_convert.assert_not_called()
        assert data["file_path"].endswith(".mp3"), (
            f"Edge TTS should keep .mp3 on CLI but returned {data['file_path']}"
        )

    def test_telegram_platform_still_converts_to_ogg(self, edge_stub, tmp_path, monkeypatch):
        """Regression guard: Telegram delivery (the only legit use-case for
        OGG/Opus conversion) must still trigger `_convert_to_opus`."""
        monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")

        out = tmp_path / "clip.mp3"

        def fake_convert(mp3_path):
            ogg_path = mp3_path.rsplit(".", 1)[0] + ".ogg"
            Path(ogg_path).write_bytes(b"OggS-fake-opus")
            return ogg_path

        with patch.object(tts_tool, "_convert_to_opus", side_effect=fake_convert) as mock_convert:
            result = text_to_speech_tool(text="hello", output_path=str(out))

        data = json.loads(result)
        assert data["success"] is True, data
        mock_convert.assert_called_once()
        assert data["file_path"].endswith(".ogg"), (
            f"Telegram delivery should convert to .ogg but returned {data['file_path']}"
        )

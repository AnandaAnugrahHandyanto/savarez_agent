from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from voice_bridge import transcribe_wav


def test_transcribe_wav_rejects_missing_input(tmp_path: Path) -> None:
    whisper_exe = tmp_path / "whisper-cli.exe"
    whisper_model = tmp_path / "ggml-small.bin"
    whisper_exe.write_text("exe", encoding="utf-8")
    whisper_model.write_text("model", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="wav file not found"):
        transcribe_wav(tmp_path / "missing.wav", whisper_exe, whisper_model)


def test_transcribe_wav_includes_whisper_stderr(tmp_path: Path) -> None:
    wav_path = tmp_path / "input.wav"
    whisper_exe = tmp_path / "whisper-cli.exe"
    whisper_model = tmp_path / "ggml-small.bin"
    wav_path.write_bytes(b"RIFF")
    whisper_exe.write_text("exe", encoding="utf-8")
    whisper_model.write_text("model", encoding="utf-8")

    with patch(
        "voice_bridge.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            2,
            ["whisper-cli"],
            stderr="input file not found",
        ),
    ):
        with pytest.raises(RuntimeError, match="input file not found"):
            transcribe_wav(wav_path, whisper_exe, whisper_model)

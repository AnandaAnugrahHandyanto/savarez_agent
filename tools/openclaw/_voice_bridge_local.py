"""Local-only voice capture/transcription (optional openclaw-voice extra)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import sounddevice as sd
import soundfile as sf


def list_audio_devices() -> dict[str, Any]:
    devices = []
    for index, device in enumerate(sd.query_devices()):
        devices.append(
            {
                "index": index,
                "name": device.get("name", ""),
                "max_input_channels": device.get("max_input_channels", 0),
                "max_output_channels": device.get("max_output_channels", 0),
            },
        )
    return {"success": True, "devices": devices, "default": list(sd.default.device)}


def run_voice_turn_local(
    *,
    record_seconds: float,
    samplerate: int,
    input_device: int | None,
    whisper_exe: Path,
    whisper_model: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="hermes-voice-") as tmp:
        wav_path = Path(tmp) / "input.wav"
        data = sd.rec(
            int(record_seconds * samplerate),
            samplerate=samplerate,
            channels=1,
            dtype="float32",
            device=input_device,
        )
        sd.wait()
        sf.write(str(wav_path), data, samplerate)

        import subprocess

        command = [
            str(whisper_exe),
            "-m",
            str(whisper_model),
            "-f",
            str(wav_path),
            "-l",
            "ja",
            "-nt",
            "-np",
        ]
        try:
            proc = subprocess.run(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            return {
                "success": False,
                "error": "whisper_failed",
                "detail": (exc.stderr or exc.stdout or "")[:500],
            }
        transcript = proc.stdout.strip()
        if not transcript:
            return {"success": False, "error": "empty_transcript"}
        return {
            "success": True,
            "transcript": transcript,
            "reply": None,
            "note": "Local mode: no agent reply — use harness for full turn or paste transcript to Hermes.",
        }

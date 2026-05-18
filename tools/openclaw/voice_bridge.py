"""Voice bridge helpers — local optional deps or harness HTTP fallback."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tools.openclaw.harness_client import call_harness, is_harness_running

DEFAULT_WHISPER_EXE = Path(
    os.environ.get("WHISPER_EXE", str(Path.home() / "Desktop" / "whisper.cpp" / "Release" / "whisper-cli.exe")),
)
DEFAULT_WHISPER_MODEL = Path(
    os.environ.get(
        "WHISPER_MODEL",
        str(Path.home() / "Desktop" / "whisper.cpp" / "models" / "ggml-small.bin"),
    ),
)


def local_audio_deps_available() -> bool:
    try:
        import sounddevice  # noqa: F401
        import soundfile  # noqa: F401

        return True
    except ImportError:
        return False


def voice_stack_status() -> dict[str, Any]:
    """Report how voice features can run on this machine."""
    harness_up = is_harness_running()
    local = local_audio_deps_available()
    whisper_ok = DEFAULT_WHISPER_EXE.is_file() and DEFAULT_WHISPER_MODEL.is_file()
    modes: list[str] = []
    if harness_up:
        modes.append("harness_http")
    if local and whisper_ok:
        modes.append("local_whisper")
    elif local:
        modes.append("local_audio_only")
    return {
        "harness_running": harness_up,
        "local_audio_deps": local,
        "whisper_exe": str(DEFAULT_WHISPER_EXE),
        "whisper_model": str(DEFAULT_WHISPER_MODEL),
        "whisper_ready": whisper_ok,
        "voicevox_url": os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021"),
        "available_modes": modes,
        "recommendation": (
            "hermes harness start"
            if not harness_up
            else "POST /voice/turn on harness or enable tool voice_bridge_turn"
        ),
    }


def list_audio_devices() -> dict[str, Any]:
    if is_harness_running():
        result = call_harness("voice/devices", method="GET")
        if result.get("success") is not False:
            return result
    if local_audio_deps_available():
        from tools.openclaw._voice_bridge_local import list_audio_devices as _local_list

        return _local_list()
    return {
        "success": False,
        "error": "voice_unavailable",
        "detail": "Install hermes-agent[openclaw-voice] or run: hermes harness start",
    }


def voice_turn(
    *,
    record_seconds: float = 5.0,
    samplerate: int = 16000,
    input_device: int | None = None,
    emotion: str = "neutral",
    speaker: int = 8,
    openclaw_timeout: int = 180,
) -> dict[str, Any]:
    """One mic → whisper → agent → VOICEVOX turn (prefers harness daemon)."""
    if is_harness_running():
        payload = {
            "record_seconds": record_seconds,
            "samplerate": samplerate,
            "input_device": input_device,
            "emotion": emotion,
            "speaker": speaker,
            "openclaw_timeout": openclaw_timeout,
            "whisper_exe": str(DEFAULT_WHISPER_EXE),
            "whisper_model": str(DEFAULT_WHISPER_MODEL),
        }
        return call_harness("voice/turn", payload, timeout=float(openclaw_timeout) + 60.0)

    if local_audio_deps_available() and DEFAULT_WHISPER_EXE.is_file():
        from tools.openclaw._voice_bridge_local import run_voice_turn_local

        return run_voice_turn_local(
            record_seconds=record_seconds,
            samplerate=samplerate,
            input_device=input_device,
            whisper_exe=DEFAULT_WHISPER_EXE,
            whisper_model=DEFAULT_WHISPER_MODEL,
        )

    return {
        "success": False,
        "error": "voice_turn_unavailable",
        "status": voice_stack_status(),
    }


def voice_test_say(text: str, emotion: str = "neutral", speaker: int = 8) -> dict[str, Any]:
    if is_harness_running():
        return call_harness(
            "voice/test-say",
            {"text": text, "emotion": emotion, "speaker": speaker},
            timeout=120.0,
        )
    return {
        "success": False,
        "error": "harness_required_for_playback",
        "recommendation": "hermes harness start",
    }

"""Local voice conversation bridge for Hypura Harness."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import sounddevice as sd
import soundfile as sf


ROOT = Path(__file__).parent
REPO_ROOT = ROOT.parent.parent.parent
DEFAULT_WHISPER_DIR = Path.home() / "Desktop" / "whisper.cpp"
DEFAULT_WHISPER_EXE = DEFAULT_WHISPER_DIR / "Release" / "whisper-cli.exe"
DEFAULT_WHISPER_MODEL = DEFAULT_WHISPER_DIR / "models" / "ggml-small.bin"
DEFAULT_COMPANION_STATE_PATH = REPO_ROOT / ".openclaw-desktop" / "companion_state.json"


def list_audio_devices() -> dict[str, Any]:
    devices = []
    for index, device in enumerate(sd.query_devices()):
        devices.append(
            {
                "index": index,
                "name": device.get("name", ""),
                "max_input_channels": device.get("max_input_channels", 0),
                "max_output_channels": device.get("max_output_channels", 0),
                "hostapi": device.get("hostapi", 0),
            }
        )
    return {"devices": devices, "default": list(sd.default.device)}


def record_wav(path: Path, seconds: float, samplerate: int, input_device: int | None) -> None:
    data = sd.rec(
        int(seconds * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=input_device,
    )
    sd.wait()
    sf.write(str(path), data, samplerate)


def transcribe_wav(
    wav_path: Path,
    whisper_exe: Path = DEFAULT_WHISPER_EXE,
    whisper_model: Path = DEFAULT_WHISPER_MODEL,
) -> str:
    if not wav_path.exists():
        raise FileNotFoundError(f"wav file not found: {wav_path}")
    if not whisper_exe.exists():
        raise FileNotFoundError(f"whisper executable not found: {whisper_exe}")
    if not whisper_model.exists():
        raise FileNotFoundError(f"whisper model not found: {whisper_model}")
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
        result = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"whisper transcription failed with exit code {exc.returncode}"
            f"{': ' + detail if detail else ''}"
        ) from exc
    return result.stdout.strip()


def extract_agent_text(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    payloads = data.get("result", {}).get("payloads", [])
    if isinstance(payloads, list):
        texts = [
            item.get("text", "").strip()
            for item in payloads
            if isinstance(item, dict) and item.get("text")
        ]
        joined = "\n".join(text for text in texts if text)
        if joined:
            return joined
    summary = data.get("summary")
    return summary.strip() if isinstance(summary, str) else raw


def call_openclaw_agent(message: str, command_template: str, timeout: int) -> str:
    if "{message}" not in command_template:
        raise ValueError("OpenClaw voice command template must contain {message}")
    command = command_template.replace("{message}", json.dumps(message, ensure_ascii=False))
    result = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "OpenClaw command failed "
            f"({result.returncode}) stdout={result.stdout.strip()} stderr={result.stderr.strip()}"
        )
    return extract_agent_text(result.stdout)


def read_companion_transcript(
    state_path: Path = DEFAULT_COMPANION_STATE_PATH,
) -> dict[str, Any]:
    if not state_path.exists():
        return {"transcript": "", "timestamp": None, "state": None}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    voice = state.get("voice") if isinstance(state, dict) else None
    if not isinstance(voice, dict):
        return {"transcript": "", "timestamp": None, "state": state}
    transcript = voice.get("lastTranscript")
    timestamp = voice.get("lastTranscriptAt")
    return {
        "transcript": transcript.strip() if isinstance(transcript, str) else "",
        "timestamp": timestamp if isinstance(timestamp, int | float) else None,
        "state": state,
    }


def infer_companion_emotion(text: str) -> str:
    normalized = text.lower()
    if any(
        token in text
        for token in (
            "\u3054\u3081\u3093",
            "\u5931\u6557",
            "\u30a8\u30e9\u30fc",
            "\u7121\u7406",
            "\u3067\u304d\u306a\u3044",
        )
    ) or any(token in normalized for token in ("error", "failed", "sorry", "can't", "cannot")):
        return "sad"
    if any(token in text for token in ("!", "\uff01", "\u3059\u3054", "\u3048\u3063", "\u307e\u3058")):
        return "surprised"
    if any(
        token in text
        for token in (
            "\u3042\u308a\u304c\u3068\u3046",
            "\u5b09\u3057\u3044",
            "\u3088\u304b\u3063\u305f",
            "OK",
            "\u4e86\u89e3",
        )
    ):
        return "happy"
    return "neutral"


def resolve_openclaw_command(config: dict[str, Any]) -> str:
    env_command = os.environ.get("OPENCLAW_VOICE_AGENT_CMD", "").strip()
    if env_command:
        return env_command
    voice = config.get("voice")
    if isinstance(voice, dict):
        command = voice.get("openclaw_command")
        if isinstance(command, str) and command.strip():
            return command.strip()
    return "node openclaw.mjs agent --agent main --json --timeout 180 --message {message}"


def run_voice_turn(
    *,
    config: dict[str, Any],
    record_seconds: float,
    samplerate: int,
    input_device: int | None,
    whisper_exe: Path,
    whisper_model: Path,
    openclaw_timeout: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="hypura-voice-") as tmp:
        wav_path = Path(tmp) / "input.wav"
        record_wav(wav_path, record_seconds, samplerate, input_device)
        transcript = transcribe_wav(wav_path, whisper_exe, whisper_model)
        if not transcript:
            return {"success": False, "error": "empty_transcript", "transcript": ""}
        reply = call_openclaw_agent(
            transcript,
            resolve_openclaw_command(config),
            openclaw_timeout,
        )
        return {"success": True, "transcript": transcript, "reply": reply}


def run_companion_transcript_turn(
    *,
    config: dict[str, Any],
    transcript: str | None,
    transcript_timestamp: int | float | None,
    last_seen_timestamp: int | float | None,
    openclaw_timeout: int,
    state_path: Path = DEFAULT_COMPANION_STATE_PATH,
) -> dict[str, Any]:
    resolved_transcript = transcript.strip() if isinstance(transcript, str) else ""
    resolved_timestamp = transcript_timestamp
    if not resolved_transcript:
        snapshot = read_companion_transcript(state_path)
        resolved_transcript = snapshot["transcript"]
        resolved_timestamp = snapshot["timestamp"]

    if not resolved_transcript:
        return {
            "success": False,
            "error": "empty_transcript",
            "transcript": "",
            "transcript_timestamp": resolved_timestamp,
        }

    if (
        resolved_timestamp is not None
        and last_seen_timestamp is not None
        and resolved_timestamp <= last_seen_timestamp
    ):
        return {
            "success": False,
            "error": "stale_transcript",
            "transcript": resolved_transcript,
            "transcript_timestamp": resolved_timestamp,
        }

    reply = call_openclaw_agent(
        resolved_transcript,
        resolve_openclaw_command(config),
        openclaw_timeout,
    )
    return {
        "success": True,
        "transcript": resolved_transcript,
        "transcript_timestamp": resolved_timestamp,
        "reply": reply,
        "emotion": infer_companion_emotion(reply),
        "handled_at": int(time.time() * 1000),
    }

#!/usr/bin/env python3
"""Validate a voice-backed WhatsApp Calling TTS stream command.

This script renders the same command template Hermes uses for
``calling_sidecar_tts_stream_command``, runs it against a temporary input file,
and verifies that stdout is raw 48 kHz mono 20 ms ``pcm_s16le`` frames suitable
for the voice WebRTC sidecar.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any


DEFAULT_TEXT = "Hermes voice stream command smoke test."
DEFAULT_SAMPLE_RATE = 48_000
DEFAULT_CHANNELS = 1
DEFAULT_FRAME_MS = 20
DEFAULT_BYTES_PER_SAMPLE = 2
DEFAULT_ENCODING = "pcm_s16le"
DEFAULT_MIN_PEAK = 384
DEFAULT_MIN_DURATION_MS = 200


@dataclass(frozen=True)
class AudioContract:
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    frame_ms: int = DEFAULT_FRAME_MS
    encoding: str = DEFAULT_ENCODING
    bytes_per_sample: int = DEFAULT_BYTES_PER_SAMPLE

    @property
    def samples_per_frame(self) -> int:
        return self.sample_rate * self.frame_ms // 1_000

    @property
    def frame_bytes(self) -> int:
        return self.samples_per_frame * self.channels * self.bytes_per_sample

    @property
    def bytes_per_second(self) -> int:
        return self.sample_rate * self.channels * self.bytes_per_sample

    def validate(self) -> None:
        failures: list[str] = []
        if self.sample_rate <= 0:
            failures.append("sample_rate must be positive")
        if self.channels <= 0:
            failures.append("channels must be positive")
        if self.frame_ms <= 0:
            failures.append("frame_ms must be positive")
        if self.bytes_per_sample <= 0:
            failures.append("bytes_per_sample must be positive")
        if self.encoding != DEFAULT_ENCODING:
            failures.append(f"encoding must be {DEFAULT_ENCODING}")
        if self.samples_per_frame <= 0:
            failures.append("samples_per_frame must be positive")
        if self.frame_bytes <= 0:
            failures.append("frame_bytes must be positive")
        if failures:
            raise SystemExit("invalid audio contract:\n- " + "\n- ".join(failures))

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "frame_ms": self.frame_ms,
            "encoding": self.encoding,
            "bytes_per_sample": self.bytes_per_sample,
            "samples_per_frame": self.samples_per_frame,
            "frame_bytes": self.frame_bytes,
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_executable(value: str, *, label: str) -> str:
    if "/" in value:
        path = Path(value).expanduser()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise SystemExit(f"{label} is not executable: {path}")
        return str(path.resolve())

    found = shutil.which(value)
    if not found:
        raise SystemExit(f"{label} not found on PATH: {value}")
    return found


def build_default_command_template(voice_bin: str) -> str:
    return (
        f"{shlex.quote(voice_bin)} stream --quiet "
        f"--sample-rate {{sample_rate}} --frame-ms {{frame_ms}} "
        f"--raw-output - --input-file {{input_path}} "
        f"--voice {{voice}} --speed {{speed}}"
    )


def render_stream_command(
    command_template: str,
    *,
    input_path: Path,
    text: str,
    contract: AudioContract,
    voice: str,
    speed: str,
) -> str:
    sys.path.insert(0, str(repo_root()))
    from tools.tts_tool import _render_command_tts_template

    return _render_command_tts_template(
        command_template,
        {
            "input_path": str(input_path),
            "text_path": str(input_path),
            "text": text,
            "sample_rate": str(contract.sample_rate),
            "channels": str(contract.channels),
            "frame_ms": str(contract.frame_ms),
            "encoding": contract.encoding,
            "voice": voice,
            "speed": speed,
        },
    )


def max_abs_pcm_s16le(pcm: bytes) -> int:
    if len(pcm) % DEFAULT_BYTES_PER_SAMPLE:
        raise ValueError("pcm_s16le payload must contain whole samples")
    if not pcm:
        return 0
    return max(abs(sample[0]) for sample in struct.iter_unpack("<h", pcm))


def validate_pcm(
    pcm: bytes,
    *,
    contract: AudioContract,
    min_peak: int = DEFAULT_MIN_PEAK,
    min_duration_ms: int = DEFAULT_MIN_DURATION_MS,
) -> dict[str, Any]:
    contract.validate()
    failures: list[str] = []

    if not pcm:
        failures.append("stream command produced no PCM")
    if len(pcm) % contract.bytes_per_sample:
        failures.append("PCM byte length is not aligned to whole s16le samples")
    if len(pcm) % contract.frame_bytes:
        failures.append(
            f"PCM byte length {len(pcm)} is not aligned to {contract.frame_bytes}-byte frames"
        )

    duration_ms = (
        len(pcm) * 1_000 // contract.bytes_per_second
        if contract.bytes_per_second > 0
        else 0
    )
    if duration_ms < min_duration_ms:
        failures.append(
            f"PCM duration {duration_ms}ms is shorter than minimum {min_duration_ms}ms"
        )

    peak = 0
    if len(pcm) % contract.bytes_per_sample == 0:
        peak = max_abs_pcm_s16le(pcm)
        if peak < min_peak:
            failures.append(f"PCM peak {peak} is below minimum {min_peak}")

    if failures:
        raise SystemExit("validation failed:\n- " + "\n- ".join(failures))

    return {
        "bytes": len(pcm),
        "frames": len(pcm) // contract.frame_bytes,
        "duration_ms": duration_ms,
        "peak": peak,
    }


def run_stream_command(command: str, *, timeout: float) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Hermes WhatsApp Calling TTS stream command and verify raw "
            "pcm_s16le frame output."
        )
    )
    parser.add_argument("--voice-bin", default=os.environ.get("VOICE_BIN", "voice"))
    parser.add_argument("--command-template")
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--speed", default="1.0")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    parser.add_argument("--channels", type=int, default=DEFAULT_CHANNELS)
    parser.add_argument("--frame-ms", type=int, default=DEFAULT_FRAME_MS)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--min-peak", type=int, default=DEFAULT_MIN_PEAK)
    parser.add_argument("--min-duration-ms", type=int, default=DEFAULT_MIN_DURATION_MS)
    parser.add_argument("--keep-input", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    voice_bin = resolve_executable(args.voice_bin, label="voice binary")
    contract = AudioContract(
        sample_rate=args.sample_rate,
        channels=args.channels,
        frame_ms=args.frame_ms,
    )
    contract.validate()
    command_template = args.command_template or build_default_command_template(voice_bin)

    tmpdir = Path(tempfile.mkdtemp(prefix="hermes-voice-stream-tts."))
    try:
        input_path = tmpdir / "input.txt"
        input_path.write_text(args.text, encoding="utf-8")
        command = render_stream_command(
            command_template,
            input_path=input_path,
            text=args.text,
            contract=contract,
            voice=args.voice,
            speed=args.speed,
        )
        completed = run_stream_command(command, timeout=args.timeout)
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise SystemExit(
                f"stream command exited with code {completed.returncode}"
                + (f": {detail[:1000]}" if detail else "")
            )

        stats = validate_pcm(
            completed.stdout,
            contract=contract,
            min_peak=args.min_peak,
            min_duration_ms=args.min_duration_ms,
        )
        retained = bool(args.keep_input)
        print(
            json.dumps(
                {
                    "success": True,
                    "input_path": str(input_path) if retained else "<temporary>",
                    "retained": retained,
                    "command_template": command_template,
                    "audio": contract.as_dict(),
                    "pcm": stats,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        if not args.keep_input:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

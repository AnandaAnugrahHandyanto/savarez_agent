from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from gateway.calls.native.voice_turn import VoiceTurnResult
from gateway.calls.native.webrtc_media import AudioUtteranceAccumulator


@dataclass
class FakeVoiceTurnPipeline:
    calls: list[tuple[str, bytes, int]] = field(default_factory=list)

    async def process_pcm16(
        self,
        *,
        call_id: str,
        pcm16: bytes,
        sample_rate: int,
    ) -> VoiceTurnResult:
        self.calls.append((call_id, pcm16, sample_rate))
        return VoiceTurnResult(
            ok=True,
            code="call_voice_turn_completed",
            message="Voice turn completed.",
            audio_path=Path("/tmp/reply.wav"),
        )


@dataclass
class FakeAudioTrack:
    queued: list[str] = field(default_factory=list)

    async def queue_file(self, audio_path: str) -> None:
        self.queued.append(audio_path)


def _pcm16(*samples: int) -> bytes:
    return struct.pack("<" + ("h" * len(samples)), *samples)


@pytest.mark.asyncio
async def test_audio_utterance_accumulator_processes_after_silence():
    pipeline = FakeVoiceTurnPipeline()
    track = FakeAudioTrack()
    accumulator = AudioUtteranceAccumulator(
        call_id="call-1",
        pipeline=pipeline,
        output_track=track,
        sample_rate=48000,
        voice_rms_threshold=500,
        silence_seconds=0.4,
    )

    await accumulator.accept_pcm16(_pcm16(1200, -1200), now=1.0)
    await accumulator.accept_pcm16(_pcm16(900, -900), now=1.1)
    await accumulator.accept_pcm16(_pcm16(0, 0), now=1.3)

    assert pipeline.calls == []
    assert track.queued == []

    await accumulator.accept_pcm16(_pcm16(0, 0), now=1.6)

    assert pipeline.calls == [
        ("call-1", _pcm16(1200, -1200) + _pcm16(900, -900), 48000)
    ]
    assert track.queued == ["/tmp/reply.wav"]


@pytest.mark.asyncio
async def test_audio_utterance_accumulator_skips_failed_voice_turn():
    class FailingPipeline(FakeVoiceTurnPipeline):
        async def process_pcm16(self, *, call_id: str, pcm16: bytes, sample_rate: int):
            self.calls.append((call_id, pcm16, sample_rate))
            return VoiceTurnResult(
                ok=False,
                code="call_voice_stt_failed",
                message="no stt backend",
            )

    pipeline = FailingPipeline()
    track = FakeAudioTrack()
    accumulator = AudioUtteranceAccumulator(
        call_id="call-1",
        pipeline=pipeline,
        output_track=track,
        sample_rate=48000,
        voice_rms_threshold=500,
        silence_seconds=0.1,
    )

    await accumulator.accept_pcm16(_pcm16(1200, -1200), now=1.0)
    await accumulator.accept_pcm16(_pcm16(0, 0), now=1.2)

    assert len(pipeline.calls) == 1
    assert track.queued == []

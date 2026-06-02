"""Real end-to-end streaming-voice simulation (Slice 7).

Drives recorded 16 kHz mono audio through ``build_real_stream_simulation`` —
the REAL turn detector (Silero VAD + Smart Turn v3), REAL faster-whisper STT,
and REAL Piper TTS — with a deterministic stub brain.  The normal-turn test
exercises the full reflex loop end to end; the barge-in variant injects a
deterministic STT + scripted turns (real whisper can't deterministically
finalize on a scripted endpoint) while keeping the real Piper TTS so a
mid-stream interrupt abandons real synthesized audio.

The drive loop lives HERE (outside ``gateway/calls/native/streaming/**``) so it
may use real ``asyncio.sleep`` — the ast-grep no-walltime rule bans sleeps in
the streaming package, not in tests.  These tests run real CPU models, so they
may take tens of seconds.
"""
from __future__ import annotations

import asyncio
import wave
from contextlib import suppress
from importlib.util import find_spec
from pathlib import Path

import pytest

from gateway.calls.native.streaming.pipecat_runtime import pipecat_available
from gateway.calls.native.streaming.simulate import build_real_stream_simulation
from gateway.calls.native.streaming.types import AudioFrame, TurnEndReason

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not (pipecat_available() and find_spec("faster_whisper") and find_spec("piper")),
        reason="real streaming deps not installed",
    ),
]

FIX = Path(__file__).parent / "fixtures" / "turn_detection" / "speech_16k_mono.wav"

_FRAME_BYTES = 640  # 20ms @ 16k mono int16
_SILENCE = b"\x00" * _FRAME_BYTES


async def _push(sim, seq: int, pcm: bytes) -> None:
    await sim.transport.push_inbound(
        AudioFrame(pcm16=pcm, media=sim.media, timestamp_ms=seq * 20, seq=seq)
    )
    await asyncio.sleep(0.02)


async def _drive(sim, wav_path: Path, *, silence_tail_frames: int = 30) -> None:
    """Stream the fixture (then a trailing-silence tail) frame-by-frame."""
    run_task = asyncio.create_task(sim.session.run())

    w = wave.open(str(wav_path), "rb")
    pcm = w.readframes(w.getnframes())
    w.close()

    seq = 0
    for off in range(0, len(pcm) - _FRAME_BYTES, _FRAME_BYTES):
        await _push(sim, seq, pcm[off : off + _FRAME_BYTES])
        seq += 1

    # Mandatory trailing silence (>= Smart-Turn stop_secs=0.5) so the real turn
    # detector emits ENDPOINT_DETECTED for the normal case.
    for _ in range(silence_tail_frames):
        await _push(sim, seq, _SILENCE)
        seq += 1

    await sim.transport.end_inbound()
    await asyncio.wait_for(run_task, timeout=60)


async def test_real_e2e_normal_turn() -> None:
    sim = build_real_stream_simulation(barge_in=False)
    await _drive(sim, FIX)

    summary = sim.summary()
    assert summary["outbound_audio_frames"] >= 1
    assert summary["flushes"] == []

    # Exactly the committed turns the session recorded.
    assert sim.session.records, "no turn was committed"
    rec = next(
        (r for r in sim.session.records if r.ended_reason is TurnEndReason.COMPLETED),
        None,
    )
    assert rec is not None, "expected a COMPLETED turn"
    assert rec.interrupted is False
    assert len(rec.assistant_heard_text) > 0
    # Whisper transcribed the fixture ("...the weather forecast for today?").
    assert "weather" in rec.user_transcript.lower()


async def test_real_e2e_barge_in() -> None:
    # A long ``response_text`` makes Piper's up-front synthesis (run via
    # ``await asyncio.to_thread(self._synthesize_pcm, text)`` in ``local_tts._gen``)
    # take long enough — on the order of hundreds of ms of CPU work — that the
    # scripted USER_SPEECH_STARTED reliably lands while ``_speaking`` is True.
    # The ``_speaking`` window is dominated by that to_thread synthesis
    # suspension, not by draining frames (they are emitted in a tight, await-free
    # loop once synthesis completes).
    sim = build_real_stream_simulation(
        barge_in=True,
        response_text=(
            "The quick brown fox jumps over the lazy dog near the riverbank "
            "at dawn. "
        ) * 8,
    )

    run_task = asyncio.create_task(sim.session.run())

    try:
        # The scripted turns fire by ``frame.seq`` (FakeTurnDetection):
        #   seq 0 -> ENDPOINT_DETECTED  (launch assistant turn; real Piper starts)
        #   seq 1 -> USER_SPEECH_STARTED (vad_trigger flush; partial gives min_words)
        #   seq 2 -> USER_SPEECH_STOPPED (escalating -> INTERRUPT once min_speech_ms)
        await _push(sim, 0, _SILENCE)  # ENDPOINT_DETECTED -> launch assistant turn

        # Wait for real Piper to begin emitting audio (TTS mid-stream).
        for _ in range(500):
            if sim.session._speaking:
                break
            await asyncio.sleep(0.005)
        assert sim.session._speaking, "Piper TTS never started speaking"

        await _push(sim, 1, _SILENCE)  # USER_SPEECH_STARTED -> vad_trigger flush
        for _ in range(3):  # advance past min_speech_ms (40ms) in real time
            await asyncio.sleep(0.02)
        await _push(sim, 2, _SILENCE)  # USER_SPEECH_STOPPED -> INTERRUPT

        await sim.transport.end_inbound()
        await asyncio.wait_for(run_task, timeout=60)
    finally:
        if not run_task.done():
            run_task.cancel()
            with suppress(asyncio.CancelledError):
                await run_task

    summary = sim.summary()
    assert summary["flushes"], "expected at least one flush from barge-in"
    rec = next(
        (r for r in sim.session.records if r.ended_reason is TurnEndReason.BARGED_IN),
        None,
    )
    assert rec is not None, "expected a BARGED_IN turn"
    assert rec.interrupted is True
    assert len(rec.assistant_abandoned_text) > 0

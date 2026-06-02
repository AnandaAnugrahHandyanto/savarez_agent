"""Reusable simulation builder for the streaming voice reflex slice (WP9).

Builds a StreamingCallSession with fakes + VirtualClock ready to be driven by
the caller.  Contains no ``asyncio.sleep`` calls (ast-grep no-walltime rule).
The caller (CLI or tests) owns the drive loop and may use ``asyncio.sleep(0)``
for settling between clock advances.

See ``hermes_cli/calls.py`` ``_run_stream_simulation_with_driver`` for the
production drive loop; see ``tests/gateway/streaming/test_stream_simulation.py``
for direct slice-level tests (which also own the drive loop via the same helper).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .clock import Clock, VirtualClock
from .fakes import (
    FakeAudioTransport,
    FakeBrain,
    FakeSTT,
    FakeTTS,
    FakeTurnDetection,
)
from .interruption import InterruptionPolicy
from .session import StreamingCallSession
from .tracer import StreamingCallTracer
from .types import (
    AudioFrame,
    InterruptionParams,
    MediaFormat,
    StreamingCallContext,
    TranscriptEvent,
    TranscriptKind,
    TurnEvent,
    TurnEventKind,
)

__all__ = [
    "StreamSimulation",
    "build_stream_simulation",
    "build_real_stream_simulation",
]

_MEDIA = MediaFormat(sample_rate=16000, channels=1, frame_ms=20)


def _make_frame(seq: int, media: MediaFormat) -> AudioFrame:
    samples = int(media.sample_rate * media.frame_ms / 1000)
    pcm = b"\x00" * samples * 2
    return AudioFrame(
        pcm16=pcm, media=media, timestamp_ms=seq * media.frame_ms, seq=seq
    )


def _final_transcript(call_id: str, text: str) -> TranscriptEvent:
    return TranscriptEvent(
        call_id=call_id, kind=TranscriptKind.FINAL, text=text
    )


def _partial_transcript(call_id: str, text: str) -> TranscriptEvent:
    return TranscriptEvent(
        call_id=call_id, kind=TranscriptKind.PARTIAL, text=text
    )


def _turn(call_id: str, kind: TurnEventKind, at_ms: int = 0) -> TurnEvent:
    return TurnEvent(call_id=call_id, kind=kind, at_ms=at_ms)


@dataclass
class StreamSimulation:
    """All components of one simulation scenario, ready to be driven.

    The caller drives by:
      1. Starting ``session.run()`` as a background task.
      2. Pushing inbound frames via ``transport.push_inbound(frame(seq))``.
      3. Advancing the virtual clock via ``clock.advance(ms)``.
      4. Calling ``transport.end_inbound()`` to close the stream.
      5. Awaiting the run task to collect ``session.records``.

    Settling between steps (``asyncio.sleep(0)`` × N) is the caller's
    responsibility — it is intentionally excluded from this module.
    """

    call_id: str
    contact_id: str
    media: MediaFormat
    barge_in: bool
    session: StreamingCallSession
    transport: FakeAudioTransport
    clock: Clock

    def make_frame(self, seq: int) -> AudioFrame:
        return _make_frame(seq, self.media)

    def summary(self) -> dict[str, Any]:
        """Return the canonical result dict from the completed session."""
        turns_summary = [
            {
                "ended_reason": r.ended_reason.value,
                "interrupted": r.interrupted,
                "user_chars": len(r.user_transcript),
                "heard_chars": len(r.assistant_heard_text),
                "abandoned_chars": len(r.assistant_abandoned_text),
            }
            for r in self.session.records
        ]
        return {
            "ok": True,
            "code": "call_stream_simulation_passed",
            "call_id": self.call_id,
            "turns": turns_summary,
            "outbound_audio_frames": len(self.transport.sent),
            "flushes": list(self.transport.flushes),
        }


def build_stream_simulation(
    *,
    call_id: str = "stream-sim",
    contact_id: str = "sim-contact",
    caller_text: str = "what's the weather",
    response_text: str = "It's sunny today.",
    barge_in: bool = False,
    brain_delay_ms: int = 0,
) -> StreamSimulation:
    """Construct all simulation components without running anything.

    Returns a ``StreamSimulation`` that the caller can drive.  No I/O, no
    clock advances, no sleeps — purely synchronous construction.
    """
    clock = VirtualClock()
    media = _MEDIA
    ctx = StreamingCallContext(
        call_id=call_id,
        contact_id=contact_id,
        session_id="sim-session",
        media=media,
        interruption=InterruptionParams(
            min_speech_ms=40,
            min_words=2,
        ),
    )

    # STT: partials only needed for barge-in (to satisfy min_words policy).
    if barge_in:
        partials = [_partial_transcript(call_id, "hold on")]
    else:
        partials = []
    stt = FakeSTT(
        partials=partials,
        final=_final_transcript(call_id, caller_text),
    )

    # Turn-detection script.
    # Normal turn: seq 0 → ENDPOINT_DETECTED
    # Barge-in: seq 0 → ENDPOINT_DETECTED, seq 1 → USER_SPEECH_STARTED,
    #           seq 2 → USER_SPEECH_STOPPED (the escalating event → INTERRUPT).
    if barge_in:
        script = [
            (0, _turn(call_id, TurnEventKind.ENDPOINT_DETECTED)),
            (1, _turn(call_id, TurnEventKind.USER_SPEECH_STARTED)),
            (2, _turn(call_id, TurnEventKind.USER_SPEECH_STOPPED)),
        ]
    else:
        script = [(0, _turn(call_id, TurnEventKind.ENDPOINT_DETECTED))]

    transport = FakeAudioTransport(media)
    turns_detector = FakeTurnDetection(script)

    # For barge-in we need many frames-per-word so TTS is still mid-stream.
    frames_per_word = 10 if barge_in else 2
    tts = FakeTTS(clock, frames_per_word=frames_per_word)

    def brain_factory() -> FakeBrain:
        return FakeBrain(clock, text=response_text, delay_ms=brain_delay_ms)

    tracer = StreamingCallTracer(call_id)
    session = StreamingCallSession(
        ctx,
        transport=transport,
        stt=stt,
        turns=turns_detector,
        tts=tts,
        brain_factory=brain_factory,
        policy=InterruptionPolicy(),
        tracer=tracer,
        clock=clock,
    )

    return StreamSimulation(
        call_id=call_id,
        contact_id=contact_id,
        media=media,
        barge_in=barge_in,
        session=session,
        transport=transport,
        clock=clock,
    )


def build_real_stream_simulation(
    *,
    call_id: str = "real-stream-sim",
    contact_id: str = "sim-contact",
    response_text: str = "It's sunny today.",
    barge_in: bool = False,
    turn_detector: Any = None,
    stt: Any = None,
    tts: Any = None,
    clock: Any = None,
) -> StreamSimulation:
    """Construct a REAL-port simulation (Silero VAD + Smart Turn, faster-whisper,
    Piper TTS) with a deterministic stub brain — ready for the caller to drive.

    Mirrors :func:`build_stream_simulation` but swaps the fakes for the real
    local adapters.  The real builders are imported lazily so this module stays
    importable without the optional extras; construction is purely synchronous
    (no sleeps — the caller owns the drive loop in a test outside the streaming
    package, where real ``asyncio.sleep`` is permitted).

    For the barge-in variant the real whisper STT can't deterministically
    finalize on a scripted endpoint, so a deterministic ``FakeSTT`` + scripted
    ``FakeTurnDetection`` are injected while the REAL Piper TTS is kept, so a
    mid-stream interrupt abandons real synthesized audio.
    """
    from .clock import MonotonicClock
    from .local_tts import build_piper_tts
    from .local_turn_detection import build_local_turn_detector
    from .local_whisper_stt import build_local_whisper_stt

    clk = clock or MonotonicClock()
    media = _MEDIA
    ctx = StreamingCallContext(
        call_id=call_id,
        contact_id=contact_id,
        session_id="sim-session",
        media=media,
        interruption=InterruptionParams(
            min_speech_ms=40,
            min_words=2,
        ),
    )

    if barge_in:
        # Real whisper cannot deterministically finalize on a scripted endpoint,
        # so inject a deterministic STT + scripted turns; keep the REAL Piper TTS.
        turns = turn_detector or FakeTurnDetection(
            [
                (0, _turn(call_id, TurnEventKind.ENDPOINT_DETECTED)),
                (1, _turn(call_id, TurnEventKind.USER_SPEECH_STARTED)),
                (2, _turn(call_id, TurnEventKind.USER_SPEECH_STOPPED)),
            ]
        )
        stt_port = stt or FakeSTT(
            partials=[_partial_transcript(call_id, "hold on")],
            final=_final_transcript(call_id, "tell me a story"),
        )
        tts_port = tts or build_piper_tts(media, clock=clk, call_id=call_id)
    else:
        turns = turn_detector or build_local_turn_detector(media, call_id=call_id)
        stt_port = stt or build_local_whisper_stt(media, call_id=call_id)
        tts_port = tts or build_piper_tts(media, clock=clk, call_id=call_id)

    transport = FakeAudioTransport(media)

    def brain_factory() -> FakeBrain:
        return FakeBrain(clk, text=response_text, delay_ms=0)

    session = StreamingCallSession(
        ctx,
        transport=transport,
        stt=stt_port,
        turns=turns,
        tts=tts_port,
        brain_factory=brain_factory,
        policy=InterruptionPolicy(),
        tracer=StreamingCallTracer(call_id),
        clock=clk,
    )

    return StreamSimulation(
        call_id=call_id,
        contact_id=contact_id,
        media=media,
        barge_in=barge_in,
        session=session,
        transport=transport,
        clock=clk,
    )

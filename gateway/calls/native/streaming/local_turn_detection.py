"""Real ``TurnDetectionPort`` over Pipecat's bundled Silero VAD + Smart Turn v3.

This adapter converts inbound :class:`AudioFrame` s into :class:`TurnEvent` s
using local onnx models (no cloud, no download). It is opt-in and built only
when the ``simplex-streaming`` extra is installed.

IMPORTANT: this module must stay importable without Pipecat. There is **no
top-level ``import pipecat``** — the factory imports the Pipecat classes
lazily. The ``VADState``/``EndOfTurnState`` enums referenced inside
:meth:`LocalTurnDetector.observe` are imported in a guarded module-level block
that degrades to ``None`` when Pipecat is absent; a ``LocalTurnDetector`` is
only ever constructed when Pipecat is present (mocked tests import the real
enums), so ``observe`` always sees the real enums at runtime.
"""
from __future__ import annotations

from .pipecat_runtime import pipecat_available
from .types import AudioFrame, MediaFormat, TurnEvent, TurnEventKind

# Guarded enum import: keeps the module importable without the extra. When
# Pipecat is present these are the real enums; the detector is never
# constructed without Pipecat, so observe() always has the real enums.
try:  # pragma: no cover - exercised indirectly by the gates
    from pipecat.audio.turn.base_turn_analyzer import EndOfTurnState
    from pipecat.audio.vad.vad_analyzer import VADState
except Exception:  # pragma: no cover
    VADState = None  # type: ignore[assignment]
    EndOfTurnState = None  # type: ignore[assignment]

_SOURCE = "silero+smartturn-v3"


def _as_float(value) -> float:
    """Coerce a VAD confidence to a Python float.

    Pipecat's ``voice_confidence`` returns a 1-element numpy array on this
    version (not a 0-d scalar), so a bare ``float(...)`` raises. Index into
    array-likes before converting; fall back to ``float`` for plain numbers.
    """
    try:
        return float(value)
    except TypeError:
        return float(value.reshape(-1)[0])


class LocalTurnDetector:
    """A ``TurnDetectionPort`` backed by Silero VAD + Smart Turn v3.

    Analyzers are injected (the factory wraps the real ones) so the
    re-chunking/state-edge logic is unit-testable with mocks. Inbound frames
    are 20ms (640 bytes @16k); the VAD wants fixed windows of
    ``vad.num_frames_required()`` samples, so a rolling byte buffer re-chunks
    into ``num_frames_required() * 2``-byte windows.
    """

    def __init__(
        self,
        *,
        media: MediaFormat,
        vad,
        smart_turn,
        call_id: str = "",
    ) -> None:
        self._media = media
        self._vad = vad
        self._smart_turn = smart_turn
        self._call_id = call_id
        self._buffer = bytearray()
        self._prev_state = None
        # 16-bit PCM -> 2 bytes/sample.
        self._window_bytes = int(vad.num_frames_required()) * 2

    async def observe(self, frame: AudioFrame) -> tuple[TurnEvent, ...]:
        if frame.media.sample_rate != 16000 or frame.media.channels != 1:
            raise ValueError(
                "LocalTurnDetector requires 16kHz mono audio; got "
                f"sample_rate={frame.media.sample_rate}, channels={frame.media.channels}"
            )

        self._buffer.extend(frame.pcm16)
        events: list[TurnEvent] = []

        while len(self._buffer) >= self._window_bytes:
            window = bytes(self._buffer[: self._window_bytes])
            del self._buffer[: self._window_bytes]

            state = await self._vad.analyze_audio(window)
            is_speech = state in (VADState.STARTING, VADState.SPEAKING)

            if (
                self._prev_state in (None, VADState.QUIET, VADState.STARTING)
                and state == VADState.SPEAKING
            ):
                events.append(
                    TurnEvent(
                        call_id=self._call_id,
                        kind=TurnEventKind.USER_SPEECH_STARTED,
                        at_ms=frame.timestamp_ms,
                        vad_confidence=_as_float(self._vad.voice_confidence(window)),
                        source=_SOURCE,
                    )
                )
            elif self._prev_state == VADState.SPEAKING and state in (
                VADState.STOPPING,
                VADState.QUIET,
            ):
                events.append(
                    TurnEvent(
                        call_id=self._call_id,
                        kind=TurnEventKind.USER_SPEECH_STOPPED,
                        at_ms=frame.timestamp_ms,
                        source=_SOURCE,
                    )
                )

            self._prev_state = state

            eot = self._smart_turn.append_audio(window, is_speech)
            if eot == EndOfTurnState.COMPLETE:
                events.append(
                    TurnEvent(
                        call_id=self._call_id,
                        kind=TurnEventKind.ENDPOINT_DETECTED,
                        at_ms=frame.timestamp_ms,
                        source=_SOURCE,
                    )
                )

        return tuple(events)

    def reset(self) -> None:
        self._buffer.clear()
        self._prev_state = None
        self._smart_turn.clear()


def build_local_turn_detector(
    media: MediaFormat,
    *,
    call_id: str = "",
    vad_params=None,
    turn_params=None,
) -> LocalTurnDetector:
    """Construct a real ``LocalTurnDetector`` (requires the Pipecat extra)."""
    if not pipecat_available():
        raise RuntimeError(
            "LocalTurnDetector requires the optional Pipecat dependency. "
            "Install: pip install 'hermes-agent[simplex-streaming]'"
        )

    from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
    from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
        LocalSmartTurnAnalyzerV3,
    )
    from pipecat.audio.vad.silero import SileroVADAnalyzer

    vad = SileroVADAnalyzer(sample_rate=16000, params=vad_params)
    vad.set_sample_rate(16000)

    smart_turn = LocalSmartTurnAnalyzerV3(
        params=turn_params
        or SmartTurnParams(stop_secs=0.5, pre_speech_ms=200, max_duration_secs=8)
    )
    smart_turn.set_sample_rate(16000)

    return LocalTurnDetector(
        media=media, vad=vad, smart_turn=smart_turn, call_id=call_id
    )

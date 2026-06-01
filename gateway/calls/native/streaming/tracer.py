"""StreamingCallTracer — WP6 implementation.

Satisfies StreamingCallTracerPort by composing NativeCallTraceWriter
for redaction and file-backed JSONL tracing.  Raw text previews are
gated behind VoiceDebugTracePolicy and marked sensitive=True.
"""
from __future__ import annotations

from gateway.calls.native.tracing import NativeCallTraceWriter
from gateway.calls.native.voice_turn import VoiceDebugTracePolicy, _preview_text  # noqa: PLC2701

from .types import (
    BrainEvent,
    CallTurnRecord,
    InterruptionDecision,
    PlaybackMark,
    TranscriptEvent,
    TurnEvent,
)


class StreamingCallTracer:
    """StreamingCallTracerPort impl.  Reuses NativeCallTraceWriter redaction.

    Raw text previews are gated behind VoiceDebugTracePolicy and marked
    sensitive=True so the underlying writer can apply text-level redaction
    before the JSONL row is persisted.
    """

    def __init__(
        self,
        call_id: str,
        *,
        policy: VoiceDebugTracePolicy | None = None,
        writer: NativeCallTraceWriter | None = None,
    ) -> None:
        self._call_id = call_id
        self._policy = policy or VoiceDebugTracePolicy()
        self._writer = writer or NativeCallTraceWriter()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, event: str, **fields: object) -> None:
        self._writer.record(self._call_id, event, **fields)

    def _maybe_preview(self, text: str) -> dict[str, object]:
        """Return {'preview': ..., 'sensitive': True} only when previews enabled."""
        if not self._policy.transcript_previews:
            return {}
        return {
            "preview": _preview_text(text or "", self._policy.max_preview_chars),
            "sensitive": True,
        }

    # ------------------------------------------------------------------
    # StreamingCallTracerPort interface
    # ------------------------------------------------------------------

    def transcript(self, event: TranscriptEvent) -> None:
        self._emit(
            "stream_transcript",
            kind=event.kind.value,
            chars=len(event.text),
            stability=event.stability,
            provider=event.provider,
            **self._maybe_preview(event.text),
        )

    def turn(self, event: TurnEvent) -> None:
        self._emit(
            "stream_turn",
            kind=event.kind.value,
            at_ms=event.at_ms,
            speech_duration_ms=event.speech_duration_ms,
            vad_confidence=event.vad_confidence,
            endpoint_confidence=event.endpoint_confidence,
            source=event.source,
        )

    def brain(self, event: BrainEvent) -> None:
        self._emit(
            "stream_brain",
            kind=event.kind.value,
            chars=len(event.text),
            tool_name=event.tool_name,
            error_code=event.error_code,
            **self._maybe_preview(event.text),
        )

    def playback(self, mark: PlaybackMark) -> None:
        self._emit(
            "stream_playback",
            char_offset=mark.char_offset,
            at_ms=mark.at_ms,
            boundary=mark.boundary,
            **self._maybe_preview(mark.text_so_far),
        )

    def interruption(
        self,
        decision: InterruptionDecision,
        heard: str,
        abandoned: str,
    ) -> None:
        fields: dict[str, object] = dict(
            action=decision.action.value,
            reason=decision.reason,
            at_ms=decision.at_ms,
            heard_chars=len(heard),
            abandoned_chars=len(abandoned),
        )
        if self._policy.transcript_previews:
            fields["heard_preview"] = _preview_text(
                heard or "", self._policy.max_preview_chars
            )
            fields["abandoned_preview"] = _preview_text(
                abandoned or "", self._policy.max_preview_chars
            )
            fields["sensitive"] = True
        self._emit("stream_interruption", **fields)

    def turn_committed(self, record: CallTurnRecord) -> None:
        fields: dict[str, object] = dict(
            turn_index=record.turn_index,
            ended_reason=record.ended_reason.value,
            interrupted=record.interrupted,
            heard_chars=len(record.assistant_heard_text),
            abandoned_chars=len(record.assistant_abandoned_text),
            user_chars=len(record.user_transcript),
        )
        if self._policy.transcript_previews:
            fields["heard_preview"] = _preview_text(
                record.assistant_heard_text, self._policy.max_preview_chars
            )
            fields["abandoned_preview"] = _preview_text(
                record.assistant_abandoned_text, self._policy.max_preview_chars
            )
            fields["user_preview"] = _preview_text(
                record.user_transcript, self._policy.max_preview_chars
            )
            fields["sensitive"] = True
        self._emit("stream_turn_committed", **fields)

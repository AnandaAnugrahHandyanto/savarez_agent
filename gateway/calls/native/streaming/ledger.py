from __future__ import annotations

from .types import CallTurnRecord, FlushResult, PlaybackMark, TurnEndReason


class HeardSpanLedger:
    """Single source of truth for playback-aware truncation (spec D/E, constraint #6).

    Tracks the maximum char_offset confirmed played back to the caller (via
    PlaybackMarks emitted at word boundaries) and computes assistant_heard_text
    vs assistant_abandoned_text for the durable CallTurnRecord at turn end.
    """

    def __init__(self, call_id: str, turn_index: int = 0) -> None:
        self.call_id = call_id
        self.turn_index = turn_index
        self._last_offset: int = 0
        self._last_text: str = ""

    def note_mark(self, mark: PlaybackMark) -> None:
        """Record a playback mark; out-of-order (regressing) marks are ignored."""
        if mark.char_offset >= self._last_offset:
            self._last_offset = mark.char_offset
            self._last_text = mark.text_so_far

    def note_flush(self, flush: FlushResult, full_text: str) -> None:
        """Process a flush event; if flush carries a mark, advance the heard span."""
        if flush.last_sent_mark is not None:
            self.note_mark(flush.last_sent_mark)
        # A flush without a mark does not extend the heard span —
        # silence alone does not confirm playback of additional text.

    def record(
        self,
        *,
        user_transcript: str,
        full_text: str,
        reason: TurnEndReason,
    ) -> CallTurnRecord:
        """Compute and return the durable CallTurnRecord for this turn.

        Slicing approach: always use self._last_offset (not len(self._last_text))
        to index into full_text for the abandoned portion. This is robust against
        any case where text_so_far might not be a byte-identical prefix of full_text
        (e.g. encoding or normalisation differences), since the offset is the
        authoritative position from the TTS engine.
        """
        if reason is TurnEndReason.COMPLETED and self._last_offset == 0:
            # No marks recorded but call completed normally: the user heard everything.
            heard = full_text
            abandoned = ""
        else:
            heard = self._last_text if self._last_text else full_text[: self._last_offset]
            abandoned = (
                ""
                if reason is TurnEndReason.COMPLETED
                else full_text[self._last_offset :]
            )

        interrupted = reason in (TurnEndReason.BARGED_IN, TurnEndReason.FALSE_INTERRUPTION)

        return CallTurnRecord(
            call_id=self.call_id,
            turn_index=self.turn_index,
            user_transcript=user_transcript,
            assistant_heard_text=heard,
            assistant_abandoned_text=abandoned,
            interrupted=interrupted,
            ended_reason=reason,
        )

# Slice 5: Real Local TTS — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. TDD. Design: `docs/plans/2026-06-01-simplex-streaming-tts-design.md`.

**Goal:** `StreamingTTS` (a real `TextToSpeechPort`) over an injected `synthesize_pcm(text)->bytes` (16k mono): frame into 20ms AUDIO frames, emit word-boundary MARKs, barge-in → CANCELLED, DONE. Local Piper factory (resamples 22050→16000), tested locally; mock-backend tests in CI. `FakeTTS` stays default; no session/engine wiring.

**Validated facts:**
- `TextToSpeechPort.synthesize(text, ctx, scope) -> AsyncIterator[TtsAudioEvent]` (SYNC method returning an async generator — like `FakeTTS.synthesize` returns `self._gen(...)`); `async cancel()`, `async flush()`.
- `TtsAudioEvent(call_id, kind, frame, mark, span_text=, span_start_char=, span_end_char=)`; `TtsEventKind`: AUDIO/MARK/DONE/CANCELLED. `PlaybackMark(call_id, char_offset, text_so_far, at_ms, boundary="word")`.
- Session (verified) iterates synthesize(): AUDIO→`transport.emit_outbound(frame)` (NO pacing/sleep); MARK→`ledger.note_mark(mark)`; breaks on CANCELLED/DONE/`scope.cancelled`. Ledger uses char_offset as authoritative (≤ len; monotonic).
- no-walltime bans `time.*`/`asyncio.sleep` in streaming/**; `clock.now_ms()` + counters allowed. `Clock` protocol: `now_ms()`. `VirtualClock` exists for tests.
- Piper: `PiperVoice.synthesize(text)` yields `AudioChunk` (`.audio_int16_bytes`, `.sample_rate`); default voices 22050Hz. Project already uses piper (tools/tts_tool.py) but there is NO piper pin in pyproject/uv.lock.

---

## Task 1: Add `simplex-streaming-local-tts` extra + lock

**Files:** pyproject.toml, uv.lock.
- [ ] Step 1: `uv add --optional simplex-streaming-local-tts 'piper-tts'` (let uv resolve a concrete version), OR manually add `simplex-streaming-local-tts = ["piper-tts==<resolved>"]` then `uv lock`. Confirm the resolved version exposes `from piper import PiperVoice` and `voice.synthesize(text)` → AudioChunk. Not in `[all]`.
- [ ] Step 2: Verify `grep -A1 'name = "piper-tts"' uv.lock | head` shows the version; confirm `uv run --no-sync python -c "import importlib.util; print(importlib.util.find_spec('piper') is not None)"` after install.
- [ ] Step 3: Commit pyproject.toml + uv.lock — `build(streaming): add simplex-streaming-local-tts extra (piper-tts)`.

---

## Task 2: `StreamingTTS` + framing/marking/barge-in (TDD, mock backend)

**Files:** Create `gateway/calls/native/streaming/local_tts.py`; Create `tests/gateway/streaming/test_local_tts.py`.

Read first: ports.py (TextToSpeechPort), types.py (TtsAudioEvent/TtsEventKind/PlaybackMark/AudioFrame/MediaFormat/StreamingCallContext), fakes.py (FakeTTS pattern), clock.py (Clock/VirtualClock), cancellation.py (CancellationScope).

- [ ] Step 1: Write failing mock-backend tests (Scenarios 1–7). Build `StreamingCallContext` via its real fields (read types.py). Inject a fixed/virtual clock and a mock `synthesize_pcm(text)->bytes` returning a known 16k PCM blob (e.g. `b"\x00\x01"*N`). Use `CancellationScope()`; for barge-in set `scope.cancel("test")` partway (e.g. via a backend that the test cancels after first event — simplest: pre-cancel for scenario 3 variant, plus a mid-stream variant by cancelling inside the async iteration after the first AUDIO). Scenarios:
  1. mock returns M bytes → iterate: get ⌈M/640⌉ AUDIO frames (each 640 bytes except last padded), timestamps monotonic (clock_start, +20 each), then DONE. Concatenated AUDIO (minus final pad) == backend bytes.
  2. multi-word text "one two three four" → MARK events present; each MARK `text_so_far == text[:char_offset]`, is a word-prefix, `char_offset` monotonic non-decreasing ≤ len(text).
  3. mid-stream cancel: begin iterating; after first AUDIO, `scope.cancel("barge")`; next event is exactly one CANCELLED, then StopAsyncIteration; no DONE.
  4. `await tts.cancel()` before iterating → first/early event CANCELLED.
  5. empty text "" (backend returns b"") → DONE only, no AUDIO.
  6. mock records `threading.get_ident()`; assert != main-loop ident (proves to_thread offload).
  7. ctx.media non-16k (8000) or channels=2 → iterating raises ValueError "16kHz mono".
- [ ] Step 2: Run → red.
- [ ] Step 3: Implement `local_tts.py`:
  - No top-level piper/numpy import (numpy lazy if used for resample; the generic StreamingTTS needs no numpy — resampling is in the factory).
  - `class StreamingTTS:` `__init__(self, *, media, synthesize_pcm, clock, call_id="", frame_ms=20)`. Store; `_cancelled=False`.
    - `def synthesize(self, text, ctx, scope) -> AsyncIterator[TtsAudioEvent]: return self._gen(text, ctx, scope)` (sync returning the async gen).
    - `async def _gen(self, text, ctx, scope):`
      - guard `ctx.media.sample_rate==16000 and channels==1` else `raise ValueError("StreamingTTS requires 16kHz mono; got ...")`.
      - if pre-cancelled (`scope.cancelled or self._cancelled`): `yield CANCELLED; return`.
      - `pcm = await asyncio.to_thread(self._synthesize_pcm, text)` (offload). If empty → `yield DONE; return`.
      - `frame_bytes = int(16000*frame_ms/1000)*2` (640). `total=len(pcm)`. `t0=self._clock.now_ms()`. `seq=0`. `emitted=0`. `prev_off=0`.
      - precompute word-boundary char offsets of `text` (indices just past each word incl following space).
      - loop over pcm in frame_bytes chunks:
        - if `scope.cancelled or self._cancelled`: `yield CANCELLED; return`.
        - chunk = pcm[i:i+frame_bytes]; if short, pad with `b"\x00"*(frame_bytes-len)`.
        - `frame=AudioFrame(pcm16=chunk, media=ctx.media, timestamp_ms=t0+seq*frame_ms, seq=seq)`; `yield AUDIO(frame)`; `seq+=1`; `emitted+=len(chunk_unpadded)` (track real bytes).
        - compute proportional offset `prop=len(text)*emitted//total`; snap BACKWARD to last word-boundary ≤ prop; `off=max(prev_off, snapped)`; if `off>prev_off`: `yield MARK(PlaybackMark(call_id, char_offset=off, text_so_far=text[:off], at_ms=t0+ (seq-1)*frame_ms, boundary="word"))`; `prev_off=off`.
      - final: if `prev_off < len(text)`: emit a final MARK at len(text). `yield DONE`.
    - `async def cancel(self)`: `self._cancelled=True`.
    - `async def flush(self)`: no-op (pass).
  - `def build_piper_tts(media, *, clock=None, call_id="", voice=...) -> StreamingTTS:`
    - `from importlib.util import find_spec; if find_spec("piper") is None: raise RuntimeError("...install 'hermes-agent[simplex-streaming-local-tts]'")`.
    - lazy `from piper import PiperVoice`; load voice (mirror tools/tts_tool.py voice resolution/path). 
    - define `def _synthesize_pcm(text: str) -> bytes:` iterate `v.synthesize(text)` → collect `chunk.audio_int16_bytes`; read `sr=chunk.sample_rate` (first chunk); concat; if `sr!=16000`: resample int16 mono `sr`→16000 (use `audioop.ratecv(data, 2, 1, sr, 16000, None)[0]` — stdlib, no numpy). return 16k bytes.
    - `return StreamingTTS(media=media, synthesize_pcm=_synthesize_pcm, clock=clock or MonotonicClock(), call_id=call_id)`.
- [ ] Step 4: Run → green.
- [ ] Step 5: Commit — `feat(streaming): StreamingTTS framing/marking/barge-in over injected backend`.

---

## Task 3: Real-Piper contract test (Scenario 8)

**Files:** extend `tests/gateway/streaming/test_local_tts.py`.
- [ ] Step 1: Install locally: `uv pip install piper-tts` (first synth downloads a voice; allow time). Verify a short synth works.
- [ ] Step 2: Add, guarded `@pytest.mark.skipif(find_spec("piper") is None, reason="simplex-streaming-local-tts extra not installed")` (NOT @integration), async:
  ```python
  async def test_real_piper_contract():
      tts = build_piper_tts(M16)
      kinds=[]; audio_bytes=0; marks=[]
      async for e in tts.synthesize("Hello there friend.", ctx(), CancellationScope()):
          kinds.append(e.kind)
          if e.kind is TtsEventKind.AUDIO: audio_bytes += len(e.frame.pcm16)
          if e.kind is TtsEventKind.MARK: marks.append(e.mark)
      assert TtsEventKind.AUDIO in kinds and kinds[-1] is TtsEventKind.DONE
      assert audio_bytes > 0
      assert any(m.text_so_far and "Hello there friend.".startswith(m.text_so_far) for m in marks)
  ```
- [ ] Step 3: Run locally → pass. Commit — `test(streaming): real-Piper TTS contract`.

---

## Task 4: Gates
- [ ] ast-grep no-walltime over `local_tts.py` → clean (no time.*/asyncio.sleep; timestamps via clock+increment).
- [ ] `ruff check` + `ty check` on the new file → clean.
- [ ] Package imports without the extra: `uv run --no-sync python -c "import gateway.calls.native.streaming; print('ok')"`.
- [ ] Full streaming suite green.

---

## Done criteria
All scenarios pass; package imports without extra; gates clean; `FakeTTS` default unchanged; MARK text_so_far always a word-prefix. Then PR → CI → fix obvious → merge on green (real-Piper test skips in CI by design; modulo pre-existing `test_setup*` + `osv-scan`).

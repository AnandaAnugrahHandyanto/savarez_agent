# SimpleX Streaming Voice — Slice 5: Real TTS (Local) (Design)

> Status: DESIGN. Architecture **A — ports own the loop**. Delivers a real `TextToSpeechPort` (`StreamingTTS`) — the framing + word-boundary marking + mid-stream barge-in + DONE logic — over an injected synth backend, with a local **Piper** factory. Cloud (Cartesia Sonic, word-timestamp marks) is a deferred later slice. `FakeTTS` stays the default; cloud is never the only path.

## 1. Goal

`StreamingTTS`, a real `TextToSpeechPort` that takes an injected `synthesize_pcm(text) -> bytes` backend (16-bit mono PCM at a declared sample rate) and converts it into the port's event stream: chunk the PCM into 20ms `AUDIO` frames, interleave `MARK` events (`PlaybackMark` with word-boundary `char_offset`/`text_so_far`) so the heard-span ledger stays meaningful, check `scope.cancelled` between chunks → yield `CANCELLED` and stop (barge-in), and yield `DONE` at the end. Ship a real local `build_piper_tts()` factory (tested locally, skips where Piper absent) + deterministic mock-backend unit tests (run in CI). `FakeTTS` stays the default; no session/engine wiring.

## 2. Validated facts & constraints

- `TextToSpeechPort`: `synthesize(self, text, ctx: StreamingCallContext, scope: CancellationScope) -> AsyncIterator[TtsAudioEvent]` (sync method returning an async generator), `async cancel()`, `async flush()`.
- `TtsAudioEvent(call_id, kind, frame, mark, span_text, span_start_char, span_end_char)`; `TtsEventKind`: AUDIO, MARK, DONE, CANCELLED. `PlaybackMark(call_id, char_offset, text_so_far, at_ms, boundary)`.
- **Verified — session consumption** (`session.py`): the session iterates `synthesize()` and calls `transport.emit_outbound(frame)` for each AUDIO frame **with no pacing/sleep** — pacing/back-pressure is the transport's job. It checks `scope.cancelled` after each event. So the adapter must **not** sleep.
- **Verified — heard-span ledger** (`ledger.py`): MARKs advance the heard span; `text_so_far` must be a real **prefix** of `full_text` (snap char offsets to word boundaries; never emit a non-prefix).
- ast-grep `no-walltime` (streaming/**) bans `time.*`/`asyncio.sleep` but **allows** `clock.now_ms()` and derived counters. `AUDIO` frame `timestamp_ms` = an injected `Clock`-anchored start + `seq * frame_ms` increment (monotonic, deterministic in tests via an injected fixed-start clock; no sleeping).
- **Piper** is already the project's local TTS provider (`tools/tts_tool.py`, `piper-tts`, `PiperVoice` → raw 16-bit PCM). Pipecat bundles only cloud TTS. Cartesia is absent.
- `FakeTTS` (the default): per word → check `scope.cancelled` → CANCELLED; else emit `frames_per_word` AUDIO frames + a MARK with char_offset past the word + space; ends DONE. VirtualClock-driven.

## 3. Decisions

- **D1 — Backend & scope (Q1=c):** `StreamingTTS(*, media, synthesize_pcm, clock, call_id="", source_sample_rate=...)` takes an injected `synthesize_pcm(text) -> bytes`. The slice's real value is the framing/marking/barge-in/DONE logic, fully unit-tested in CI with a deterministic mock backend. A real local `build_piper_tts(...)` factory wires `PiperVoice` behind the seam (tested locally, `skipif(find_spec("piper") is None)`). **Defer cloud** (Cartesia) to a later slice; the deferred path will reuse the same event-emission code, supplying exact word-timestamp char offsets instead of proportional ones.
- **D2 — MARK / char_offset (Q2):** assign `char_offset` **proportional to cumulative PCM bytes emitted** (`char_offset ≈ len(text) * bytes_emitted / total_bytes`), then **snap forward to the next word boundary** so `text_so_far = text[:char_offset]` is always a real word-prefix (ledger invariant). Emit a MARK at least at each sentence/clause boundary (split the text); finer marks via the proportional snap. `char_offset` is clamped monotonic and ≤ len(text). Snapping forward biases to **not over-claiming** heard text (conservative for barge-in truncation). If a backend later provides word timestamps, the same MARK path accepts exact offsets.
- **D3 — Timing & no-walltime (Q3):** the adapter emits frames in a tight async loop with **no sleep** (the transport paces). `frame.timestamp_ms = clock.now_ms()` captured once at synthesis start, then `+= frame_ms` per emitted 20ms frame (monotonic; deterministic with an injected fixed clock). `seq` increments per frame.
- **D4 — Sample rate & framing:** the backend declares its PCM `source_sample_rate`. Frame to `ctx.media` (16k mono target). If `source_sample_rate != ctx.media.sample_rate`, resample (linear or via the same numpy approach as Slice 4; or require backends to emit at the target rate — prefer **require 16k mono** from the backend for this slice (YAGNI), assert/guard, defer resampling). 20ms frame = `sample_rate * 0.02 * 2` bytes; the final short remainder (< one frame) is emitted as a final padded/short AUDIO frame or dropped — choose: pad the last frame to full length with silence (keeps the transport happy).
- **D5 — Cancellation/cleanup (Q4):** check `scope.cancelled` before each chunk/frame-group; on cancel, yield a single `CANCELLED` event and `return` (no DONE). `cancel()` sets an internal flag the generator also checks (covers cancel() called out-of-band). `flush()` is a no-op for a finite generator. CPU-bound `synthesize_pcm` is offloaded via `asyncio.to_thread`.
- **D6 — Packaging/gating:** new extra `simplex-streaming-local-tts = ["piper-tts==<pin>"]` (parallel to `-local-stt`); not in `[all]`; add to `LAZY_DEPS` if that registry is used for TTS. **No config flag** this slice (no consumer yet — defer per Slice 4). `build_piper_tts` raises a clear `RuntimeError` naming the extra when `find_spec("piper")` is None; lazy import inside the factory; package stays importable without the extra. **Not** added to CI install (no model download in CI). `FakeTTS` stays default.

## 4. BDD scenarios

1. **Framing → AUDIO + DONE** (mock backend returns N bytes of PCM): `synthesize()` yields ⌈N/frame_bytes⌉ AUDIO frames (each `frame_ms`=20ms, 16k mono, `timestamp_ms` monotonic from the injected clock + seq*20), then a `DONE`. The concatenated AUDIO payload equals the backend PCM (modulo final-frame padding).
2. **MARKs are word-prefixes** (mock backend, multi-word text): MARK events appear; every MARK's `text_so_far == text[:char_offset]` and is a prefix of `text` ending at a word boundary; `char_offset` is monotonic non-decreasing and ≤ len(text); the final MARK (or DONE) reaches end-of-text.
3. **Barge-in mid-stream → CANCELLED** (scope cancelled after the first chunk): once `scope.cancelled` is set, the next iteration yields exactly one `CANCELLED` and stops; no DONE; no further AUDIO.
4. **cancel() out-of-band**: calling `await tts.cancel()` then iterating yields CANCELLED/stops promptly.
5. **Empty text → DONE only** (or CANCELLED if pre-cancelled): no AUDIO, immediate DONE; mock backend not called (or called with "" returning b"").
6. **CPU-bound backend offloaded**: the injected backend is invoked via a path that doesn't block the loop (assert by making the mock backend record the running thread != the test's main loop thread, or simply that an `await` occurs — pragmatic: assert the synth callable was called once with the text).
7. **16k-mono guard / sample-rate**: `synthesize` with `ctx.media` non-16k or backend `source_sample_rate` mismatch raises a clear `ValueError` (per D4's require-16k decision).
8. **Real Piper contract** (skipif find_spec("piper") None; local): `build_piper_tts()` synthesizes a short phrase; iterating yields AUDIO frames then DONE; total audio duration > 0; at least one MARK with a valid word-prefix. (Assert structure, not audio content.)

## 5. Files

- **Create:** `gateway/calls/native/streaming/local_tts.py` — `StreamingTTS(TextToSpeechPort)` + `build_piper_tts(...)`; injected `synthesize_pcm`; lazy Piper import; `asyncio.to_thread`; Clock-anchored timestamps.
- **Create:** `tests/gateway/streaming/test_local_tts.py` — mock-backend unit tests (1–7) + real-Piper contract (8, skipif).
- **Modify:** `pyproject.toml` — add `simplex-streaming-local-tts` extra (pin Piper to the project's existing piper version); `uv.lock` regen. (If LAZY_DEPS registers TTS providers, add the entry.)
- **Do NOT modify:** `.github/workflows/tests.yml` (real-Piper test skips in CI); `streaming/__init__.py` (no eager export).

## 6. Acceptance criteria

- All scenarios pass; mock-backend tests run in CI; real-Piper test runs locally (Piper installed) and skips cleanly in CI.
- Package imports without the `simplex-streaming-local-tts` extra (lazy import).
- ast-grep no-walltime / ruff / ty clean over the new file (no `time.*`/`asyncio.sleep`; timestamps via injected Clock + increment). `FakeTTS` stays the default; no session/engine change.
- Heard-span invariant honored: every MARK `text_so_far` is a real word-prefix of the text.
- `uv lock --check` consistent; CI shards green except the documented pre-existing `test_setup*` + private-fork `osv-scan`.

## 7. Out of scope (later slices)

- **Cartesia Sonic** cloud TTS (gated, word-timestamp marks) — later slice.
- Internal resampling (require 16k-mono backend now).
- Real aiortc transport (Slice 6), full E2E (Slice 7), live call (Slice 8).

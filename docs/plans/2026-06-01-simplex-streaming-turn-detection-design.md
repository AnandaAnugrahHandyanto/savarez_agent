# SimpleX Streaming Voice — Slice 3: Real Local Turn Detection (Design)

> Status: DESIGN. Architecture **A — ports own the loop**. This slice delivers a real `TurnDetectionPort` implementation backed by Pipecat's bundled Silero VAD + Smart Turn v3 (local onnx, CPU). Fakes remain the default; the real adapter is opt-in and built only when the `simplex-streaming` extra is installed.

## 1. Goal

Provide `LocalTurnDetector`, a real `TurnDetectionPort` that converts inbound `AudioFrame`s into `TurnEvent`s (speech started/stopped, endpoint detected) using Pipecat's bundled **Silero VAD** + **Smart Turn v3** onnx models — no cloud, no model download. Ship it behind the port with contract tests (real onnx on a committed speech fixture + fast mocked unit tests). **No engine/config wiring this slice** (YAGNI); the session's default stays `FakeTurnDetection`.

## 2. Empirically validated facts (this slice rests on these)

Verified locally against the installed pipecat 1.3.0:
- `SileroVADAnalyzer(sample_rate=16000)` then **`set_sample_rate(16000)`** (required — it initializes internal byte counts; constructing alone leaves `_vad_frames_num_bytes` unset).
  - **`async analyze_audio(buffer: bytes) -> VADState`** — **must be awaited**.
  - `num_frames_required() -> int` == **256 samples @16k** ⇒ a **512-byte** PCM16 window per call.
  - `VADState`: QUIET, STARTING, SPEAKING, STOPPING. `VADParams(confidence=0.7, start_secs=0.2, stop_secs=0.2, min_volume=0.6)`.
- `LocalSmartTurnAnalyzerV3(params=SmartTurnParams(...))` then **`set_sample_rate(16000)`**. Bundled weights at `pipecat/audio/turn/smart_turn/data/smart-turn-v3.2-cpu.onnx` (no download).
  - **`append_audio(buffer: bytes, is_speech: bool) -> EndOfTurnState`** — **synchronous** (do NOT await).
  - `EndOfTurnState`: COMPLETE, INCOMPLETE. `SmartTurnParams(stop_secs=3, pre_speech_ms=500, max_duration_secs=8)`.
  - With `SmartTurnParams(stop_secs=0.5)` and ≥~1s trailing silence, `COMPLETE` fires once at utterance end (validated: a `say`-generated clip + 2s silence → COMPLETE at ~3.3s).
- Our `AudioFrame` is **20ms = 320 samples = 640 bytes @16k**; the VAD window is 256 samples ⇒ **re-chunking required** (rolling byte buffer).
- A macOS `say` clip converted with `afconvert … -d LEI16@16000 -c 1` reliably drives the full VAD cycle QUIET→STARTING→SPEAKING→STOPPING (validated). This is the committed fixture source.

Port contract (unchanged): `TurnDetectionPort` — `async observe(frame: AudioFrame) -> tuple[TurnEvent, ...]`, `reset() -> None`. `TurnEvent(call_id, kind, at_ms, speech_duration_ms=0, vad_confidence=0.0, endpoint_confidence=0.0, source="")`. `TurnEventKind`: USER_SPEECH_STARTED, USER_SPEECH_STOPPED, ENDPOINT_DETECTED, POSSIBLE_BACKCHANNEL. `at_ms` derives from `frame.timestamp_ms` (no wall-clock — ast-grep no-walltime rule).

## 3. Decisions

- **D1 — Fixture:** commit one tiny real speech WAV (16k mono PCM16, ~2–3s) generated via macOS `say` + `afconvert`, plus appended trailing silence in-test. A real-onnx contract test feeds it through `LocalTurnDetector` and asserts the **event sequence** (not exact confidences, which can drift across CPUs). The test is **not** marked `integration` (the CI run filters `-m 'not integration'`, which would silently skip it); instead it is guarded by `pytest.mark.skipif(not pipecat_available())`. Fast **mocked-analyzer** unit tests cover re-chunking, state edges, and `reset()`.
- **D2 — Re-chunking & sample rate:** the adapter keeps a rolling `bytearray`; each `observe(frame)` appends `frame.pcm16` and, while ≥512 bytes buffered, slices 512-byte windows, `await`s `vad.analyze_audio(window)`, and calls `smart_turn.append_audio(window, is_speech)`. **Require 16k mono** — assert `frame.media.sample_rate == 16000 and channels == 1` (SimpleX media is resampled upstream); **no internal resampling** (YAGNI). `reset()` clears the buffer, calls `smart_turn.clear()`, and resets state.
- **D3 — Event mapping:**
  - `is_speech = vad_state in {STARTING, SPEAKING}`.
  - Track the previous VADState across `observe()` calls. Edge (prev ∈ {QUIET, STARTING}) → SPEAKING ⇒ emit `USER_SPEECH_STARTED` (fires only on the actual transition *into* SPEAKING, so repeated SPEAKING windows don't duplicate it; a QUIET→STARTING→QUIET flap that never reaches SPEAKING emits nothing).
  - Edge SPEAKING → (STOPPING or QUIET) ⇒ emit `USER_SPEECH_STOPPED`.
  - `append_audio(window, is_speech) == COMPLETE` ⇒ emit `ENDPOINT_DETECTED`.
  - **Confidence fields (honest about the 1.3.0 API):**
    - `vad_confidence`: populated via the **public** `vad.voice_confidence(window) -> float` called on the window that drives the `USER_SPEECH_STARTED` edge. Documented as the *per-window* confidence (approximate relative to the multi-window smoothed transition) — useful as a signal for the downstream `InterruptionPolicy`. Other events leave it at the default `0.0`.
    - `endpoint_confidence`: **left at default `0.0`** — `append_audio` returns only the `EndOfTurnState` enum; the endpoint probability is computed inside private `_process_speech_segment`/`_predict_endpoint` and is **not** exposed publicly in 1.3.0. Do **not** read private attributes. (Future: populate if Pipecat exposes it.)
  - `POSSIBLE_BACKCHANNEL` is **deferred** (no first-class signal in these APIs).
  - `at_ms` = `frame.timestamp_ms`; `source = "silero+smartturn-v3"`.
- **D4 — Construction & gating:** a factory `build_local_turn_detector(media, *, vad_params=None, turn_params=SmartTurnParams(stop_secs=0.5, …))` that raises a clear error when `pipecat_available()` is False. Construct VAD + Smart Turn, call `set_sample_rate(16000)` on both. The adapter imports Pipecat lazily (inside the factory / module-guarded) so importing the streaming package without the extra never fails.
- **D5 — Scope:** deliver `LocalTurnDetector` + factory + tests **only**. No `calls.native.streaming.turn_detector` config key, no engine/session wiring — that lands when an engine path actually selects a real detector. `FakeTurnDetection` stays the default for the deterministic session scenario tests.

## 4. BDD scenarios (given / when / then)

1. **Re-chunking** *(mocked VAD/SmartTurn — deterministic, no onnx)*
   - *Given* a `LocalTurnDetector` with mocked analyzers and 20ms (640-byte) frames,
   - *when* I `observe()` several frames,
   - *then* the VAD is fed exactly 512-byte windows and leftover bytes roll over to the next call (assert the window sizes passed to the mock).

2. **Speech-started/stopped edges** *(mocked VAD returning a scripted state sequence)*
   - *Given* the mocked VAD yields QUIET, STARTING, SPEAKING, SPEAKING, STOPPING, QUIET,
   - *when* frames are observed,
   - *then* exactly one `USER_SPEECH_STARTED` (on the →SPEAKING edge) and one `USER_SPEECH_STOPPED` (on the SPEAKING→ edge) are emitted, with `at_ms == frame.timestamp_ms`.

3. **Endpoint detected** *(mocked SmartTurn returning COMPLETE on a chunk)*
   - *Given* the mocked SmartTurn returns `EndOfTurnState.COMPLETE` for a window,
   - *when* that window is processed,
   - *then* an `ENDPOINT_DETECTED` event is emitted.

4. **Sample-rate guard**
   - *Given* a frame with `media.sample_rate != 16000` (or channels != 1),
   - *when* `observe()` is called,
   - *then* it raises a clear `ValueError` naming the 16k-mono requirement.

5. **reset() clears state**
   - *Given* a detector mid-utterance (buffered bytes, SPEAKING),
   - *when* `reset()` is called,
   - *then* the buffer is empty, `smart_turn.clear()` was invoked, and the next `observe()` starts fresh (a new →SPEAKING edge re-emits `USER_SPEECH_STARTED`).

6. **Real-onnx contract** *(skipif not pipecat_available; committed speech fixture)*
   - *Given* the committed `say`-generated speech WAV + appended trailing silence, fed as 20ms frames through a real `LocalTurnDetector`,
   - *when* the whole clip is observed,
   - *then* the emitted sequence contains `USER_SPEECH_STARTED` … `USER_SPEECH_STOPPED` … and at least one `ENDPOINT_DETECTED`, in that order (assert ordering/containment, not counts/confidences).

7. **Absent extra is safe**
   - *Given* `pipecat_available()` is False,
   - *when* `build_local_turn_detector(...)` is called,
   - *then* it raises a clear error instructing to install `simplex-streaming` — and merely importing the module never raises.

## 5. Files

- **Create:** `gateway/calls/native/streaming/local_turn_detection.py` — `LocalTurnDetector(TurnDetectionPort)` + `build_local_turn_detector(...)`; lazy Pipecat import; async `observe`, sync `reset`.
- **Create:** `tests/gateway/streaming/test_local_turn_detection.py` — mocked unit tests (Scenarios 1–5, 7) + the real-onnx contract test (Scenario 6, skipif-guarded).
- **Create:** `tests/gateway/streaming/fixtures/turn_detection/speech_16k_mono.wav` — committed fixture (generated once via `say`+`afconvert`; ~32–64KB). Include the generation command in the plan for reproducibility.
- **Modify (maybe):** `gateway/calls/native/streaming/__init__.py` — export `LocalTurnDetector`, `build_local_turn_detector` only if it doesn't force a Pipecat import at package import time (keep the import lazy; do **not** import the module at package top if that would pull Pipecat). Prefer **no** top-level export to keep the package importable without the extra; expose via the submodule path.

## 6. Acceptance criteria

- All 7 BDD scenarios have passing tests. Scenario 6 runs (not skips) in the CI `test` shard (the extra is installed there); skips cleanly where the extra is absent.
- Importing `gateway.calls.native.streaming` (the package) still works **without** the `simplex-streaming` extra (lazy Pipecat import).
- ast-grep **no-walltime** passes over the new file (`observe` uses only `frame.timestamp_ms` for time; no `time.*`/`asyncio.sleep`). (Note: `streaming-purity` scopes only `types.py`/`ports.py` and `frozen-dataclass` only `types.py`, so neither inspects `local_turn_detection.py` — no-walltime is the relevant guard here.) ruff + ty pass over the new file.
- `FakeTurnDetection` remains the default; no session/engine behavior changes; existing streaming tests stay green.
- CI shards green except the documented pre-existing `test_setup*` set and the private-fork `osv-scan`.

## 7. Out of scope (later slices)

- Selecting the real detector via config + wiring it into the session — a later slice (or Slice 7 E2E).
- Real STT (Slice 4), TTS (Slice 5), aiortc transport (Slice 6), full E2E barge-in (Slice 7), live call (Slice 8).
- `POSSIBLE_BACKCHANNEL` detection.

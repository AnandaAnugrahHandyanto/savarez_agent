# Slice 4: Real Local Streaming STT — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. TDD. Design: `docs/plans/2026-06-01-simplex-streaming-stt-design.md`.

**Goal:** `LocalWhisperSTT` (a real `SpeechToTextPort`) over local faster-whisper: buffer pushed audio, transcribe on `finalize()`, emit one `FINAL`, no partials. Behind the port with mocked unit tests (CI) + a real-ASR contract test (local, skipif). `FakeSTT` stays default; no session/engine wiring.

**Validated facts:**
- `SpeechToTextPort`: `async start(ctx)`, `async push(frame)`, `events()->AsyncIterator[TranscriptEvent]`, `async finalize()->TranscriptEvent|None`, `async cancel()`, `async close()`.
- `TranscriptEvent(call_id, kind, text, start_ms=0, end_ms=0, stability=1.0, words=(), provider="")`; `TranscriptKind.FINAL`.
- Session reads the FINAL from `finalize()` return; `events()` only updates `_latest_partial` (tolerates empty). So empty `events()` is safe.
- faster-whisper `WhisperModel.transcribe(audio, language="en")` accepts an **in-memory float32 numpy array** (no temp WAV). int16→float32: `np.frombuffer(buf, np.int16).astype(np.float32)/32768.0`. numpy is present via pipecat.
- Fixture reused: `tests/gateway/streaming/fixtures/turn_detection/speech_16k_mono.wav` ("Hello Hermes, what is the weather forecast for today?").

---

## Task 1: Add `simplex-streaming-local-stt` extra + lock

**Files:** `pyproject.toml`, `uv.lock`.

- [ ] Step 1: Add extra near the other call extras:
  ```toml
  # Local streaming STT for SimpleX voice (opt-in; heavy: ctranslate2+onnxruntime).
  simplex-streaming-local-stt = ["faster-whisper==1.2.1"]
  ```
  Not in `[all]`.
- [ ] Step 2: `uv lock`. Verify: `grep -A1 'name = "faster-whisper"' uv.lock | head` shows 1.2.1.
- [ ] Step 3: Commit `pyproject.toml uv.lock` — `build(streaming): add simplex-streaming-local-stt extra (faster-whisper==1.2.1)`.

---

## Task 2: `LocalWhisperSTT` + factory (TDD, mocked transcriber)

**Files:** Create `gateway/calls/native/streaming/local_whisper_stt.py`; Create `tests/gateway/streaming/test_local_whisper_stt.py`.

Read first: ports.py (SpeechToTextPort), types.py (TranscriptEvent/TranscriptKind/AudioFrame/MediaFormat), fakes.py (FakeSTT), pipecat_runtime.py (pattern for the absent-extra guard).

- [ ] Step 1: Write failing mocked tests (Scenarios 1–5, 7). The detector takes an **injected** `transcribe` callable for testing: `transcribe(audio: "np.ndarray") -> str` (the adapter wraps the real `WhisperModel.transcribe` to return joined segment text). Sketch:
  ```python
  import pytest
  from gateway.calls.native.streaming.local_whisper_stt import LocalWhisperSTT, build_local_whisper_stt
  from gateway.calls.native.streaming.types import AudioFrame, MediaFormat, StreamingCallContext, TranscriptKind
  M16 = MediaFormat(sample_rate=16000, channels=1, frame_ms=20)
  pytestmark = pytest.mark.asyncio
  def frame(seq, ms, nbytes=640): return AudioFrame(pcm16=b"\x01\x02"*(nbytes//2), media=M16, timestamp_ms=ms, seq=seq)
  def ctx(): return StreamingCallContext(call_id="c1", contact_id="x", session_id="s", media=M16, interruption=..., endpoint=..., debug=...)  # build via the real dataclass defaults; inspect types.py for required fields
  ```
  Tests:
  1. push 3 frames, `finalize()` → injected transcribe received a numpy array whose length == total samples; result is one FINAL TranscriptEvent (kind FINAL, text==mock text, provider=="faster-whisper", start_ms==first frame ms, end_ms==last frame ms).
  2. `finalize()` with nothing pushed → None (transcribe not called).
  3. `events()`: `async for _ in stt.events(): pytest.fail(...)` — yields nothing.
  4. push, `cancel()`, then `finalize()` → None (buffer cleared); `close()` does not raise.
  5. `build_local_whisper_stt()` with faster-whisper unavailable (monkeypatch the availability check False) → RuntimeError matching "simplex-streaming-local-stt".
  7. `push()` of an 8000Hz (and a 2-channel) frame → ValueError matching "16kHz mono".
  Use a plain function/Mock for the injected transcribe. For Scenario 1 assert the numpy array dtype float32 and values in [-1,1].
- [ ] Step 2: Run → red.
- [ ] Step 3: Implement `local_whisper_stt.py`:
  - No top-level `import faster_whisper`. `import numpy as np` at top is fine (numpy always present via pipecat/the stack) — but to keep the streaming package importable in a truly numpy-less env, prefer importing numpy **inside** `finalize()` (lazy). (Confirm numpy import at package import doesn't break the no-extra import test; if numpy is guaranteed present, top-level is acceptable — choose lazy to be safe.)
  - `class LocalWhisperSTT:` `__init__(self, *, media: MediaFormat, transcribe, call_id: str = "")` storing `transcribe` (callable: np.ndarray->str), a `bytearray` buffer, `_first_ms=None`, `_last_ms=None`.
    - `async def start(self, ctx)`: store `call_id` from ctx if not set; no-op otherwise.
    - `async def push(self, frame)`: guard `frame.media.sample_rate==16000 and channels==1` else ValueError; append `frame.pcm16`; track first/last `timestamp_ms`.
    - `async def events(self)`: `return; yield` (empty async generator) — i.e. `if False: yield`.
    - `async def finalize(self)`: if buffer empty → None. Else lazy `import numpy as np`; `audio = np.frombuffer(bytes(self._buffer), np.int16).astype(np.float32)/32768.0`; `text = self._transcribe(audio)`; build FINAL TranscriptEvent(call_id, kind=FINAL, text=text.strip(), start_ms=self._first_ms or 0, end_ms=self._last_ms or 0, provider="faster-whisper"); return it. (Do NOT clear buffer here unless the port contract requires single-use; keep simple: clear after finalize.)
    - `async def cancel(self)`: clear buffer + first/last.
    - `async def close(self)`: clear buffer; drop transcribe/model ref.
  - `def build_local_whisper_stt(media, *, call_id="", model="distil-small.en", device="cpu", compute_type="int8") -> LocalWhisperSTT:`
    - availability check: `from importlib.util import find_spec; if find_spec("faster_whisper") is None: raise RuntimeError("LocalWhisperSTT requires the optional faster-whisper dependency. Install: pip install 'hermes-agent[simplex-streaming-local-stt]'")`
    - lazy `from faster_whisper import WhisperModel`; `m = WhisperModel(model, device=device, compute_type=compute_type)`.
    - define `def _transcribe(audio): segments, _info = m.transcribe(audio, language="en"); return " ".join(s.text for s in segments)`.
    - return `LocalWhisperSTT(media=media, transcribe=_transcribe, call_id=call_id)`.
- [ ] Step 4: Run → green.
- [ ] Step 5: Commit — `feat(streaming): LocalWhisperSTT over local faster-whisper`.

---

## Task 3: Real-ASR contract test (Scenario 6)

**Files:** extend `tests/gateway/streaming/test_local_whisper_stt.py`.

- [ ] Step 1: To run this locally, install faster-whisper: `uv pip install faster-whisper==1.2.1` (first `transcribe` downloads distil-small.en, ~150MB — local only).
- [ ] Step 2: Add, guarded by `@pytest.mark.skipif(find_spec("faster_whisper") is None, reason="simplex-streaming-local-stt extra not installed")` (NOT @integration):
  ```python
  from importlib.util import find_spec
  import wave
  from pathlib import Path
  FIX = Path(__file__).parent / "fixtures" / "turn_detection" / "speech_16k_mono.wav"

  @pytest.mark.skipif(find_spec("faster_whisper") is None, reason="...")
  async def test_real_asr_contract_transcribes_fixture():
      w = wave.open(str(FIX), "rb"); pcm = w.readframes(w.getnframes()); w.close()
      stt = build_local_whisper_stt(M16, call_id="real")
      await stt.start(ctx())
      for seq, off in enumerate(range(0, len(pcm) - 640, 640)):
          await stt.push(frame_from(seq, seq*20, pcm[off:off+640]))
      final = await stt.finalize()
      assert final is not None
      norm = "".join(c.lower() if c.isalnum() or c.isspace() else " " for c in final.text)
      norm = " ".join(norm.split())
      assert "weather" in norm and "today" in norm and ("hermes" in norm or "forecast" in norm)
  ```
- [ ] Step 3: Run locally → passes (after install). Commit — `test(streaming): real-ASR local STT contract on speech fixture`.

---

## Task 4: Gates

- [ ] ast-grep no-walltime over `local_whisper_stt.py` → clean.
- [ ] `ruff check` + `ty check` on the new file → clean.
- [ ] Package imports without the extra: `uv run --no-sync python -c "import gateway.calls.native.streaming; print('ok')"`.
- [ ] Full streaming suite: `uv run --no-sync python -m pytest tests/gateway/streaming/ -q` → all pass (real-ASR runs locally since faster-whisper now installed; would skip in CI).

---

## Done criteria
All scenarios pass; package imports without the extra; gates clean; `FakeSTT` default unchanged. Then finish-branch: PR → CI → fix obvious issues → merge on green (modulo documented pre-existing `test_setup*` + `osv-scan`; the real-ASR test SKIPS in CI by design).

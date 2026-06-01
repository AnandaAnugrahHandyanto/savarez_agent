# SimpleX Streaming Voice — Slice 2: Pipecat Dependency Foundation (Design)

> Status: DESIGN (awaiting plan). Part of the multi-slice "real streaming voice → live iPhone round trip" effort. Architecture decision **A — Ports own the loop** (Pipecat is a parts library, never the runtime) holds across all slices.

## 1. Goal

Make Pipecat an **installable, importable, conflict-free optional dependency**, and turn the STREAMING engine seam from "raises `PipecatIntegrationDeferred`" into "constructs a real (fake-backed) `StreamingCallSession` that runs end-to-end in simulation." No real audio, STT, TTS, or VAD in this slice.

This de-risks the single biggest unknown that caused Slice 1 to defer Pipecat (dependency conflict) and establishes a verifiable streaming seam that later slices fill in one real port at a time.

## 2. Background / empirical facts

- `pipecat-ai==1.3.0` **resolves cleanly** against the locked deps on Python 3.11 (verified via `uv pip install --dry-run`). It aligns `onnxruntime` to `1.24.4` (the already-locked version; satisfies `faster-whisper==1.2.1`) and adds ~17 transitive deps (numba, llvmlite, scipy, resampy, soxr, nltk, joblib, pyloudnorm, loguru, sympy, regex, pillow, markdown, mpmath, wait-for2). `aiortc==1.14.0` / `av==16.1.0` are untouched and satisfy Pipecat's `webrtc` extra bound.
- Pipecat 1.3.0 makes `onnxruntime~=1.24.3` a **base** dependency and **bundles** Silero VAD + Smart Turn v3 ONNX weights (no torch). This makes the local turn-detection path (Slice 3) feasible on Python 3.11.
- `gateway/calls/native/streaming/` already provides `StreamingCallSession`, the 7 hexagonal ports, frozen-dataclass events, a deterministic `VirtualClock`, complete fakes (`fakes.py`), and `simulate.py::build_stream_simulation()` which wires all 7 fakes into a real session.
- The engine selector `select_call_engine(config)` returns `"turn_based"` (default) or `"streaming"`. `build_native_pipeline()`'s streaming branch currently calls `pipecat_transport.build_pipeline()` → raises `PipecatIntegrationDeferred`. `test_pipecat_smoke.py` is import-skipped and asserts nothing real.

## 3. Decisions

### D1 — Packaging: new dedicated, pinned extra
Add `simplex-streaming = ["pipecat-ai==1.3.0"]` as a **new optional extra**, separate from `simplex-native-calls`.
- **Not** in `[all]` — the documented `[all]` policy excludes opt-in backend deps so a single quarantined PyPI release can't break every fresh install; Pipecat's 17-dep footprint is exactly that risk.
- **Not** folded into `simplex-native-calls` — that extra is the raw WebRTC media wire (aiortc/aioice/av); Pipecat is a streaming-orchestration library layered above, with a different blast radius and lifecycle. Keeping them separate lets a media-only user avoid scipy/numba.
- **Exact pin** `==1.3.0`, matching sibling extras (`aiortc==1.14.0`, `faster-whisper==1.2.1`) for reproducible locks (CI `uv lock --check`).
- Provider extras (`deepgram`, `cartesia`) are **deferred to slices 4/5** (YAGNI; no test exercises them yet).

### D2 — Live streaming path stays deferred; deferral becomes availability-aware
**Correctness constraint (do not break the live path):** `build_native_pipeline()`'s result is consumed by the **live** sidecar in `aiortc_engine.py` as a `pipeline_factory` whose product must expose `process_pcm16(call_id=…, pcm16=…, sample_rate=…)` (see `aiortc_engine.py` `peer.start(...)`). `StreamingCallSession` exposes a driven `run()` loop, **not** `process_pcm16`. Therefore Slice 2 must **not** make the streaming branch return a `StreamingCallSession` — doing so would replace a loud, early `PipecatIntegrationDeferred` with a runtime `AttributeError` deep in the live media loop. The real `process_pcm16`-shaped streaming pipeline (the aiortc↔session bridge) is **Slice 6**.

What Slice 2 changes about the seam (small, honest):
- The streaming branch of `build_native_pipeline()` **still raises** when the real transport isn't wired — the live streaming path remains deferred until Slice 6.
- It becomes **availability-aware** using the D3 probe: if the `simplex-streaming` extra (Pipecat) is **not installed**, raise a clear, distinct error instructing the user to install it; if Pipecat **is** installed but the transport bridge isn't wired yet, raise the existing `PipecatIntegrationDeferred` (now meaning "dependency present, integration lands in Slice 6").
- `select_call_engine` is unchanged: `turn_based` remains the default; the proven turn-based live path is untouched.

The fake-backed `StreamingCallSession` already runs end-to-end **in simulation** via `build_stream_simulation()` (which returns a `StreamSimulation` whose **caller owns the drive loop**: start `session.run()`, push frames, advance the `VirtualClock`, `end_inbound()`, await). That simulation path predates this slice and is **Pipecat-independent**; Slice 2 keeps a regression test over it (reusing the existing driver in `test_stream_simulation.py`) but does **not** route the live engine through it.

### D3 — Single truthful Pipecat import point
Add `gateway/calls/native/streaming/pipecat_runtime.py` exposing:
- `pipecat_available() -> bool` — performs the `import pipecat` **inside the function** (so tests can simulate absence by patching), wrapped in try/except; never raises.
- `pipecat_version() -> str | None` — returns the installed version via `importlib.metadata.version("pipecat-ai")` (the **distribution** name, not the import name `pipecat`), wrapped in try/except for `PackageNotFoundError`; returns `None` when absent; never raises.

This gives the smoke test, the availability-aware deferral (D2), and later slices one place to probe Pipecat rather than scattering `try/import` blocks.

## 4. BDD scenarios (given / when / then)

1. **Pipecat present** *(runs only where the `simplex-streaming` extra is installed)*
   - *Given* the `simplex-streaming` extra is installed,
   - *when* I call `pipecat_available()` and `pipecat_version()`,
   - *then* `pipecat_available()` is `True` and `pipecat_version() == "1.3.0"`.

2. **Pipecat absent is safe** *(deterministic everywhere via patched import)*
   - *Given* the Pipecat import is patched to raise `ImportError` (simulating the extra not installed),
   - *when* I call the probe functions,
   - *then* `pipecat_available()` is `False`, `pipecat_version()` is `None`, and neither raises.

3. **Streaming live path: clear error when extra missing**
   - *Given* config `calls.native.engine = "streaming"` and Pipecat **not** available (probe patched False),
   - *when* `build_native_pipeline()` is invoked,
   - *then* it raises an error whose message instructs installing the `simplex-streaming` extra.

4. **Streaming live path: deferred when extra present (transport is Slice 6)**
   - *Given* config `calls.native.engine = "streaming"` and Pipecat available (probe patched True),
   - *when* `build_native_pipeline()` is invoked,
   - *then* it raises `PipecatIntegrationDeferred` (dependency present; the real `process_pcm16` aiortc bridge lands in Slice 6) — it does **not** return a `StreamingCallSession`.

5. **Turn-based default preserved**
   - *Given* config with no `calls.native.engine` (or `turn_based`),
   - *when* `build_native_pipeline()` is invoked,
   - *then* it returns the legacy turn-based pipeline (unchanged behavior).

6. **Fake-backed simulation still runs deterministically (Pipecat-independent regression guard)**
   - *Given* a `StreamSimulation` built by `build_stream_simulation()` and driven by the existing driver,
   - *when* one simulated turn is driven (push frames, advance `VirtualClock`, `end_inbound`, await),
   - *then* it completes a full user→brain→TTS→DONE turn with no wall-clock sleeps. (This path does not import Pipecat; the test guards that the streaming seam keeps working.)

## 5. Files

- **Modify:** `pyproject.toml` — add `simplex-streaming = ["pipecat-ai==1.3.0"]` extra (not in `[all]`). `uv.lock` — regenerate (`uv lock`), commit.
- **Create:** `gateway/calls/native/streaming/pipecat_runtime.py` — `pipecat_available()` (import inside function, never raises), `pipecat_version()` (via `importlib.metadata.version("pipecat-ai")`, never raises).
- **Modify:** `gateway/calls/native/streaming/engine.py` — streaming branch becomes availability-aware: raise a clear "install `simplex-streaming`" error when `pipecat_available()` is False; otherwise raise the existing `PipecatIntegrationDeferred`. Must **not** return a `StreamingCallSession` (live consumer needs `process_pcm16`, added in Slice 6).
- **Keep:** `gateway/calls/native/streaming/pipecat_transport.py` — documented real-transport seam for Slice 6; `build_pipeline()` keeps raising `PipecatIntegrationDeferred`.
- **Replace:** `tests/gateway/streaming/test_pipecat_smoke.py` — Scenario 1 (real import + `version == "1.3.0"`), guarded so it runs where the extra is installed; Scenario 2 (patched-absence → probe False/None, no raise).
- **Modify (retire stale test):** `tests/gateway/streaming/test_engine_selection.py` — the existing `test_engine_build_pipeline_streaming_raises_deferred` must be **rewritten** to the new availability-aware behavior (Scenarios 3 & 4); add/keep the turn_based-default test (Scenario 5).
- **Keep/extend:** `tests/gateway/streaming/test_stream_simulation.py` — reuse its existing driver for Scenario 6 (do not write a second drive loop).

### CI install note (A3)
The default CI `test` shards install `.[all,dev]`, which does **not** include `simplex-streaming`. To actually verify Pipecat installs/imports cleanly and to make Scenario 1 run, the plan updates `.github/workflows/tests.yml` to install `.[all,dev,simplex-streaming]` for the `test` shards. The locked `onnxruntime==1.24.4` is unchanged by adding the extra (it already satisfies Pipecat's `~=1.24.3`), so this does not perturb `faster-whisper` or other tests. Scenario 2 stays deterministic everywhere via the patched-import technique (independent of whether the extra is installed).

## 6. Acceptance criteria

- `uv lock` resolves with Pipecat in the new `simplex-streaming` extra; `uv lock --check` passes in CI; the locked `onnxruntime` stays `1.24.4` (capture this from `uv.lock` as the verification artifact).
- `pip install -e ".[simplex-streaming]"` imports Pipecat 1.3.0 with no conflict.
- All 6 BDD scenarios have passing tests; Scenario 1 runs (not skipped) in the CI shard that installs the extra; Scenario 2 passes everywhere.
- The live streaming path does **not** return a non-conforming object: streaming `build_native_pipeline()` still raises (clear-error or `PipecatIntegrationDeferred`), never an object lacking `process_pcm16`.
- ast-grep streaming-purity / no-walltime / frozen-dataclass rules, ruff, and ty all pass.
- The CI `test` shards stay green (no new failures beyond the documented pre-existing `test_setup*` set).
- `turn_based` remains the default; the live turn-based path is behaviorally unchanged.

## 7. Out of scope (later slices)

- Real Silero VAD + Smart Turn v3 behind `TurnDetectionPort` — **Slice 3**.
- Real Deepgram Flux STT behind `SpeechToTextPort` (gated, cloud) — **Slice 4**.
- Real Cartesia Sonic TTS behind `TextToSpeechPort` (gated, cloud) — **Slice 5**.
- Real aiortc media bridge behind `AudioTransportPort` — **Slice 6**.
- Full simulated E2E with barge-in across real ports — **Slice 7**.
- Live iPhone round trip + gap fixes (weather tool, STT normalization) — **Slice 8**.

# Slice 2: Pipecat Dependency Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pipecat-ai` an installable, importable, conflict-free optional dependency, add a truthful Pipecat probe, and make the engine STREAMING seam availability-aware — without breaking the live consumer (which needs `process_pcm16`) and without real STT/TTS/VAD/transport.

**Architecture:** "Ports own the loop." Pipecat is a parts library for later slices. Slice 2 only adds the dependency + a probe + an availability-aware deferral. The live streaming path stays deferred until Slice 6 (the `process_pcm16` aiortc bridge).

**Tech Stack:** Python 3.11, uv, pytest (+ pytest-asyncio, pytest-split), pipecat-ai 1.3.0, ast-grep, ruff, ty.

Design: `docs/plans/2026-06-01-simplex-streaming-pipecat-foundation-design.md`.

---

## Task 1: Add the `simplex-streaming` optional extra + lock

**Files:**
- Modify: `pyproject.toml` (`[project.optional-dependencies]`)
- Modify: `uv.lock`

- [ ] **Step 1:** Add a new extra near the other call extras:
  ```toml
  # SimpleX streaming voice orchestration library (opt-in; NOT in [all] per
  # the [all] policy — large transitive footprint). Real STT/TTS/VAD land in
  # later slices behind the existing streaming ports.
  simplex-streaming = ["pipecat-ai==1.3.0"]
  ```
  Do **not** add it to `[all]`. Do **not** add provider extras (deepgram/cartesia) — deferred to slices 4/5.
- [ ] **Step 2:** Regenerate the lock: `uv lock`
- [ ] **Step 3:** Verify the lock resolved Pipecat and kept onnxruntime at 1.24.4:
  Run: `grep -A2 'name = "pipecat-ai"' uv.lock | head; grep -m1 -A1 'name = "onnxruntime"' uv.lock`
  Expected: pipecat-ai 1.3.0 present; onnxruntime version line shows `1.24.4`.
- [ ] **Step 4:** Verify install + import in a throwaway resolution:
  Run: `uv pip install --dry-run -e ".[simplex-streaming]" 2>&1 | tail -5`
  Expected: resolves with no conflict error.
- [ ] **Step 5:** Commit.
  ```bash
  git add pyproject.toml uv.lock
  git commit -m "build(streaming): add simplex-streaming extra (pipecat-ai==1.3.0)"
  ```

---

## Task 2: `pipecat_runtime.py` probe (TDD)

**Files:**
- Create: `gateway/calls/native/streaming/pipecat_runtime.py`
- Create: `tests/gateway/streaming/test_pipecat_runtime.py`

- [ ] **Step 1: Write failing tests.**
  ```python
  # test_pipecat_runtime.py
  import builtins
  import pytest
  from gateway.calls.native.streaming import pipecat_runtime as pr


  def test_absent_is_safe(monkeypatch):
      # Force the in-function import to fail, simulating the extra not installed.
      real_import = builtins.__import__

      def fake_import(name, *args, **kwargs):
          if name == "pipecat" or name.startswith("pipecat."):
              raise ImportError("simulated missing pipecat")
          return real_import(name, *args, **kwargs)

      monkeypatch.setattr(builtins, "__import__", fake_import)
      monkeypatch.setattr(pr, "_distribution_version", lambda _name: None)
      assert pr.pipecat_available() is False
      assert pr.pipecat_version() is None  # must not raise


  @pytest.mark.skipif(not pr.pipecat_available(), reason="simplex-streaming extra not installed")
  def test_present_reports_version():
      assert pr.pipecat_available() is True
      assert pr.pipecat_version() == "1.3.0"
  ```
- [ ] **Step 2: Run to verify failure.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/test_pipecat_runtime.py -q`
  Expected: FAIL/ERROR (module `pipecat_runtime` does not exist).
- [ ] **Step 3: Implement.**
  ```python
  # gateway/calls/native/streaming/pipecat_runtime.py
  """Single truthful probe for the optional Pipecat dependency.

  Pipecat ships in the opt-in ``simplex-streaming`` extra. These helpers let
  callers (the engine deferral, the smoke test, and later slices) check
  availability without scattering try/import blocks. Neither helper raises.
  """
  from __future__ import annotations

  from importlib.metadata import PackageNotFoundError, version as _pkg_version

  # Distribution name on PyPI (import name is ``pipecat``).
  _DISTRIBUTION = "pipecat-ai"


  def _distribution_version(name: str) -> str | None:
      try:
          return _pkg_version(name)
      except PackageNotFoundError:
          return None


  def pipecat_available() -> bool:
      """True iff ``import pipecat`` succeeds. Import is inside the function so
      tests can simulate absence by patching ``builtins.__import__``."""
      try:
          import pipecat  # noqa: F401
      except Exception:
          return False
      return True


  def pipecat_version() -> str | None:
      """Installed Pipecat version, or None when absent. Never raises."""
      return _distribution_version(_DISTRIBUTION)
  ```
- [ ] **Step 4: Run tests to verify pass.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/test_pipecat_runtime.py -q`
  Expected: PASS (the `present` test may SKIP if the extra isn't installed locally — acceptable; CI installs it).
- [ ] **Step 5: Commit.**
  ```bash
  git add gateway/calls/native/streaming/pipecat_runtime.py tests/gateway/streaming/test_pipecat_runtime.py
  git commit -m "feat(streaming): pipecat runtime probe (available/version)"
  ```

---

## Task 3: Availability-aware streaming deferral in engine.py (TDD)

**Files:**
- Modify: `gateway/calls/native/streaming/engine.py`
- Modify: `tests/gateway/streaming/test_engine_selection.py` (rewrite the stale `*_raises_deferred` test)

Context: read `engine.py` first. `build_native_pipeline(config, *, turn_based_factory)` currently: streaming → `pipecat_transport.build_pipeline(config=config)` (raises `PipecatIntegrationDeferred`); else → `turn_based_factory()`. The streaming branch must become availability-aware and must **never** return a `StreamingCallSession` (the live consumer needs `process_pcm16`, added in Slice 6). Define a clear error type for the missing-extra case (e.g. reuse a `RuntimeError` subclass or a new `StreamingExtraNotInstalled` exception in `engine.py`).

- [ ] **Step 1: Write/rewrite failing tests.** Replace `test_engine_build_pipeline_streaming_raises_deferred` with:
  ```python
  import pytest
  from gateway.calls.native.streaming import engine as eng
  from gateway.calls.native.streaming.ports import CallTurnCancelled  # if needed
  from gateway.calls.native.streaming.pipecat_transport import PipecatIntegrationDeferred


  def _streaming_cfg():
      return {"calls": {"native": {"engine": "streaming"}}}


  def test_streaming_missing_extra_raises_clear_error(monkeypatch):
      monkeypatch.setattr(eng, "pipecat_available", lambda: False)
      with pytest.raises(eng.StreamingExtraNotInstalled) as ei:
          eng.build_native_pipeline(_streaming_cfg(), turn_based_factory=lambda: object())
      assert "simplex-streaming" in str(ei.value)


  def test_streaming_present_defers_until_transport(monkeypatch):
      monkeypatch.setattr(eng, "pipecat_available", lambda: True)
      with pytest.raises(PipecatIntegrationDeferred):
          eng.build_native_pipeline(_streaming_cfg(), turn_based_factory=lambda: object())


  def test_turn_based_default_returns_factory_product():
      sentinel = object()
      result = eng.build_native_pipeline({}, turn_based_factory=lambda: sentinel)
      assert result is sentinel
  ```
- [ ] **Step 2: Run to verify failure.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/test_engine_selection.py -q`
  Expected: FAIL (`StreamingExtraNotInstalled` undefined / streaming branch doesn't check availability).
- [ ] **Step 3: Implement.** In `engine.py` (current streaming branch is `engine.py:67-72`: a function-body `from ...pipecat_transport import build_pipeline` then `if engine == STREAMING: return build_pipeline(config=config)`):
  - Add a **module-top** import of the probe (by name, so the test's `monkeypatch.setattr(eng, "pipecat_available", ...)` works):
    `from gateway.calls.native.streaming.pipecat_runtime import pipecat_available`
  - Add exception (module scope):
    ```python
    class StreamingExtraNotInstalled(RuntimeError):
        """Raised when engine=streaming but the simplex-streaming extra is absent."""
    ```
  - Rewrite the streaming branch (keep the existing **by-name** `build_pipeline` function-body import — do NOT use `pipecat_transport.build_pipeline`, that name isn't bound):
    ```python
    if engine == STREAMING:
        if not pipecat_available():
            raise StreamingExtraNotInstalled(
                "calls.native.engine='streaming' requires the optional Pipecat "
                "dependency. Install it with: pip install 'hermes-agent[simplex-streaming]'"
            )
        # Pipecat present; the real process_pcm16 aiortc bridge lands in Slice 6.
        from gateway.calls.native.streaming.pipecat_transport import build_pipeline
        return build_pipeline(config=config)  # raises PipecatIntegrationDeferred
    return turn_based_factory()
    ```
  - Leave `select_call_engine` and the turn_based branch unchanged. Update the `build_native_pipeline` docstring's Raises section to mention `StreamingExtraNotInstalled`.
- [ ] **Step 4: Run tests to verify pass.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/test_engine_selection.py -q`
  Expected: PASS.
- [ ] **Step 5: Commit.**
  ```bash
  git add gateway/calls/native/streaming/engine.py tests/gateway/streaming/test_engine_selection.py
  git commit -m "feat(streaming): availability-aware streaming deferral in engine"
  ```

---

## Task 4: Real Pipecat smoke test (replace import-skipped stub)

**Files:**
- Replace: `tests/gateway/streaming/test_pipecat_smoke.py`

Context: read the current file first; it uses `importorskip` and asserts nothing real. Replace with a smoke that (a) where the extra is installed, asserts pipecat imports and the probe reports `1.3.0`; (b) is import-guarded so it skips cleanly where the extra is absent (local dev), since Scenario-2 (absence-is-safe) is already covered deterministically in `test_pipecat_runtime.py`.

- [ ] **Step 1: Write the test.**
  ```python
  import pytest
  from gateway.calls.native.streaming.pipecat_runtime import pipecat_available, pipecat_version

  pytestmark = pytest.mark.skipif(
      not pipecat_available(), reason="simplex-streaming extra not installed"
  )


  def test_pipecat_imports_and_version():
      import pipecat  # noqa: F401
      assert pipecat_version() == "1.3.0"
  ```
  Keep it to the bare `import pipecat` + version check — do NOT guess deeper symbol paths (e.g. `pipecat.frames.frames.Frame`) that could break CI on a wrong guess; later slices import the specific service/frame classes they actually use.
- [ ] **Step 2: Run.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/test_pipecat_smoke.py -q`
  Expected: PASS where extra installed, else SKIP.
- [ ] **Step 3: Commit.**
  ```bash
  git add tests/gateway/streaming/test_pipecat_smoke.py
  git commit -m "test(streaming): real pipecat import smoke (replaces import-skipped stub)"
  ```

---

## Task 5: Regression guard — fake-backed simulation still runs (reuse existing driver)

**Files:**
- Modify (extend, do not duplicate): `tests/gateway/streaming/test_stream_simulation.py`

Context: read the file + `gateway/calls/native/streaming/simulate.py` first. **A full-turn test ALREADY exists**: `test_stream_simulation.py::test_normal_turn_returns_ok_summary` drives a complete user→brain→TTS→DONE turn via the file's own inline `_drive`/`_settle`/`_push_frame`/`_drain` helpers under `VirtualClock`, asserting `ended_reason == "completed"`, `outbound_audio_frames > 0`, `flushes == []`. (Note: the shared `_run_stream_simulation_with_driver` lives in `hermes_cli/calls.py`, not exported from simulate.py; the test uses its own local helpers — do not invent a shared import.)

- [ ] **Step 1:** This task is expected to be a **no-op / verification only** — the existing test already satisfies Scenario 6. Confirm `test_normal_turn_returns_ok_summary` is green and covers the full turn. Optionally add a single explicit assertion that no wall-clock sleep occurs (the run already uses `VirtualClock` + `asyncio.sleep(0)` settles, so the property holds). Do not duplicate the drive loop.
- [ ] **Step 2: Run.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/test_stream_simulation.py -q`
  Expected: PASS.
- [ ] **Step 3: Commit** (only if changed).
  ```bash
  git add tests/gateway/streaming/test_stream_simulation.py
  git commit -m "test(streaming): guard fake-backed simulation turn completes"
  ```

---

## Task 6: CI installs the extra for the test shards

**Files:**
- Modify: `.github/workflows/tests.yml`

- [ ] **Step 1:** In the `test` job's "Install dependencies" step (`tests.yml:53`), change `uv pip install -e ".[all,dev]"` to `uv pip install -e ".[all,dev,simplex-streaming]"`. **WARNING:** the identical line also appears in the `e2e` job (`tests.yml:86`) — the Edit `old_string` MUST include unique surrounding context (the `test`-job lines under the `strategy.matrix.group` block) so only line 53 changes and the `e2e` job at line 86 is left untouched.
- [ ] **Step 2:** Validate the workflow YAML parses (optional local check):
  Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/tests.yml')); print('ok')"`
  Expected: `ok`.
- [ ] **Step 3: Commit.**
  ```bash
  git add .github/workflows/tests.yml
  git commit -m "ci: install simplex-streaming extra in test shards"
  ```

---

## Task 7: Gates — ast-grep, ruff, ty, focused suite

**Files:** none (verification only).

- [ ] **Step 1: ast-grep streaming rules.**
  Run: `ast-grep scan --config sgconfig.yml gateway/calls/native/streaming/ 2>&1 | tail -20`
  Expected: no new violations (no-walltime / streaming-purity / frozen-dataclass).
- [ ] **Step 2: ruff + ty.**
  Run: `uv run --no-sync ruff check gateway/calls/native/streaming/ tests/gateway/streaming/ && uv run --no-sync ty check gateway/calls/native/streaming/pipecat_runtime.py gateway/calls/native/streaming/engine.py`
  Expected: clean (match repo's existing diff-based expectations).
- [ ] **Step 2b (kit coupling check, if configured):** run the repo's `kit`/cased-kit coupling check over the streaming slice if a project script exists; otherwise note N/A.
- [ ] **Step 3: Focused suite.**
  Run: `uv run --no-sync python -m pytest tests/gateway/streaming/ -q`
  Expected: all pass (present-only tests skip locally if the extra isn't installed).
- [ ] **Step 4:** No commit (or a docs/status commit only).

---

## Done criteria
All 6 BDD scenarios from the design have passing tests; the live streaming `build_native_pipeline` never returns a non-`process_pcm16` object; lock + CI install resolve Pipecat with onnxruntime pinned at 1.24.4; gates pass; `turn_based` default and the live turn-based path unchanged. Then: open PR → CI → fix obvious issues → merge on green (modulo documented pre-existing `test_setup*` + private-fork `osv-scan`).

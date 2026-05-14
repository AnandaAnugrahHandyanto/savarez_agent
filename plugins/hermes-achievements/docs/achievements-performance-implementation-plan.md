# Hermes Achievements Performance Implementation Plan

Status: **In progress on branch `perf/hermes-achievements-snapshot`** — not yet
merged or published. This document is the single source of truth for the
performance refactor; check the boxes below as work lands. The plugin itself
remains frozen on `main` until the hackathon review window closes.

Decision: `/overview` and top-banner slots are out of scope and have been
removed.

---

## Phase 0 — Baseline & Safety (no behavior change)

### Task 0.1: Add perf benchmark script (local) — **DONE**
Objective: Repro baseline before/after.

Acceptance:
- [x] Can print endpoint timings for `/achievements` (3 cache-busted/first-hit
  runs + 3 warm runs). True cold-cache measurement still requires clearing or
  restarting the dashboard outside the script, then running it immediately.
- Script: `plugins/hermes-achievements/scripts/benchmark_api.py`. Sends
  `X-Hermes-Session-Token` when the env var is set; never starts/restarts
  services.

### Task 0.2: Define acceptance thresholds — **DONE**
Objective: Lock success criteria now.

Acceptance:
- [x] Documented SLOs:
  - `/achievements` p95 < 1s (cached)
  - max active scan jobs = 1

---

## Phase 1 — Remove unused overview/slot surface (highest certainty)

### Task 1.1: Remove `/overview` backend route — **DONE**
Objective: Eliminate duplicate heavy endpoint path.

Acceptance:
- [x] `plugin_api.py` no longer exposes `/overview`. Guarded by
  `tests/test_plugin_perf.py::RouteSurfaceTests`.

### Task 1.2: Remove slot registration and SummarySlot frontend code — **DONE**
Objective: Remove cross-tab banner fetch behavior.

Acceptance:
- [x] No `registerSlot(..."sessions:top"...)` or `registerSlot(..."analytics:top"...)`.
- [x] No frontend call to `api("/overview")`. Guarded by
  `tests/test_plugin_perf.py::DistBundleTests`.

### Task 1.3: Update plugin manifest — **DONE**
Objective: Reflect final UI scope.

Acceptance:
- [x] `manifest.json` has no `slots` declarations.
- [x] Tab registration remains intact. Guarded by
  `tests/test_plugin_perf.py::ManifestTests`.

---

## Phase 2 — Shared snapshot persistence + single-flight for `/achievements`

### Task 2.1: Introduce snapshot store abstraction + on-disk persistence — **DONE**
Objective: Single source of truth for Achievements data that survives process restarts.

Acceptance:
- [x] One structure contains dataset consumed by `/achievements`
  (`_SNAPSHOT_CACHE` + `scan_snapshot.json`).
- [x] Repeated requests do not recompute when cache is fresh (`_cache_is_fresh` TTL).
- [x] Snapshot persisted at `~/.hermes/plugins/hermes-achievements/scan_snapshot.json`.

### Task 2.2: Single-flight scan coordinator — **DONE**
Objective: Prevent concurrent recomputes.

Acceptance:
- [x] Simultaneous requests result in one compute run
  (`_BACKGROUND_SCAN_LOCK` + `_SCAN_LOCK`). Guarded by
  `tests/test_plugin_perf.py::BackgroundScanSingleFlightTests`.

### Task 2.3: Refactor `/achievements` to read snapshot — **DONE**
Objective: Remove direct repeated compute from request path.

Acceptance:
- [x] `/achievements` does not run independent full recompute per request when
  cache is valid — it returns cache and triggers a background refresh when stale.

---

## Phase 3 — Stale-While-Revalidate

### Task 3.1: TTL state (`FRESH`/`STALE`) — **DONE**
Objective: Serve immediately when stale, refresh in background.

Acceptance:
- [x] Cached response returned quickly even when expired.
- [x] Refresh is asynchronous (`_start_background_scan` daemon thread).

### Task 3.2: Add `scan-status` endpoint — **DONE**
Objective: Let UI/ops inspect scan state.

Acceptance:
- [x] Returns state, last success time, last duration, last error
  (`/scan-status`).

### Task 3.3: Add metadata fields to `/achievements` — **DONE**
Objective: Improve transparency.

Acceptance:
- [x] Response includes `generated_at`, `is_stale`, `scan_meta.status`.
  Guarded by `tests/test_plugin_perf.py::AchievementsResponseShapeTests`.
- [x] Pending and in-progress payloads are reported as stale so the UI keeps
  polling even when `generated_at` is current.

---

## Phase 4 — Incremental Scanning

### Task 4.1: Add per-session checkpoint file — **DONE**
Objective: Track session-level changes, not just global scan time.

Acceptance:
- [x] Checkpoint persisted at
  `~/.hermes/plugins/hermes-achievements/scan_checkpoint.json`.
- [x] For each session: `session_id`, fingerprint
  (`started_at`/`last_active`/`model`/`title`), and cached per-session stats.

### Task 4.2: Incremental aggregation — **DONE**
Objective: Recompute only changed/new sessions and reuse unchanged cached stats.

Acceptance:
- [x] Warm scans reuse cached per-session stats when fingerprints match
  (`scan_sessions`).
- [x] `scan_meta` reports `sessions_reused` / `sessions_rescanned`.

### Task 4.3: Full rebuild fallback — **DONE**
Objective: Preserve correctness.

Acceptance:
- [x] Manual full rescan always possible via `POST /rescan`
  (`evaluate_all(force=True)`).
- [x] `schema_version` field on checkpoint allows future invalidation.
- [x] Force rescans run synchronously and do **not** publish partial
  snapshots. Guarded by `tests/test_plugin_perf.py::ForceRescanTests`.

---

## Test Plan

1. Unit tests — `plugins/hermes-achievements/tests/test_plugin_perf.py`
- [x] `/overview` route is not registered or referenced in `plugin_api.py`
- [x] Manifest has no `slots` and keeps the Achievements tab
- [x] Compiled dist bundle does not reference `/overview`, `registerSlot`,
  `SummarySlot`, `sessions:top`, or `analytics:top`
- [x] `/achievements` response carries `generated_at`, `is_stale`, and
  `scan_meta.status`
- [x] Pending and in-progress snapshots are reported stale
- [x] Background scan is single-flight under concurrent
  `_start_background_scan` and `evaluate_all` calls
- [x] Force rescan disables partial publishing and returns completed snapshot

2. Integration / manual checks (run locally; not in CI)
- Opening Achievements repeatedly causes ≤1 heavy scan while in-flight
- `/achievements` warm-cache load is fast
- Manual rescan updates snapshot and timestamps

3. Manual benchmarks
- `python plugins/hermes-achievements/scripts/benchmark_api.py` — compare
  cache-busted/first-hit and warm `/achievements` timings against the same
  history dataset. For true cold-cache numbers, clear/restart the dashboard
  outside the script before the first run.

---

## Rollout Plan

1. **Done on this branch** — Phase 1 (overview/slots removed), Phase 2
   (snapshot/dedupe), Phase 3 (stale-while-revalidate + status metadata),
   Phase 4 (incremental checkpoint).
2. Manually validate no UI regression in Achievements tab against a real
   Hermes session DB before merging.
3. Capture pre/post benchmark numbers using the benchmark script and add
   them to the PR description.

Rollback: revert this branch. The old non-cached compute path is no longer
guarded behind a flag — the in-memory + on-disk snapshot store is now the
sole source of truth.

---

## Definition of Done

- [x] Achievements tab remains fully functional (counts, latest, tiers, cards, filters).
- [x] No `/overview` endpoint or slot calls remain.
- [x] Repeated Achievements loads feel immediate after warm cache (in-memory
  TTL + on-disk snapshot reused across process restarts).
- [ ] Metrics/unlocks remain unchanged versus baseline. *Verify on real
  history before merging — capture in PR description with benchmark output.*

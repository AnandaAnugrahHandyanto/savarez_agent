# Overnight Research Engine v2 — Jack3 maintenance handoff

## Purpose
This handoff returns code ownership of the overnight research engine v2 to Jack3.
Woros retains operational ownership because the engine is part of the core weekly investing routine and anchored to the weekly journal cycle.

This document is for future maintenance, iteration, and bug-fixing.

---

## System role
The overnight engine is not a generic report generator.
It is a stateful retrieval / adjudication / packaging system that feeds:
1. weekly prep
2. live journal session
3. weekly follow-up

The weekly journal is the anchor workflow.

---

## Canonical code / state surfaces

### Main engine code
Under:
- `~/.hermes/docs/woros/weekly-journal/scripts/`

Key files:
- `overnight_v2_run.py` — top-level orchestration / resume behavior
- `overnight_v2_resume.py` — resume entrypoint
- `overnight_v2/schemas.py` — run/phase schema
- `overnight_v2/state_store.py` — disk-backed state IO
- `overnight_v2/perplexity_adapter.py` — worker adapter boundary
- `overnight_v2/blocks/block2_harvest_pass1.py`
- `overnight_v2/blocks/block4_submit_pass2.py`
- `overnight_v2/blocks/block5_harvest_pass2.py`
- `overnight_v2/blocks/block6_final_packaging.py`
- `overnight_v2/blocks/block7_assimilation_routing.py`
- `overnight_v2/bridge.py` — weekly-surface bridge generation + sanitation/compression

### Tests
Key test files:
- `tests/test_overnight_v2_end_to_end.py`
- `tests/test_overnight_v2_bridge.py`
- `scripts/overnight_v2/tests/test_block2_harvest_pass1.py`
- `scripts/overnight_v2/tests/test_block5_harvest_pass2_followup.py`
- `scripts/overnight_v2/tests/test_downstream_hardening.py`
- `scripts/overnight_v2/tests/test_pass2_prompt_construction.py`

### Run-state / outputs
Each run lives under:
- `~/.hermes/docs/woros/overnight-runs/<run-id>/`

Important artifacts:
- `run-state.json`
- `task-registry.json`
- `<phase>/phase-state.json`
- `artifacts/concise-memo.md`
- `artifacts/delta-shortlist.md`
- `artifacts/artifact-map.yaml`
- `artifacts/weekly-cycle-bridge.json`
- `artifacts/challenge-resolution-table.json`
- `artifacts/pause-summary.json`
- `artifacts/pause-summary.md`

---

## Architecture summary

### Block flow
0. setup
1. submit pass1
2. harvest pass1
3. cross-exchange
4. submit pass2
5. harvest pass2
6. final packaging
7. assimilation / routing into weekly surfaces

### Adapter boundary
The worker adapter should remain provider-neutral.
Current important methods:
- `submit_task(...)`
- `get_task_status(task_ref)`
- `harvest_task(task_ref)`
- `submit_followup(...)`

### Weekly-cycle bridge contract
The engine should emit bridge payloads with:
- `prep_ingest`
- `live_session_ingest`
- `followup_ingest`

And then ingest them into:
- `prep-pack.md`
- `session-lead-sheet.md`
- `follow-up.md`

---

## Important fixes already implemented

### 1. Provider-status-lag timeout harvest
Problem:
- Perplexity can keep returning `status=running` even when task content is materially complete.

Fix already implemented:
- `block2_harvest_pass1.py` and `block5_harvest_pass2.py` harvest on timeout even if provider status is still non-terminal.
- If harvested content validates, phase completes with `provider_status_lag_detected=true` and an explanatory note.
- If timed out and raw output is still empty, phase expires instead of hanging forever.

### 2. Pass2 multiline source-row parsing
Problem:
- Perplexity can emit multiline `new_opened_sources` rows.

Fix already implemented:
- `normalize_pass2.py` coalesces multiline source rows before validation.

### 3. Top-level stop-on-waiting gating
Problem:
- Pipeline could continue into block6/block7 while pass work was still waiting.

Fix already implemented:
- `overnight_v2_run.py` pauses after block2 or block5 when phases remain non-terminal.

### 4. Pass2 submission idempotency
Problem:
- Reruns could create duplicate pass2 submit jobs.

Fix already implemented:
- `block4_submit_pass2.py` avoids duplicate submission when a phase already has a task.

### 5. Weekly-surface sanitation + compression
Problem:
- Weekly surfaces got polluted by prompt/UI residue and were too long for actual use.

Fix already implemented:
- `bridge.py` strips obvious garbage.
- `bridge.py` compresses/ranks/caps bullets for session-facing artifacts.

### 6. Compression hardening
Problem:
- malformed bridge inbox JSON could break ingestion
- over-aggressive cleaning could drop valid short bullets
- over-broad truncation heuristics could drop valid monitor/threshold items

Fix already implemented:
- malformed inbox payloads are skipped
- broad lowercase-token junk filter removed
- truncation suffix heuristic narrowed

### 7. Resume/provider hardening
This was the most recent important fix.

Problem A:
- Resume treated `current_block=block5_harvest_pass2` as if block5 were done, even when the run had actually paused there waiting for phases.
- Result: resume skipped block5, so timeout-harvest logic never got another chance to fire.

Fix:
- `overnight_v2_run.py` now reruns the current block on resume if it is still logically blocking.

Problem B:
- Resume could silently fall back to `stub` provider when config omitted `worker_provider`.

Fix:
- provider resolution now checks persisted `run_state.worker_preflight.provider`.

### 8. Run-state semantics hardening
Problem:
- `current_block` alone was too ambiguous.

Fix:
- run-state now includes:
  - `pipeline_state`
  - `resume_from_block`
  - `paused_at_sgt`
  - `pause_reason`
  - `waiting_phase_ids`

### 9. Pause summary artifact
Problem:
- operators had to read raw run-state to understand why a run was paused.

Fix:
- paused runs now write:
  - `artifacts/pause-summary.json`
  - `artifacts/pause-summary.md`
- these are cleared again when the pipeline resumes/activates or fully completes.

---

## Important real-world lesson from 2026-04-25 run
The 2026-04-25 AI fragility dashboard run looked like “same provider-status lag again,” but the real operational failure was:
- timeout-harvest logic existed,
- block5 paused correctly,
- but resume semantics skipped the paused current block,
- so timeout-harvest never re-fired automatically.

Secondary issue:
- generic resume could resolve provider as `stub` instead of the persisted real worker if config/env were incomplete.

This is now fixed, but these are the core failure modes to remember.

---

## Current operational semantics to preserve

### Paused state
If the pipeline pauses because phases are still waiting:
- `pipeline_state = paused`
- `resume_from_block = current blocking block`
- `pause_reason = waiting_for_phase_completion`
- `waiting_phase_ids = [...]`
- pause summary artifacts exist

### Completed state
On successful block7:
- `pipeline_state = completed`
- pause metadata cleared
- pause summary artifacts removed
- weekly bridge written
- adoption metadata written into run-state

---

## Known remaining rough edges / future maintenance targets

### 1. Packaging quality is still dense
The bridge is cleaner and shorter than before, but the session-facing prose is still sometimes too research-dense.
Future work:
- stronger editorial rendering for prep/live/follow-up surfaces
- more aggressive dedupe across highly similar claims

### 2. Manual-run truth vs automated-run truth
If a human/operator manually probes the adapter/browser outside the normal pipeline, run-state may lag unless the result is written back through the engine.
Future work:
- cleaner official “manual recovery apply” path
- explicit artifact for externally harvested / operator-applied completion

### 3. Worker-preflight truthfulness
The run-state provider fields should remain truthful even under manual repair/resume flows.
Do not let a recovery path overwrite real worker history with `stub` metadata.

### 4. Better challenge-row mapping
`contested_claims` still derives imperfectly from packaged memo ordering rather than a precise claim-status map.
This is not a nightly blocker but is a logic-quality improvement target.

### 5. Handoff/debug surfaces
Morning/operator outputs should ideally embed pause-summary semantics directly rather than requiring separate inspection.

---

## Recommended maintenance doctrine for Jack3
1. Keep the adapter boundary provider-neutral.
2. Keep run-state disk-backed and explicit.
3. Never let resume semantics infer too much from `current_block` alone.
4. Distinguish:
   - content complete
   - provider terminal
   - run paused
   - run completed
5. Weekly-cycle assimilation must remain first-class, not an afterthought.
6. Prefer explicit artifacts over hidden inferred state.

---

## Woros vs Jack3 boundary going forward

### Woros owns
- nightly operation
- weekly-cycle integration
- topic selection
- interpretation of output quality
- deciding whether a run is decision-useful
- simple operational unblock (e.g. rerun block5 with the real adapter when state is obviously lagging)

### Jack3 owns
- code maintenance
- engine iteration
- parser/validator fixes
- resume/control-plane hardening
- provider integration details
- test coverage expansion
- refactors and bugfix implementation

This boundary should be preserved unless explicitly changed.

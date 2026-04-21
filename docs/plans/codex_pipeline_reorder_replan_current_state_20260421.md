# Codex Context — Full Pipeline Replanning From Current Post-Phase1 State

## Goal
Re-plan the **entire multi-phase repository reordering** for the Orbi webtoon/webnovel pipeline based on the **current actual repo state**, not the earlier pre-Phase1 assumptions.

The user wants a fresh, current-state-based full plan for:
- pipeline/runtime infrastructure
- canonical project specs
- dated experiments
- generated artifacts

This is a **re-planning task**, not immediate implementation.
Use Codex **`$ralplan`** semantics and produce a concrete multi-phase roadmap grounded in the repo as it exists now.

## User request
The user asked, in effect:
- use Codex
- based on the **current state now**
- re-order / re-plan the whole thing end-to-end

So the planning output should assume:
1. Phase 1 already happened
2. the repo is still dirty and path-sensitive
3. the next steps should build on the new canonical homes instead of ignoring them

## Repo root
- `/home/orbibot/.zeroclaw/workspace/hermes-agent`

## Verified current baseline
This exact command passed immediately before this replan request:

```bash
source .venv/bin/activate && pytest -q \
  tests/test_pipeline_reorder_phase1_indexes.py \
  tests/test_balloon_pipeline_ep001.py \
  tests/test_balloon_pipeline_ep001_live.py \
  tests/test_tail_less_contracts.py \
  tests/test_webtoon_prompt_schema_ep001.py
```

Observed result:
- `41 passed`

Treat that as the current protected baseline.

## Important current-state fact
The repo is **not clean**.
There are many pre-existing modified and untracked generated files, especially under:
- `docs/plans/orbi-romance-webtoon-20260421/renders/`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/generated_fal_live_*`
- other dated plan directories

Do not assume a clean migration environment.
A good plan must explicitly account for:
- dirty-tree coexistence
- generated binaries not being safe to mass-move casually
- legacy path compatibility during transition

## What Phase 1 already accomplished
A conservative zero-regression Phase 1 has already been implemented.
It did **not** mass-move files.
Instead it introduced top-level canonical homes and mapping manifests.

### New canonical homes already exist
- `pipeline/INDEX.json`
- `projects/INDEX.json`
- `projects/orbi-romance-20260421/manifest.json`
- `experiments/INDEX.json`
- `artifacts/INDEX.json`
- `tests/test_pipeline_reorder_phase1_indexes.py`

### Legacy manifest was extended backward-compatibly
- `docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json`

It now includes a `canonical_mappings` block but keeps the old `episodes` structure intact.

## What those new indexes currently mean
### pipeline/
Currently an **index-only canonical home**.
It points to legacy runtime entrypoints such as:
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py`
- `docs/plans/orbi-romance-webtoon-20260421/storyboard_renderer.py`
- `docs/plans/orbi-romance-webtoon-20260421/scripts/render_storyboard.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`

### projects/
Currently a **canonical manifest home** for the romance package.
`projects/orbi-romance-20260421/manifest.json` maps to:
- signal
- series bible
- deliverables manifest
- series pitch
- full webnovel
- per-episode novel/spec/render paths

### experiments/
Currently an **index-only grouping layer** for:
- `20260417-balloon-baseline`
- `20260420-tail-less-policy`
- `20260420-codex-contexts`
- `20260421-vlm-observation-mvp`

### artifacts/
Currently an **index-only artifact home** for episode outputs such as:
- episode longscroll
- panel directories
- raw generation dirs
- render manifests

## What is still true after Phase 1
The actual runtime / spec / artifact files mostly still live under legacy dated trees:
- `docs/plans/orbi-romance-webtoon-20260421/...`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/...`
- `docs/plans/orbi-live-webtoon-20260420/...`
- `docs/plans/orbi-trend-webnovel-webtoon-20260420/...`

So the repo is currently in a **hybrid state**:
- canonical homes exist
- canonical source-of-truth code/data has not yet been fully migrated
- legacy paths remain operational and protected

## Planning problem to solve now
Need a **full updated multi-phase plan** for getting from the current hybrid state to a cleaner structure.

The plan should answer:
1. What should Phase 2, Phase 3, Phase 4, etc. be now?
2. What should be promoted into canonical real homes versus remain indexed only?
3. What can be physically moved safely, and in what order?
4. Where are compatibility wrappers needed?
5. Which tests need to be added before higher-risk moves?
6. What is the stopping point of each phase?

## Key planning constraints
### 1. Zero-regression remains the main rule
Do not propose a plan that casually breaks:
- existing test suite
- current render runner entrypoints
- legacy docs/plans/orbi-* workflows that are still in use

### 2. Phase 1 should not be thrown away
The new plan should **build on**:
- `pipeline/INDEX.json`
- `projects/orbi-romance-20260421/manifest.json`
- `experiments/INDEX.json`
- `artifacts/INDEX.json`

### 3. No fake cleanliness assumptions
The tree is dirty.
Generated assets exist.
Some manifests point to absolute paths.
Some tests and scripts hardcode old dated locations.
A good plan must explicitly treat these as migration risks.

### 4. Runtime code and project/spec code should be separated gradually
A likely good direction is:
- first make `pipeline/runtime/` contain actual canonical runtime code
- then keep legacy paths as wrappers
- only later decide whether project/spec files should physically move into `projects/`

### 5. Experiments are probably the lowest-risk real move target
A likely low-risk next phase is real relocation of context-only docs into `experiments/`.
But do not assume that blindly; verify against current references.

## Areas that likely need phased planning
### A. Runtime canonicalization
Examples:
- live episode runner
- balloon analyzer
- balloon renderer
- balloon layout utils
- storyboard fallback path

Need a plan for when/how these become real files under `pipeline/runtime/`.

### B. Project canonicalization
Examples:
- whether `projects/orbi-romance-20260421/` stays manifest-only for now
- whether it later receives copied or moved spec files
- whether project README / local manifest layers are needed first

### C. Experiment relocation
Examples:
- dated codex context docs
- VLM MVP context docs
- tail-less policy notes
- attachment iteration docs

Need a clear separation between:
- experiment docs
- reusable runtime assets
- canonical project files

### D. Artifact governance
Examples:
- per-episode artifact manifests
- raw vs overlay vs final segregation
- whether physical moves should happen at all in the near term
- whether artifact manifests should become the operational boundary before any binary move

## Existing planning docs to use as inputs
- `docs/plans/webtoon-webnovel-pipeline-reordering-roadmap-20260421.md`
- `docs/plans/codex_pipeline_reorder_execution_context_20260421.md`

Also inspect the new Phase 1 files:
- `pipeline/INDEX.json`
- `projects/orbi-romance-20260421/manifest.json`
- `experiments/INDEX.json`
- `artifacts/INDEX.json`
- `tests/test_pipeline_reorder_phase1_indexes.py`

## What the new `$ralplan` output must contain
Produce a **current-state-based multi-phase plan** with at least:
1. updated repo diagnosis from the current hybrid state
2. recommended end-state architecture
3. phase-by-phase plan with clear exit criteria
4. exact file/path targets per phase
5. regression-test strategy per phase
6. compatibility strategy per phase
7. risk register for path-sensitive and dirty-tree issues
8. recommended order of operations
9. clear statement of what should **not** be moved yet

## Deliverable preference
The plan should be execution-ready and structured enough that the next Codex `$ralph` run could take one phase at a time.

In other words:
- not vague strategy talk
- not one giant migration fantasy
- a realistic staged roadmap from **current post-Phase1 hybrid repo** to cleaner separation

## Naming hint
Use a task slug around:
- `pipeline-reorder-replan-current-state-20260421`

## Final instruction
Read the current-state context file first.
Ground the plan in the actual present repo state.
Use `$ralplan` semantics.
Create the appropriate `.omx/context/...` and `.omx/plans/...` artifacts for this updated multi-phase re-planning task.
Do not execute code changes in this step; planning only.
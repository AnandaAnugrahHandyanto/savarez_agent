# Codex Context — Webtoon/Webnovel Pipeline Reorder With Zero-Regression Constraint

## Goal
Reorder the current Orbi webtoon/webnovel repository structure so that these concerns are clearly separated:

1. **pipeline / runtime infrastructure**
2. **project/spec source-of-truth**
3. **dated experiments / Codex contexts**
4. **generated artifacts**

This is not a cosmetic rename-only task.
The goal is to make the repository operationally legible **without breaking the existing pipeline behavior**.

## Hard constraint
**Existing pipeline behavior must keep working without regression.**
Do not break:
- existing regression tests
- existing live render runner behavior
- existing romance project outputs/paths unless a compatibility shim or manifest update preserves behavior

If a move would break current scripts/tests, either:
- keep a compatibility wrapper, or
- update all affected references and verify them

No hand-wavy cleanup that strands the current working lane.

## Repo / working directory
- Repo root: `/home/orbibot/.zeroclaw/workspace/hermes-agent`
- Work in-repo only
- Current branch: `main`

## Verified environment facts
- `codex` CLI exists
- OMX skills exist:
  - `~/.codex/skills/ralplan/SKILL.md`
  - `~/.codex/skills/ralph/SKILL.md`
- Python env for this repo is `.venv`, not `venv`

## Verified current regression baseline
This exact command passed before implementation:

```bash
source .venv/bin/activate && pytest -q \
  tests/test_balloon_pipeline_ep001.py \
  tests/test_balloon_pipeline_ep001_live.py \
  tests/test_tail_less_contracts.py \
  tests/test_webtoon_prompt_schema_ep001.py
```

Observed result:
- `34 passed`

Treat that as the minimum protected baseline.

## Additional verified runtime fact
A transient DNS failure previously broke one live render download from `v3b.fal.media`, but a retry succeeded.
This means network flakiness exists, but the render lane itself is still functional.
Do not misdiagnose that as a structural pipeline issue.

## User direction
The user explicitly said the repo needs a separation between:
- pipeline
- actual execution infrastructure
- dated experiments
- generated artifacts

Then explicitly asked:
- use **`$ralplan`** to plan this
- use **Codex** to implement it
- keep the existing pipeline working without regression

## Key observed current-state problems
The repo currently mixes four different things under dated `docs/plans/orbi-*` directories:

### 1. Pipeline / project source-of-truth
Examples:
- `docs/plans/orbi-romance-webtoon-20260421/00_signal.md`
- `docs/plans/orbi-romance-webtoon-20260421/01_series_bible.md`
- `docs/plans/orbi-romance-webtoon-20260421/novel/*.md`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/scroll_plan.yaml`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/panel_prompts.yaml`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/lettering_script.yaml`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/render_queue.yaml`
- `docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json`

### 2. Runtime infrastructure / runner code
Examples:
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001/render_webtoon_fal_live.py`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001/render_webtoon_fal_live_vlm.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`
- `docs/plans/orbi-romance-webtoon-20260421/storyboard_renderer.py`
- `docs/plans/orbi-romance-webtoon-20260421/scripts/render_storyboard.py`

### 3. Dated experiments / Codex context docs
Examples:
- `docs/plans/orbi-trend-webnovel-webtoon-20260420/codex_*_context.md`
- `docs/plans/orbi-romance-webtoon-20260421/codex_*_context.md`
- VLM MVP context docs
- balloon attachment replan / iteration docs

### 4. Generated artifacts
Examples:
- `docs/plans/orbi-romance-webtoon-20260421/renders/ep00N/*.png`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/generated_fal_live_*`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_*`
- `generated_fal_v3_ballooned_*`
- `generated_fal_ui*`
- `placement_manifest.json`
- `generated_fal_live_manifest_*.json`

## Existing roadmap document already written
Use this as an input, not the only source of truth:
- `docs/plans/webtoon-webnovel-pipeline-reordering-roadmap-20260421.md`

It proposes the target separation into:
- `pipeline/`
- `projects/`
- `experiments/`
- `artifacts/`

## Canonical direction to preserve
The intended direction is:

### Canonical product lane
- `docs/plans/orbi-romance-webtoon-20260421`

### Canonical balloon/runtime baseline
- `docs/plans/orbi-trend-webnovel-webtoon-20260417`

### Policy/reference lane
- `docs/plans/orbi-live-webtoon-20260420`

### Archive/experiment candidate
- `docs/plans/orbi-trend-webnovel-webtoon-20260420`

## Important implementation preference
Do **not** do a massive risky relocation with no compatibility layer.
Prefer a staged refactor that keeps behavior working:

Possible good approach:
1. introduce new top-level structure (`pipeline/`, `projects/`, `experiments/`, `artifacts/`)
2. move or copy the truly canonical files into those locations
3. add lightweight compatibility wrappers / forwarding docs / path shims where needed
4. update tests and manifests deliberately
5. verify the current render/test flow still works

If full file moves are too risky in one pass, a first safe pass that:
- establishes the new canonical homes,
- moves low-risk docs/experiments,
- extracts runtime code,
- and preserves the old project paths as wrappers,
would be acceptable.

## Required planning output from `$ralplan`
Need a concrete plan that specifies:
1. exact files/directories to create
2. exact files to move vs leave in place
3. compatibility strategy for old paths
4. regression-test strategy before/during/after
5. acceptance criteria for "reordered but still works"
6. risk notes for path-sensitive code and manifests

The plan should be implementation-ready, not vague commentary.

## Required implementation output from `$ralph`
Implement the approved plan.
At minimum, the result should include a real structure separation such as:
- `pipeline/` for runtime code and/or pipeline contracts
- `projects/` for canonical project/spec content
- `experiments/` for dated Codex context and tuning lanes
- `artifacts/` for generated outputs and manifests

But do it in a way that preserves working behavior.

## Strong suggestions for safe implementation
- Lock behavior with tests first if any moved path is not already covered
- Keep diffs reviewable
- Prefer compatibility wrappers over breaking moves
- Do not introduce new dependencies
- Update manifests/docs if source-of-truth paths move
- Run targeted tests during the refactor, then full protected baseline at the end

## Files/tests likely to matter
Regression-sensitive tests:
- `tests/test_balloon_pipeline_ep001.py`
- `tests/test_balloon_pipeline_ep001_live.py`
- `tests/test_tail_less_contracts.py`
- `tests/test_webtoon_prompt_schema_ep001.py`

Likely touched files:
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`
- `docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json`
- project/spec markdown files and render_queue YAMLs if paths change

## Existing dirty tree warning
The repository already contains many modified/untracked files, especially render outputs.
Do not assume a clean repo.
Avoid destructive cleanup of unrelated dirty files.
Scope your edits carefully.

## Preferred outcome quality bar
A good result should make the repo legible enough that a human can answer these quickly:
1. Where is the canonical project spec?
2. Where is the runtime code that actually executes the pipeline?
3. Where do dated experiments live?
4. Where do generated outputs live?
5. What old paths still work, and why?

## Final instruction
First run **`$ralplan`** using this context and the current repo state.
Create the OMX planning artifacts.
Then inspect the plan and execute it with **`$ralph`**.
Do not stop at planning.
Implement the reordering/refactor and verify the regression baseline still passes.
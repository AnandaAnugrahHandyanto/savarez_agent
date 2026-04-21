# Codex Ralplan Context — Webtoon Prompt Design for Character Consistency

## Why this planning pass exists
The user identified a new primary quality issue in the current ep001 webtoon pipeline:

> 컷마다 캐릭터가 달라져버리는 이슈가 있음

This is now more important than balloon styling.
The immediate request is **not implementation yet**.
The request is specifically:

> codex를 통해 프롬프트 디자인을 ralplan해

So this step should use **Codex `$ralplan`** to create a concrete prompt-design plan focused on fixing **character consistency across panels**.

## Scope of this planning pass
Plan only.
Do not jump straight into broad implementation in this step.
The desired output is a file-specific, execution-ready plan for improving prompt design and reference strategy so the same characters stay visually stable across cuts.

## Current repo surfaces to inspect
Primary files:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/panel_prompts.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_manifest_v3.json`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/scroll_plan.yaml`

Supporting outputs worth checking:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v3/*.png`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v3/ep001_fal_longscroll.png`

## Current rendering structure
The current renderer:
- creates 3 top-level anchors:
  - location
  - protagonist
  - mother
- then renders `p01..p08`
- uses `fal-ai/flux-2-pro` for initial generation
- uses `fal-ai/flux-2-pro/edit` for subsequent panels
- builds refs mainly from:
  - location anchor
  - protagonist anchor
  - mother anchor when present
  - previous panel image (`prev_url`) for continuity

This means the current system is mostly **anchor + edit chain**.

## Current prompt-design weakness
The likely problem is that prompt design is too weak to hold identity.
Examples from the current renderer:
- protagonist anchor language is roughly: same 19-year-old Korean male student in black hoodie
- mother anchor language is roughly: same Korean mother in simple beige homewear

These descriptors are too loose.
They do not strongly lock:
- hair silhouette
- face shape
- age impression
- eye shape
- body build
- outfit structure
- repeated distinguishing traits

As a result, the model can re-interpret the mother and sometimes even the protagonist from cut to cut.

## Observed continuity failure
Visual review suggests:
- protagonist is relatively stable
- mother drifts more noticeably
- the most unstable region is the mid-sequence repeated cuts
- p04–p08 are the likely trouble zone
- especially p05 and p08 feel like stronger identity drift candidates for the mother

The plan should validate this against the actual current outputs.

## Strong hypothesis
The pipeline is currently optimized more for:
- scene continuity
- room continuity
- rough role continuity

than for:
- identity-locked character continuity

The drift likely comes from a combination of:
1. weak anchor prompt design
2. insufficiently specific character sheets
3. over-reliance on `prev_url`
4. too few explicit per-character visual invariants
5. insert/prop-heavy cuts breaking the continuity chain before later character-heavy panels

## Direction constraints
The new plan should respect these constraints:
- Keep `generated_fal_v3` as the current quality baseline / source-art baseline for comparison
- Keep the existing downstream balloon overlay architecture separate from art generation
- Focus this plan on **prompt design and reference strategy**, not balloon placement
- Prefer improving the current `render_webtoon_fal_v3.py` lane rather than replacing the whole pipeline
- No generic hand-wavy advice; produce a file-specific plan
- The user asked for **Codex `$ralplan`**, so the output should be a real plan artifact under `.omx/`

## What Codex should inspect and answer
The planning pass should explicitly evaluate:

### 1. Character anchor design
Should we introduce stronger character anchor prompts and/or structured character sheets?
Examples:
- protagonist anchor with fixed hair, face, age, hoodie silhouette, body build, emotional baseline
- mother anchor with fixed hairstyle, face shape, age band, homewear silhouette, posture impression

### 2. Prompt schema design
Should `panel_prompts.yaml` evolve from simple freeform panel prompts into a more structured prompt package?
For example fields like:
- required_characters
- character_visibility
- locked_traits
- continuity_priority
- shot-specific allowed deviations
- identity_must_keep
- facial_visibility_level

### 3. Reference injection strategy
Should the render step stop treating `prev_url` as the primary continuity carrier?
Questions:
- when should character anchors outrank `prev_url`?
- should character-specific refs be re-injected every time a character appears?
- should insert-screen / hand-closeup panels reset or reduce chain dependence before the next character-heavy shot?

### 4. Character-sheet generation lane
Should there be a dedicated pre-pass that generates:
- protagonist sheet
- mother sheet
- maybe multiple controlled anchor views per character
before episode panel generation?

### 5. Scene-type-specific prompt rules
Prompt design may need different rules for:
- face-visible dialogue cuts
- over-shoulder cuts
- doorway reveal cuts
- insert/monitor cuts
- hand closeups
- blurred-background character cuts

### 6. Verification design
How should we verify prompt-design success beyond subjective visual judgment?
Examples:
- checklist for face/hair/outfit consistency
- panel-by-panel continuity rubric
- human review notes per panel
- optional machine-readable continuity manifest fields

## Desired output from `$ralplan`
A concrete plan that includes:
- exact files to edit
- exact new prompt-schema or data-structure fields
- whether to add character-sheet assets or manifests
- how to rebalance anchor refs vs previous-panel refs
- whether to split prompt design by shot type
- verification steps
- risks and tradeoffs

## Important non-goals for this step
Do not make this planning pass about:
- balloon tail rendering
- caption placement
- general webtoon UI overlay tuning
- a totally different product architecture

This is a focused planning pass for:
**prompt design and reference strategy to improve same-character consistency across panels**.

## Deliverable expectation
Produce the normal OMX planning artifacts, ideally including:
- `.omx/context/...`
- `.omx/plans/prd-...md`
- `.omx/plans/test-spec-...md`

The plan should be strong enough that we can review it and then decide whether to run `$ralph` afterward.

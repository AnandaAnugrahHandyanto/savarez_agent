# Codex Implementation Context — EP001 Character Consistency Prompt Design

## Goal
Implement the approved character-consistency prompt-design upgrade for the EP001 webtoon art-generation lane.

Primary source plans:
- `.omx/plans/prd-character-consistency-ep001-20260420.md`
- `.omx/plans/test-spec-character-consistency-ep001-20260420.md`

## Why this implementation exists
The current EP001 art-generation lane produces noticeable same-character drift across panels, especially for the mother.
The implementation goal is to improve same-character continuity through:
- stronger character-sheet prompt structure
- shot-aware reference routing
- typed continuity state instead of a universal `prev_url`
- inspectable prompt/continuity manifest data
- deterministic tests for schema and routing behavior

## In-scope files
Primary implementation targets:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/panel_prompts.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py`
- `tests/test_webtoon_prompt_schema_ep001.py`

Expected new artifact(s):
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/character_consistency_review.yaml`

Expected regenerated artifact(s):
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_manifest_v3.json`
- if live render is run, updated `generated_fal_v3/*.png` and longscroll

## Constraints
- Keep `generated_fal_v3` as the current before/after comparison baseline.
- Keep balloon/overlay logic separate from this work.
- Do not replace the whole pipeline; evolve the current lane.
- No new dependencies without explicit request.
- Prefer pure helper functions for prompt assembly and reference selection so tests can run without live FAL calls.
- Keep the YAML authorable by a human; do not overcomplicate the schema.

## Required implementation direction
1. Upgrade `panel_prompts.yaml` from the current flat anchor descriptions to a structured prompt schema.
2. Add explicit character-sheet identity locks for protagonist and mother.
3. Add per-panel continuity metadata such as:
   - visible characters
   - identity focus
   - face visibility
   - continuity mode
   - must_keep
   - allowed_variation
   - reference_injection
4. Refactor `render_webtoon_fal_v3.py` so it no longer relies on a universal single `prev_url` chain.
5. Add typed reference state, including per-character strong refs and shot-aware reset behavior.
6. Add deterministic dry-run / manifest-only support if needed for tests.
7. Expand manifest observability so continuity choices are explainable panel-by-panel.
8. Add the deterministic regression suite from the test spec.
9. Add the human review YAML artifact.

## Important specific expectations
- `p03`, `p05`, and `p07` should not become the primary identity carrier for later character-heavy panels.
- `p08` should be able to recover mother continuity from mother anchor views and/or `p06`, rather than depending mainly on `p07`.
- Character sheets must lock more than clothing-only cues.
- The mother must be described tightly enough to reduce hairstyle / face-impression drift.

## Verification requirements
At minimum, run:
```bash
python -m py_compile docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py
pytest -q tests/test_webtoon_prompt_schema_ep001.py
```

If a dry-run mode is implemented, also run it and confirm the manifest explains:
- prompt parts
- used refs
- skipped refs and reasons
- continuity mode
- strong-ref update decisions

If live render is run, compare continuity in:
- `p02`
- `p06`
- `p07`
- `p08`

## Deliverable shape
Implementation should leave behind:
- updated prompt schema
- updated renderer
- tests passing
- human review checklist artifact
- manifest evidence
- concise summary of changed files and any residual risks

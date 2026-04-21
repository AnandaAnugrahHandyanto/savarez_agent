# Codex Tight Implementation Context — EP001 Character Consistency

Implement only the approved EP001 prompt-schema continuity upgrade.

## Hard scope
Only touch these files unless absolutely necessary:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/panel_prompts.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py`
- `tests/test_webtoon_prompt_schema_ep001.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/character_consistency_review.yaml`
- generated dry-run manifest output if the renderer writes it

Do NOT wander into balloon pipeline files, rerender candidate scripts, unrelated tests, or exploratory image-generation experiments.
Do NOT inspect unrelated docs beyond what is required by the PRD/test spec.
Do NOT create alternative candidate render scripts.

## Required deliverables
1. Upgrade `panel_prompts.yaml` to the structured schema required by:
   - `.omx/plans/prd-character-consistency-ep001-20260420.md`
   - `.omx/plans/test-spec-character-consistency-ep001-20260420.md`
2. Refactor `render_webtoon_fal_v3.py` to:
   - use typed per-character continuity state instead of a universal `prev_url`
   - support deterministic `--dry-run --manifest-only`
   - expose prompt parts / reference strategy / used refs / skipped refs in the manifest
3. Add `tests/test_webtoon_prompt_schema_ep001.py`
4. Add `character_consistency_review.yaml`
5. Run verification:
   - `python -m py_compile docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py`
   - `python docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py --dry-run --manifest-only`
   - `pytest -q tests/test_webtoon_prompt_schema_ep001.py`

## Important implementation constraints
- Preserve existing panel ids and EP001 lane paths.
- Do not run live FAL generation unless it is strictly required. Prefer deterministic dry-run verification.
- `p03`, `p05`, and `p07` must not become the primary identity carrier for later character-heavy panels.
- `p08` must recover mother continuity from mother anchor views and/or `p06`, not mainly from `p07`.
- Keep the YAML human-authorable.

## Output discipline
Do not spend time narrating plans. Edit the files, run the required commands, and finish with verified outputs.

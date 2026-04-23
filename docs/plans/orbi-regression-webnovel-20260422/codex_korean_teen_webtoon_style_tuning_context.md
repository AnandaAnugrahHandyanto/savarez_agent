# Codex context — Korean teen webtoon style tuning for ep001

## User request
- 현재 결과는 그림체가 미묘하게 다르고 너무 실사 느낌이 짙다.
- 한국 10대 인기 웹툰들 그림체를 리서치해서 프롬프트 형태로 튜닝해야 한다.
- Codex로 진행.

## Current work area
Base directory:
- `docs/plans/orbi-regression-webnovel-20260422/webtoon/ep001/`

Existing important files:
- `character_anchor.md`
- `consistency_fix_notes.md`
- `style_research_korean_teen_webtoons.md`
- `generated_gpt_image2_panels_consistency_lock_manifest.json`
- prompt dir currently incomplete / needs cleanup and rebuilding

Rendered panel outputs exist here:
- `docs/plans/orbi-regression-webnovel-20260422/renders/ep001/panels_consistency_lock/`

## Problem to solve
1. Current prompts lean too far toward grounded realism / semi-real live-action look.
2. Character consistency improved, but style consistency is still not locked.
3. Need a **mainstream Korean teen-popular webtoon** prompt language rather than gritty realism.

## Style research summary to use
Read and follow:
- `docs/plans/orbi-regression-webnovel-20260422/webtoon/ep001/style_research_korean_teen_webtoons.md`

Key derived direction:
- clean Naver-style school/romance/drama lineart
- youthful webtoon face proportions
- almond eyes, small nose, soft V-line jaw
- soft cel shading / semi-flat rendering
- simplified school/interior backgrounds
- anti-photoreal negatives
- mobile-readable vertical composition

## What Codex should do
Please update or create a clean prompt package for EP001 that pushes the images toward a more popular Korean teen webtoon style.

### Required outputs
Create/update these files:
- `docs/plans/orbi-regression-webnovel-20260422/webtoon/ep001/style_prompt_contract.md`
- `docs/plans/orbi-regression-webnovel-20260422/webtoon/ep001/panel_prompts_style_locked.yaml`
- `docs/plans/orbi-regression-webnovel-20260422/webtoon/ep001/render_queue_style_locked.yaml`
- `docs/plans/orbi-regression-webnovel-20260422/webtoon/ep001/prompts/20-p01-style-lock.md`
- `.../prompts/21-p02-style-lock.md`
- `.../prompts/22-p03-style-lock.md`
- `.../prompts/23-p04-style-lock.md`
- `.../prompts/24-p05-style-lock.md`
- `.../prompts/25-p06-style-lock.md`
- `.../prompts/26-p07-style-lock.md`

### Requirements for new prompt package
- Keep the current character anchor identity from `character_anchor.md`
- Reduce photoreal cues significantly
- Use wording that steers toward popular Korean teen webtoon style
- Keep grounded Korean exam-drama props and settings
- Add explicit anti-realism negatives
- Keep prompts short enough to be practical, but detailed enough for stable style
- Maintain one shared style block + per-panel deltas if appropriate

### Good direction
- clean Korean webtoon lineart
- polished digital manhwa illustration
- semi-flat or soft cel shading
- smooth even skin
- youthful school-drama faces
- simplified background detail
- mobile vertical webtoon readability

### Avoid
- photorealistic
- cinematic live-action
- painterly skin
- prestige-drama realism
- gritty mature manhwa rendering
- hyper-detailed hair strands
- broad-shouldered or adult-looking protagonist

## Deliverable expectation
Codex should modify/create files only. No need to render images. The goal is a better prompt package ready for the next image generation pass.

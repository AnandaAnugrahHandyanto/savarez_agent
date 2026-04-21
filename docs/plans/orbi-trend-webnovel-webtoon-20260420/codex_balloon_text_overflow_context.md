# Codex Context — Balloon Text Overflow in EP001

## Goal
Fix the current EP001 balloon-render issue where Korean text visibly protrudes outside the speech balloon shape.

## User constraint
The user explicitly does **not** want direct manual patching by Orbiracle for this class of work.
Use **Codex `$ralplan` + `$ralph` only** for investigation and implementation.

## Current symptom
In the latest ballooned output, some speech text appears to extend beyond the white speech balloon boundary.
The user described it as:

> 글씨가 말풍선을 튀어나오는 이슈가 있음

This should be treated as a real rendering bug, not just an aesthetic nit.

## Important current state
The latest ballooned output directory is:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v3_ballooned_latest/`

Relevant current source files:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`
- `tests/test_balloon_pipeline_ep001.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_analysis_ep001.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/lettering_script.yaml`

## Critical evidence already confirmed
### 1. Current test file is broken from an invalid manual import attempt
`python -m py_compile tests/test_balloon_pipeline_ep001.py ...` currently fails with:

- `SyntaxError: invalid decimal literal`

Cause:
- `tests/test_balloon_pipeline_ep001.py` contains an invalid import path using the date-stamped directory name directly in a Python import:
  - `from docs.plans.orbi-trend-webnovel-webtoon-20260417.webtoon.ep001.balloon_layout_utils import ...`

This must be fixed as part of the Codex work.

### 2. Root-cause hypothesis for overflow
The likely cause is geometric mismatch between:
- text-fit width/height checks in `fit_text_block(...)`
- actual safe drawable region inside an ellipse speech balloon in `render_shape(...)`

More specifically:
- text fitting appears to use rectangular inner-box assumptions
- speech bubbles are rendered as ellipses
- centering text in the rectangular `inner_box` can still place corners/long lines outside the visually safe ellipse interior

So the bug is likely **not** only line wrapping; it is also a **shape-aware safe-area mismatch**.

### 3. There was a partial manual patch attempt that should be superseded cleanly by Codex
Partial local changes already exist in:
- `balloon_layout_utils.py`
- `render_balloons.py`
- `tests/test_balloon_pipeline_ep001.py`

Those edits are not authoritative.
Codex should inspect them, keep good ideas if useful, but produce a clean correct result and restore passing verification.

## What Codex should investigate
1. How `fit_text_block(...)` decides text width/height acceptance.
2. Whether speech balloons need a stricter fit region than captions/chat boxes.
3. Whether `render_shape(...)` should use a smaller shape-aware text-safe box for `speech` templates.
4. Whether a regression test should assert that speech text fits inside the effective safe region, not just inside the rectangular box.
5. How to repair the broken test import in a robust way.

## Desired implementation direction
The likely best fix is:
- keep the split analyzer/renderer pipeline
- preserve current attachment/ranking logic
- make speech-bubble text fitting more conservative than rectangular box fitting
- add a speech-specific safe region used both for fit checks and final text placement
- add/repair deterministic regression coverage

## Hard scope
Prefer to stay within:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `tests/test_balloon_pipeline_ep001.py`

Do not drift into unrelated webtoon-generation or prompt-design files.
Do not touch the character-consistency art lane unless strictly required.

## Verification requirements
Codex should not stop until it has externally verifiable evidence for:
1. syntax validity:
   - `python -m py_compile docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py tests/test_balloon_pipeline_ep001.py`
2. test pass:
   - `pytest -q tests/test_balloon_pipeline_ep001.py`
3. regenerated output:
   - rerender a fresh output directory from current `generated_fal_v3`
4. visual plausibility:
   - confirm no obvious text-overflow remains in the new longscroll output

## Deliverables expected
- fixed source files
- repaired test file
- passing verification commands
- a new regenerated ballooned output directory for review
- concise summary of what actually caused the overflow and how it was fixed

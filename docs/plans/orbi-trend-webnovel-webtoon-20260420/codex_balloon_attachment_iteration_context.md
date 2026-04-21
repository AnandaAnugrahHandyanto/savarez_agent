# Codex Iteration Context — Residual Attachment Quality Issues

## Current state
Attachment-quality implementation has landed and tests pass.

Verified:
- `tests/test_balloon_pipeline_ep001.py` now passes with 14 tests.
- `generated_fal_v3_ballooned/ep001_ballooned_longscroll.png` exists.
- Attachment contract fields and manifest diagnostics were added.

## Remaining visual problem
Visual review still says the balloons can feel slightly mechanical:
- p02: readable, but still feels like a balloon placed near the speaker rather than fully attached
- p06: better than before, but still has a slightly safe/algorithmic placement feel
- p08: understandable, but the speech attachment still feels less natural than ideal in a mixed-mode panel

The main residual issue is:
- balloons are less wrong now, but still sometimes look like **safe-zone placements with better tails**, not truly actor-driven composition.

## What to improve in this iteration
Without re-architecting again, tighten the implementation around:
1. stronger preference for speaker-local placement over generic safe zones
2. shorter, more natural speech-balloon-to-speaker distance where possible
3. better tail entry-side choice and tail geometry so the tail feels connected, not bolted on
4. better handling of p02 / p06 / p08 specifically if needed through bounded overrides
5. preserve mixed-mode correctness and test coverage

## Constraints
- Do not regress existing passing tests; update tests only if behavior contract legitimately changes
- Keep `generated_fal_v3` as source art baseline
- Keep split analyzer -> renderer pipeline
- No new dependencies
- If you find another concrete visual failure during the run, keep iterating within the same execution until the result is materially better

## Success condition
Return with:
- updated implementation
- regenerated attachment-quality outputs
- tests passing
- a materially improved balloon attachment feel on p02/p06/p08 compared with the current version

# Codex Iteration Context — Residual Mixed-Mode Attachment On p08

## Current verified state
- Attachment-quality implementation landed
- Tests pass: 14 passed
- A second attachment iteration was run and rendered to `generated_fal_v3_ballooned_attach2`

## Latest visual verdict
Current ranking after the latest iteration:
- p06: best / materially improved
- p02: improved but still slightly conservative
- p08: still the weakest because mixed-mode elements compete and the speech attachment still feels a bit artificial

## Remaining target
This iteration should focus primarily on **p08 mixed-mode attachment quality**, and secondarily tighten p02 if a low-risk improvement is obvious.

The issue is not general architecture anymore. It is:
- in mixed-mode panels, the speech balloon still competes with chat_ui/caption layers
- the speech balloon may be logically correct but not compositionally “locked” to the mother strongly enough
- the resulting attachment reads better than before, but still not fully natural

## Constraints
- Keep split analyzer -> renderer pipeline
- Keep generated_fal_v3 as source art baseline
- Do not regress passing tests
- No new dependencies
- Prefer bounded panel/item overrides and scoring improvements over broad rewrite

## Desired outcome
- p08 speech balloon should read more clearly as attached to the mother
- mixed-mode coexistence should remain readable
- tests remain green
- regenerate output artifact(s)

## Suggested focus areas
- p08 item override / speaker-local zone priority
- p08 tail override / entry edge / anchor preference
- mixed-mode penalty tuning so speech does not drift to a merely safe but compositionally weak zone
- if useful, add or refine panel-specific override data rather than global heuristic churn

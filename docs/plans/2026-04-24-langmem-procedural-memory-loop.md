# Reviewed procedural-memory loop for Hermes LangMem

## Goal

Turn prompt optimization into a formal review loop for Hermes without auto-patching the live system prompt.

## What counts as a prompt-worthy failure

A failure is prompt-worthy when:
- the agent had the right tools available but consistently framed or prioritized the task badly
- the failure reflects reusable instruction gaps rather than one-off user context
- the problem survives across multiple trajectories or reviewers can clearly articulate the missing guidance

A failure is **not** prompt-worthy when it is mainly:
- missing retrieval
- bad ranking
- tool breakage
- auth or environment problems
- temporary project-specific state
- user-specific data that belongs in memory, not policy

## Workflow

1. Collect failed trajectories into a JSON review set.
2. Run `scripts/langmem_prompt_review.py` to emit a review packet under `tmp/langmem-prompt-review/`.
3. Inspect whether the failures are really prompt-shaped.
4. If they are, use the review packet as the handoff surface for a human-reviewed optimization pass.
5. Review candidate prompt deltas manually.
6. Apply approved deltas in the actual prompt source, not in an automatic background patcher.
7. Re-run the relevant evals before shipping the prompt change.

## Who reviews optimized prompt text

Human review is mandatory before any prompt delta lands.

The reviewer should check:
- whether the change generalizes
- whether it duplicates an existing instruction
- whether it overfits to a single user or one weird session
- whether the change would create broader regressions or verbosity bloat

## Where approved prompt deltas are applied

Approved prompt deltas should be applied in the real Hermes prompt sources and code review flow.

They should **not** be:
- auto-written into the current system prompt
- silently injected into memory stores
- merged without a human-readable diff

## What should never be auto-learned

Never auto-learn:
- user-specific temporary task state
- secrets, credentials, or security-sensitive instructions
- one-off exceptions that are not stable policy
- prompt text inferred from broken tools or missing auth
- irreversible behavioral policy changes without review

## Script stub boundary

`scripts/langmem_prompt_review.py` is intentionally a scaffold.

It currently:
- loads sample trajectories from JSON
- builds a review packet
- marks where `create_prompt_optimizer` would fit later
- writes `tmp/langmem-prompt-review/latest.json`

It does **not**:
- call the optimizer yet
- patch prompts automatically
- modify Hermes runtime behavior

## Review packet expectations

A useful packet should include:
- failure counts by category
- representative sample trajectories
- explicit TODOs for optimizer integration
- a reviewer checklist separating prompt failures from retrieval or tooling failures

## Success condition

Hermes can improve prompt policy through a deliberate human-reviewed loop without turning prompt learning into an opaque self-modifying system.

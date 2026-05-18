# Existing product evidence / branch arbitration

Use when crypto_bot readiness is green and the strategic plan points at a next session, but local branches or logs suggest that session (or a later one) already has committed local evidence.

## Pattern

1. Do not immediately create or overwrite product files just because `plan.json` says a session is `planned` or `next_recommended_session_id` points at it. First inspect live git branches/logs for existing `hermes/<session>*` branches and evidence paths.
2. Check whether the candidate branch is ahead of `origin/main`, whether its changed paths match the strategic-plan allowlist, and whether completion-gate/sidecar artifacts already exist under `/Users/preston/.local/state/hermes-operator/`.
3. If the branch already contains plausible evidence for the selected session, classify the work as branch/evidence arbitration or review-gate closure instead of duplicating the product docs.
4. If you accidentally start writing over existing evidence on a branch that already contains the target outputs, stop, inspect the diff, and restore the overwritten files unless the intended task is explicitly a repair of those files.
5. Return the checkout to the branch that was active at run start unless you intentionally completed and committed a new selected task on a different branch.
6. Report the discovered branches, commits, evidence artifacts, and why you did or did not proceed to the next session.

## Pitfalls

- `plan.json` status can lag behind local committed branches and completion-gate artifacts. Treat live git/evidence as higher-confidence state for dispatch decisions.
- Do not downgrade or shorten an existing detailed contract by overwriting it with a simpler regenerated version. If the task is duplicate detection, preserve the existing committed evidence and move to arbitration.
- S017B-style tasks may have `requires_review_before_next_session: true`; even when local evidence exists, do not dispatch S017C until review/arbitration is recorded or the control plane says the review gate is satisfied.

## Session-derived example

A sleep-window PM run repaired Hermes control-plane parity, then saw `plan.json` point at `S017A`. Git showed `hermes/S017A-runpod-automation-gap-mapping` at commit `6adba5d` with completion-gate/sidecar artifacts, and existing S017B/S017F-style evidence appeared in branch history. The correct next action was not to regenerate product docs; it was to preserve the product checkout, report the arbitration need, and queue review/readiness reconciliation before S017C.
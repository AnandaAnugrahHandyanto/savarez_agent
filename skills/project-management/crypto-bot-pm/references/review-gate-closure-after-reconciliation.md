# Review gate closure after branch/evidence reconciliation

Use when crypto_bot readiness is green, a strategic-plan session has already produced local evidence, and the remaining safe action is to close a review-required boundary without advancing into a later approval-gated session.

## Pattern

1. Start from live control-plane truth, not plan labels alone: verify Hermes source state, product repo branch/HEAD, readiness booleans, and any existing completion-gate/sidecar artifacts.
2. If the candidate session already has a committed branch-local reconciliation artifact and a passing completion gate, do not regenerate or overwrite the original implementation/docs. Add a narrow review-gate closure artifact inside the same allowlisted evidence pattern.
3. The closure artifact should explicitly list:
   - strategic-plan session ID/title and allowlist source;
   - reviewed branch and prior HEAD;
   - existing sidecar/completion-gate artifact paths and hashes when available;
   - related committed evidence chain;
   - exact closure decision and remaining gates;
   - non-actions proving no provider/cloud/runtime/Gitea/financial surface was touched.
4. Force-add ignored evidence paths such as `_codex_discovery/**` when they are intentionally allowlisted and validator-gated.
5. Commit the closure artifact locally, render a fresh final sidecar prompt for the new HEAD, run the Codex audit, then rerun `crypto_bot_completion_gate.py` for the exact base/branch/new HEAD. The prior passing gate does not cover the new review-closure commit.
6. Report both the control-plane/readiness state and the new product evidence path. Keep remote/PR/CI/merge readiness separate from local autonomy readiness.

## Pitfalls

- Do not treat `ready_for_next_task: true` as permission to skip a session's `requires_review_before_next_session` boundary when live evidence shows that review is the actual next safe work.
- Do not advance into S017G/provider lifecycle proof merely because S017F local mapping evidence is complete. Provider API calls, credential setup/reference, cloud-cost/provisioning, and lifecycle automation remain separately gated.
- Do not reuse an old sidecar/completion-gate artifact after adding the review closure file; regenerate sidecar and completion-gate evidence for the new HEAD.
- Do not report a clean/ahead/behind state without fresh `git status --short --branch` evidence.

## Session-derived example

During a sleep-window PM run, readiness became green after repairing installed/source `crypto-bot-pm` skill parity. The product branch `hermes/S017F-plan-readiness-reconciliation` already had a passing S017F reconciliation gate at `8e137ca`. Because the strategic plan still marked S017A-S017F as planned and S017F required review before next session, the safe action was a branch-local review closure note under `_codex_discovery/autoresearch_runpod_provider_readonly_preflight/`, followed by a new commit, Codex sidecar audit, and completion gate for HEAD `9a0622e`. No provider API, credential, cloud, runtime, Gitea, workflow/runner, broker/trading, push, PR, or merge action was taken.
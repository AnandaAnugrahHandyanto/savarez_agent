# Plan Track Readiness Reconciliation

Use this reference when crypto_bot strategic-plan summaries, recently completed session IDs, native Kanban/readiness, and provider/runtime approval gates disagree about the next safe work item.

## Durable lesson

Before selecting a new implementation task, reconcile the live track boundary. If the already-validated local branch history shows a sequence such as S017A–S017F completed, do not repeat those sessions and do not jump into the next provider/cloud/runtime surface merely because the strategic plan mentions it. Record a small branch-local reconciliation artifact when that artifact itself is allowlisted and advances plan integrity.

## Safe branch-local pattern

1. Read the strategic-plan item/session IDs, the current branch/HEAD state, and the live readiness/control-plane signals.
2. Identify the highest already-completed local slice and the first blocked or approval-gated continuation.
3. If the next continuation touches provider APIs, cloud resources, runtime services, broker/trading/financial surfaces, Gitea writes, runners/workflows, or secrets, classify it as blocked/escalation-required even if broad code-work approval exists.
4. Prefer a neutral, allowlisted evidence/reconciliation path that documents the boundary without triggering blocked path-token hygiene. Avoid filenames that contain hard-surface tokens unless the selected task explicitly allowlists them and the completion gate accepts them.
5. If a reconciliation branch already exists with prior evidence, first inspect whether the branch/HEAD is still current and clean. A fresh revalidation pass (targeted validators, regenerated sidecar prompt/result, and a new completion-gate JSON for the same HEAD) is valid progress and safer than adding churn just to create a new diff.
6. Run targeted validators, `git diff --check`, secret/governance validators, post-commit Codex sidecar audit, and the completion gate on the exact HEAD.
7. For the Hermes-owned Codex sidecar wrapper, use `--result-file` (not `--output-file`) along with `--mode audit-readonly --repo-root ... --prompt-file ...`; keep prompt/result files outside the product repo.
8. Update local Kanban/commentary with branch, commit, changed files, validators, sidecar path, completion-gate path, and explicit non-actions. Do not mutate Gitea unless separately authorized.

## Reporting requirements

Report the reconciliation as plan-integrity work, not as provider/runtime progress. Include:

- selected plan source/session ID;
- branch and exact commit;
- changed reconciliation artifact path;
- validator results;
- sidecar result path;
- completion-gate JSON path and status;
- exact next blocked boundary and the approval surface required.

## Pitfall

Do not treat a planning-summary `next_recommended_session_id` as permission to skip readiness arbitration. Live machine-verifiable state and hard-forbid surfaces win over stale plan pointers.
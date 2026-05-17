# S006 approved code-scope evidence repair pattern

Session-derived pattern for resolving S006 remote-lifecycle blockers after the Operator grants broad approval for code-related work that advances documented plans.

## Durable lesson

When the Operator explicitly approves code-related work, do not keep treating every non-doc path as impossible. Preserve hard safety boundaries (secrets, broker/trading/financial APIs, live runtime/deploy, protected-branch merge), but allow the managed-project descriptor and strategic plan to carry explicit path allowlists for code, validation, workflow, and evidence files that are part of the documented S006 branch/PR repair.

The completion gate should not silently discard non-doc allowlist entries. It should:

- load descriptor/strategic-plan allowlists as the source of path authority;
- fail closed for secret-like, broker/trading/financial, runtime database, deploy/GitOps, and unallowlisted workflow/runtime surfaces;
- classify explicitly allowlisted non-financial code paths as `allowed_operator_approved_code`;
- classify explicitly allowlisted workflow files as `allowed_operator_approved_workflow` only when the path is named by the managed-project descriptor/plan;
- keep unallowlisted workflow files blocked.

## S006 remote blocker triage loop

If PR/CI audit reports stale evidence for a live PR head:

1. Resolve live PR HEAD and target branch from Gitea/read-only audit, not from stale packet paths.
2. Run completion gate for that exact HEAD and inspect blockers.
3. If blockers include blocked surfaces, decide whether they are genuinely forbidden or explicitly approved documented code surfaces.
4. If they are approved code surfaces, update the managed-project allowlist and policy scanner tests before re-running the gate.
5. If blockers include ruff failures, fix the product branch locally and validate with `ruff check <changed-python-files>` plus `git diff --check`.
6. Generate a fresh final sidecar prompt/result for the new exact HEAD. Stale sidecar evidence from the previous head must remain a blocker.
7. Re-run completion gate. Only after `PASS`, generate a fresh PR evidence packet for the same HEAD.
8. Push/update PR only after local gate and PR evidence are aligned to the new HEAD; then wait for CI and rerun PR/CI audit.

## Pitfalls

- Do not repair stale PR evidence by weakening source-head matching. The correct fix is fresh completion/PR evidence for the live head.
- Do not claim S006 resolved when only blocked-surface blockers were removed. Ruff and sidecar-head/range mismatches still block completion.
- Do not use a temporary minimal worktree as final evidence for the real PR unless it becomes the actual branch/PR head.
- Avoid direct Gitea database mutations for PR/evidence work; use Hermes/Gitea APIs or the approved adapters, and never print tokens.
- `ruff format` remains forbidden; use targeted source edits and `ruff check`.

# Post-push PR/CI evidence after approved stale-branch repair

Session-derived pattern: Operator approved exactly one controlled remote branch push for an existing crypto_bot S006 PR branch, followed only by read-only PR/CI evidence checks.

Safe sequence after approval:

1. Reconfirm approval scope, local branch, exact local HEAD, clean worktrees, and current remote branch SHA before pushing.
2. Push only the exact approved commit to the exact existing remote source branch, e.g. `git push origin <full-head>:refs/heads/<source-branch>`.
3. Immediately verify with read-only `git ls-remote origin refs/heads/<source-branch>`.
4. Run read-only PR/CI audit against the pushed head.
5. Poll read-only PR/CI audit briefly to distinguish transient `pending` from a terminal blocker.
6. Stop before PR metadata/body/comment/status/check mutation, runner/workflow starts, merge, deploy, runtime, secrets, or broker/trading actions unless a separate exact approval covers that action.

Expected post-push classifications:

- If PR branch now matches the locally validated HEAD but CI is not complete, classify as `pr_created_ci_pending` rather than stale branch mismatch.
- If the PR body still links older completion/PR-evidence artifacts, do not update those links under a branch-push-only approval. Report blockers such as `completion_gate_source_head_mismatch` or `pr_evidence_source_head_mismatch` precisely as stale evidence-link/metadata issues.
- A successful branch push proves only branch synchronization. It does not prove CI readiness, merge readiness, updated PR evidence links, or authority to dispatch the next product task.
- If CI remains pending and runner status is unreadable, the next step is read-only wait/polling or a separately approved runner/CI inspection path, not unilateral runner/workflow action.

Reporting checklist:

- Push command shape and exit status.
- Pre-push remote SHA and post-push remote SHA.
- Existing PR number and URL from Gitea output or read-only audit.
- Latest PR/CI audit artifact path.
- `pr_matches_spec`, PR head SHA, `ci_state`, `ci_evidence_ready`, `merge_ready`, and `s006_remote_lifecycle_state`.
- Explicit non-actions: no new PR, no PR metadata/comment/status/check update, no runner/workflow start, no merge, no deploy, no secrets, no runtime/broker/trading actions.

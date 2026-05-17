# Stale PR branch / local completion HEAD mismatch

Session-derived pattern: local S006 completion evidence passed for a newer branch-local HEAD while the existing Gitea PR source branch still pointed at an older SHA.

Symptoms from read-only probes:

- Control-plane self-check passes, but readiness says `ready_for_next_task: false` and S006 remote lifecycle blocks next task.
- Kanban audit classifies the board as `IMPORT_VALID_REMOTE_LIFECYCLE_BLOCKED` with S006 in `review_required`.
- `crypto_bot_pr_ci_audit.py` reports blockers such as `s006_pr_identity_mismatch`, `ci_evidence_stale_for_nonmatching_pr_head`, `completion_gate_source_head_mismatch`, or `pr_evidence_source_head_mismatch`.
- Gitea PR pilot dry-run / `--create-pr-only --preflight-only --no-push` reports both `Remote source branch points to a different SHA` and `An open PR already exists for source branch to target`.
- `git ls-remote origin refs/heads/<source-branch>` confirms the remote branch SHA differs from the local validated HEAD.

Correct classification:

- This is not a new-PR request state. The PR already exists.
- This is not permission to dispatch the next product task. Remote lifecycle remains open.
- This is a stale remote PR branch / head mismatch.

Safe next sequence:

1. Keep all probes read-only until explicit approval exists.
2. Generate fresh local-head completion and PR-evidence packets if local validated HEAD changed.
3. Run read-only remote readiness, PR/CI audit, merge-readiness dry-run, PR pilot self-check, and PR pilot dry-run/preflight.
4. If the remote PR branch is stale and an open PR already exists, ask only for a narrowly scoped controlled remote branch update to push the exact local validated HEAD to the existing remote branch.
5. Do not create a new PR, update PR metadata/comments/statuses/checks, start workflows/runners, merge, deploy, inspect secrets, or perform runtime/broker/trading/financial actions as part of the stale-branch repair.
6. After an approved branch update, collect read-only PR/CI evidence again and only then classify CI/merge readiness.

Reusable approval wording should name the exact repo, task, source branch, local HEAD, existing PR number, and forbidden actions.
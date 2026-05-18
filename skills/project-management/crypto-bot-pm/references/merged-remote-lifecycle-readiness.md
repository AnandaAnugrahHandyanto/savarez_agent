# Merged Remote Lifecycle Readiness

Use this when crypto_bot control-plane tools disagree after an S006-style PR has actually merged.

## Durable lesson

A live PR/CI audit state of `s006_remote_lifecycle_state: "merged"` is stronger lifecycle evidence than stale pre-merge CI/evidence booleans. If a Kanban/readiness audit still reports `IMPORT_VALID_REMOTE_LIFECYCLE_BLOCKED`, `remote_done: false`, or recommends holding next-task dispatch while the same live PR/CI audit reports the PR is merged, treat that as Hermes control-plane inconsistency, not product incompletion.

## Safe repair pattern

1. Keep the product repo untouched unless there is a separate selected product task.
2. Repair the Hermes control-plane tool that derives Kanban remote lifecycle state so `merged` and `remote_lifecycle_complete` are terminal remote-done states.
3. Preserve pending/stale CI details as diagnostic fields, but do not let them override a verified merged PR lifecycle state for next-task readiness.
4. Add a focused regression test for the merged-state interpretation.
5. Validate with the Hermes test wrapper, not direct pytest:
   - `scripts/run_tests.sh tests/test_crypto_bot_tenacity_control_plane.py -q`
6. Rerun the control-plane preflight/readiness tools and verify all of the following before reporting readiness:
   - self-check blockers are empty
   - `native_control_plane_ready: true`
   - `ready_for_next_task: true`
   - Kanban classification is `IMPORT_VALID_READY_FOR_NEXT_TASK`
7. Commit the Hermes control-plane repair locally on a non-protected branch.

## Pitfall

Do not "fix" this by mutating Kanban cards, editing product evidence, starting runners/workflows, refreshing statuses, pushing, creating PRs, or touching Gitea. The bug is in lifecycle-state arbitration when a read-only audit already proves the PR merged.
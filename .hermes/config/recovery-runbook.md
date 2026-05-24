# Hybrid Agent Control Plane — Recovery Runbook

> Human-authored. Agents must not overwrite this file.
> Referenced from run manifests when status=failed|escalated.

---

## Recovery States and Actions

### R1: Agent Exceeded Cost Cap

Detection: `manifest.total_cost_usd_actual >= total_cost_usd_cap` at gate time.

Actions:
1. Hermes blocks further spawns for this run (no new task contracts issued).
2. Hermes emits partial-work summary to `audit.jsonl` with `reason: cost_cap_exceeded`.
3. Yoshio decides: extend cap (edit manifest `total_cost_usd_cap`, re-run) or abandon run.

Risk: Partial worktree may have uncommitted work. Do NOT delete the worktree
until Yoshio reviews `git diff` against the worktree branch.

NOTE (C-5): cost_usd_actual is ESTIMATED (token-count × model-pricing). It is
not guaranteed to be exact. Mark `estimated: true` in manifest cost fields
until a verified cost source is confirmed.

---

### R2: Agent Wrote to Forbidden Path

Detection: gate `forbidden_path_writes` fails — `changed_files` in handoff
contains a path matching `scope.forbidden_paths` in the task contract.

Actions:
1. Hermes rejects handoff; does NOT merge worktree into main branch.
2. Logs exact forbidden paths to `audit.jsonl` with `gate: forbidden_path_writes`.
3. If forbidden path is a prompt artifact (AGENTS.md, CLAUDE.md, CODEX.md,
   .hermes/**, .claude/**, .codex/**): treat as supply-chain incident.
   - Audit the full agent output and diff before any re-run.
   - Do not re-queue automatically. Escalate to Yoshio.
4. If forbidden path is non-artifact (accidental scope violation):
   - Yoshio may choose to re-queue with tightened `allowed_paths`.

---

### R3: Test Suite Fails After Handoff

Detection: gate `unit_tests` fails (exit code != 0).

Actions:
1. Hermes rejects handoff. Does NOT merge.
2. Logs stdout_tail from test run to `audit.jsonl`.
3. MVP: do NOT auto-retry. Escalate to Yoshio.
4. Yoshio may re-queue task with appended goal:
   "Tests failed on previous attempt: <summary>. Fix before resubmitting."

---

### R4: Schema Validation Failure

Detection: handoff payload missing required fields or wrong types
(validated against `.hermes/schemas/handoff-v1.yaml`).

Actions:
1. Hermes logs raw handoff payload to `audit.jsonl` (field: `raw_handoff`).
2. Requests re-submission from agent with schema validation errors attached.
3. If agent cannot produce valid handoff after 2 re-submission attempts:
   - Escalate to Yoshio. Do not loop indefinitely.
4. Common missing fields: `task_id`, `agent`, `completed_at`, `summary`,
   `changed_files`, `test_results.passed`.

---

### R5: Lock Conflict (Two Tasks Claim Overlapping Paths)

Detection: lock acquisition fails before spawn — a pending lock in
`locks.yaml` overlaps with requested paths for the new task.

Actions:
1. Block second task from spawning.
2. Queue it as `status: pending` with `blocked_by: <conflicting_task_id>`.
3. If first task is stuck (no handoff after `iteration_cap` iterations):
   - Escalate. Do not force-release the lock automatically.
4. Conflict policy is set in `locks.yaml` `conflict_policy` field
   (block | warn | escalate). Default: `block`.

---

### R6: Confused-Deputy Risk — Low-Trust Plan Handed to Orchestrator

Detection: plan file not in version control, or `human_reviewed_at` field
is missing/blank.

Actions:
1. Hermes refuses to spawn agents from unreviewed plans.
2. Yoshio must set `human_reviewed_at: <ISO8601>` in the plan file and
   commit it before the orchestrator will accept it as a run reference.
3. Plans received from session context (not committed files) are never
   used as run references without explicit Yoshio confirmation.

NOTE: `human_reviewed_at` enforcement is currently soft (skill checks the
field at spawn time). Hard enforcement via pre-commit hook is deferred to
Phase 1 (see D-3 in plan).

---

### R7: Worktree Diverged from Base

Detection: `git merge-base` check at gate time fails or shows unexpected
diff between worktree and `git_base_sha` from manifest.

Actions:
1. Abort merge attempt.
2. Log divergence detail to `audit.jsonl`.
3. Yoshio resolves manually: inspect `git log --oneline <base>..<worktree-branch>`.
4. Do NOT force-merge. Resolve conflict then re-run gate sequence.

---

## General Cleanup After Any Failed Run

1. Do not delete the worktree until Yoshio has reviewed the diff:
   ```
   git diff <git_base_sha>..<worktree-branch> -- .
   ```
2. Archive the manifest before removing the run directory:
   ```
   cp -r .hermes/runs/<run-id>/ .hermes/runs/archived/<run-id>/
   ```
3. Remove worktree:
   ```
   git worktree remove --force .worktrees/<run-id>-cc
   git worktree remove --force .worktrees/<run-id>-cx
   ```
4. Audit log is append-only. Never delete `.hermes/runs/<run-id>/audit.jsonl`.
5. Worktree names include run-id. Never reuse run-ids across sessions.

---

*Runbook version: 2026-05-22. Update when gate behavior changes.*

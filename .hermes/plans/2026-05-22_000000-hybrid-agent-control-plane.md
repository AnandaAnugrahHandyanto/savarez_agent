# Hybrid Agent Control Plane: Hermes + Claude Code + Codex

**Status:** Phase 1 implementation in progress — locked decisions encoded; skill drafts, eval harness, and pytest coverage added
**Date:** 2026-05-22
**Author:** Yoshio (via planning session)
**Slug:** hybrid-agent-control-plane

<!-- MACHINE-CHECKABLE FIELDS — do not reformat these lines -->
human_reviewed_at: 2026-05-22T23:27:28Z
phase1_locked_at: 2026-05-22T23:27:28Z
<!-- END MACHINE-CHECKABLE FIELDS -->

---

## Goal

Build a secure, auditable, cost-bounded orchestration layer on top of Hermes
that routes coding tasks to Claude Code and/or Codex as bounded workers,
enforces per-task contracts, and gates results before they land in a shared
repo. Hermes is the control plane; agents are trusted workers with explicit
capability grants, not autonomous co-owners.

---

## Guiding Constraints

1. Hermes is orchestrator, not peer. Agents never hand back to each other
   without a Hermes gate in between.
2. Worktrees are isolation-of-state, not security isolation. Strong isolation
   requires containers or per-agent HOME. MVP may defer containers but must
   document the gap and not pretend worktrees are sandboxes.
3. Prompt artifacts (AGENTS.md, CLAUDE.md, .claude/**, .codex/**,
   .hermes/**, .planning/**) are supply-chain artifacts. They must be version-
   controlled, reviewed on change, and never silently overwritten by agents.
4. No --dangerously-skip-permissions on real host filesystems.
5. One canonical instruction source per repo; agent-specific files are thin
   adapters that reference it, not duplicate it.
6. Every run emits a manifest. Every task has a contract. Every handoff has a
   schema. Every resource has a lock claim.
7. MVP is skills + templates + eval harness. Core Hermes code changes come
   after the workflow is validated.

---

## Non-Goals for MVP

- Full container-per-agent isolation (documented gap, deferred to Phase 3).
- Merging the kanban worker into this system (integration point noted but out
  of scope until Phase 2 validated).
- A new core Hermes CLI command or plugin (use skills + slash commands first).
- Automatic agent self-repair loops (agents propose fixes; Hermes human gate
  approves).
- Cost optimization or model routing across multiple providers.
- Support for agents other than Claude Code and Codex.
- Reuse of any GSD repo installers or npx @latest patterns. Templates are
  vendored here.

## Phase 1 Locked Decisions (approved 2026-05-22T23:27:28Z)

These decisions were locked by Yoshio and encoded in Phase 1 implementation artifacts.
They supersede open decisions D-1 through D-6 for the MVP scope.

**LD-1 Isolation: worktrees for MVP/Phase 1.**
  Git worktrees are the isolation mechanism for Phase 1. This is merge
  isolation only — NOT security isolation. A worker agent in a worktree
  can read/write any path on the host that the Hermes process can access.
  Container-per-agent isolation and per-agent HOME are explicitly deferred
  to Phase 3. All run manifests must carry `worktrees_are_sandbox: false`
  and `container_isolation: false`. This gap must be documented in every
  run manifest until Phase 3 ships.

**LD-2 Handoff: file-based handoff is canonical.**
  The YAML handoff file at `.hermes/runs/<run-id>/handoffs/<task-id>.yaml`
  is the single source of truth. Worker stdout may print a sentinel line
  of the form `HANDOFF_PATH: <path>` so Hermes can locate the file, but
  the file content is authoritative. Stdout parsing alone is not permitted
  as a handoff mechanism. If the file is absent, the handoff is rejected.

**LD-3 Human signoff: enforced via repo-local check script.**
  Plans without a non-empty `human_reviewed_at` field cannot be used as a
  run reference for any worker execution or real mutation phase.
  Conservative/docs-only phases (Phase 0) may proceed without it.
  Worker execution (Phase 2+) is blocked if `human_reviewed_at` is empty
  or absent. The enforcement mechanism is `scripts/check_hybrid_control_plane.py`
  (run before commit and at gate time). Soft skill wording alone is
  insufficient; pre-commit hooks are additive but not the primary gate.

**LD-4 Gate parallelism: serial gates for MVP.**
  All gates run in the order defined by `gate-taxonomy.yaml` and
  `eval-matrix.yaml`: static gates first, then dynamic (tests), then human.
  No parallel gate execution until Phase 2 timing data shows >2 min
  serial gate overhead. Rationale: serial gates are easier to audit and
  debug; the MVP must first establish that gates work correctly before
  optimizing throughput.

**LD-5 CODEX.md and Codex adapter: opportunistic/non-blocking.**
  `CODEX.md` is a provisional, explicitly-unverified stub. The Codex
  adapter is NOT relied upon for Phase 1 or Phase 2. `sandbox_verified`
  remains `false`. No Codex-specific logic is implemented in MVP; all
  Codex paths in templates are marked PROVISIONAL. Phase 2 canary test
  (task 2.1) must pass before Codex is used for real work.

**LD-6 Cost tracking: estimated fields only in MVP.**
  Manifests and contracts carry `cost_estimated: true` and
  `total_cost_usd_actual: ~` (null until filled). External agent costs
  are estimated via token-count × model-pricing, not exact provider data.
  The `cost_usd_actual` field in task entries is set to null with
  `cost_estimated: true`. Full per-run cost ledger is deferred to Phase 3.
  No cost tracking code is added to Hermes core in Phase 1.

---

## Conservative MVP Tightening (added 2026-05-22)

> These caveats were tightened after plan review. They supersede any
> conflicting text in Phase 0/1 tasks below.

**C-1 route-dev-task already exists.**
  `~/.hermes/skills/_custom/route-dev-task/SKILL.md` exists and handles
  task routing to the dev-profile Hermes subprocess. The conservative MVP
  must NOT create a second route-dev-task skill. Phase 1 task 1.3 should
  instead document how the hybrid-agent-control-plane integrates with or
  extends the existing skill. No new route-dev-task file is written in
  this phase.

**C-2 Skill location: repo-local over user-profile.**
  Conservative MVP artifacts (schemas, configs, templates, fixtures) live
  under `.hermes/` in the repo. User-profile skill creation
  (`~/.hermes/profiles/dev/skills/`) is deferred to Phase 1 and must be
  explicitly decided by Yoshio before writing into the user profile. If a
  skill skeleton is useful earlier, place it as a draft under
  `.hermes/templates/` or `docs/` to avoid polluting installed skills.

**C-3 delegate_task does not directly spawn Claude Code/Codex by default.**
  Real external worker execution is terminal CLI-based and belongs in
  Phase 2. The conservative MVP only defines adapter contracts and
  templates. Any skill language referencing "spawns agent via
  delegate_task" means: writes the contract + calls terminal() to invoke
  the CLI. Document this as the intended mechanism; do not assume
  delegate_task auto-discovers external CLI agents.

**C-4 Codex adapter path is TBD.**
  Codex CLI docs and current behavior are unverified. CODEX.md is
  provisional (created only because the repo already has CLAUDE.md as a
  precedent, and CODEX.md is marked explicitly as unverified). The Codex
  adapter in capability-matrix.yaml has `sandbox_verified: false` and
  `cli_behavior_confirmed: false`. Do not treat Codex as production-ready
  until Phase 2 canary test (task 2.1) passes.

**C-5 Cost tracking: external agent costs are estimated, not exact.**
  Hermes does not guarantee per-external-agent cost data. Use token-count
  × model-pricing estimation as the primary accounting method for Phase 1.
  Mark `cost_usd_actual` fields in manifests as `estimated: true` until
  exact cost data is confirmed available from agent internals
  (see D-6 / Assumption 6).

**C-6 Prompt artifact gate: repo-local check script, not CODEOWNERS alone.**
  CODEOWNERS may not enforce local-only workflows (no PR required in solo
  dev). A local check script (`scripts/check_hybrid_control_plane.py`)
  is the primary pre-commit verification mechanism. CODEOWNERS is
  additive when PRs are used, not the sole gate.

---

## Architecture Overview

```
User / Trigger
    |
    v
Hermes (control plane)
  |-- reads: run-manifest.yaml, task-contract.yaml
  |-- acquires: resource lock map
  |-- spawns: Claude Code worker  (worktree or container)
  |           Codex worker        (worktree or container)
  |-- gates:  capability check, path lock check, cost check
  |-- receives: handoff payload (schema-validated)
  |-- runs: eval matrix against handoff
  |-- decides: merge / request-changes / escalate
  |-- emits: run manifest update, audit log entry
    |
    v
Repo (protected main branch)
```

Control flow is always Hermes -> Agent -> Hermes. Agents never push to main
directly. Gate results are structured and logged.

---

## Data Model / Spec Sections

### 1. Run Manifest

File: `.hermes/runs/<run-id>/manifest.yaml`
Written by Hermes at start; updated at each phase; immutable after close.

```yaml
run_id: <uuid>
triggered_by: <user|cron|webhook>
trigger_ref: <session-id or event-id>
started_at: <ISO8601>
closed_at: ~
status: running|completed|failed|escalated

plan_ref: .hermes/plans/<plan-file>.md   # which plan this run executes
git_base_sha: <sha>                      # HEAD at spawn time
worktree_paths:                          # CONFIRM: actual worktree root
  claude_code: ~/hermes-agent/.worktrees/<run-id>-cc   # CONFIRM path convention
  codex:       ~/hermes-agent/.worktrees/<run-id>-cx   # CONFIRM path convention

tasks:
  - task_id: <uuid>
    contract_ref: .hermes/runs/<run-id>/contracts/<task-id>.yaml
    agent: claude_code|codex
    status: pending|running|handoff_received|gate_passed|gate_failed|merged|cancelled
    cost_usd_actual: ~

total_cost_usd_cap: 5.00   # hard cap; agent spawns blocked beyond this
total_cost_usd_actual: ~
audit_log: .hermes/runs/<run-id>/audit.jsonl
```

### 2. Task Contract

File: `.hermes/runs/<run-id>/contracts/<task-id>.yaml`
Written before agent spawn. Agent is handed a read-only copy. Hermes validates
the handoff against this contract.

```yaml
task_id: <uuid>
run_id: <uuid>
created_at: <ISO8601>
agent: claude_code|codex
model: claude-sonnet-4-5|codex-1    # CONFIRM: exact model identifiers

goal: |
  <one paragraph, imperative, no implementation detail>

scope:
  allowed_paths:       # relative to worktree root
    - src/
    - tests/
  forbidden_paths:
    - .hermes/
    - .claude/
    - .codex/
    - AGENTS.md
    - CLAUDE.md
  allowed_operations: [read, write, create, delete]
  forbidden_operations: [git_push, network_external, install_global]

acceptance_criteria:
  - <testable criterion 1>
  - <testable criterion 2>

eval_gates:            # which gates must pass before handoff is accepted
  - lint
  - unit_tests
  - no_forbidden_path_writes
  - diff_size_limit_kb: 500

cost_cap_usd: 2.00
iteration_cap: 40

handoff_schema_ref: .hermes/schemas/handoff-v1.yaml
```

### 3. Resource / Path Lock Map

File: `.hermes/runs/<run-id>/locks.yaml`
Prevents two agents from writing to overlapping paths simultaneously.
Must be checked before any agent spawn. Hermes holds the lock file;
agents never write it.

```yaml
run_id: <uuid>
locks:
  - task_id: <uuid>
    agent: claude_code
    claimed_at: <ISO8601>
    released_at: ~
    paths:        # glob patterns, relative to repo root
      - src/agent/**
      - tests/agent/**
  - task_id: <uuid2>
    agent: codex
    claimed_at: <ISO8601>
    released_at: ~
    paths:
      - src/tools/**
      - tests/tools/**

conflict_policy: block   # block|warn|escalate
```

Lock acquisition and release logic lives in Hermes orchestrator skill, not
in agent code.

### 4. Handoff Schema

File: `.hermes/schemas/handoff-v1.yaml`
Agent returns a structured payload when it considers the task done.
Hermes validates this payload before running eval gates.

```yaml
# Schema definition (not an instance)
handoff_schema_version: "1"
fields:
  task_id:          {type: string, required: true}
  agent:            {type: string, required: true}
  completed_at:     {type: string, format: iso8601, required: true}
  summary:          {type: string, max_len: 500, required: true}
  changed_files:
    type: array
    items: {type: string}   # relative paths from worktree root
    required: true
  test_results:
    type: object
    fields:
      command_run:  {type: string}
      exit_code:    {type: integer}
      stdout_tail:  {type: string, max_len: 2000}
      passed:       {type: boolean, required: true}
  eval_evidence:
    type: object
    fields:
      lint_clean:         {type: boolean}
      unit_tests_passed:  {type: boolean}
      diff_size_kb:       {type: number}
      no_forbidden_writes: {type: boolean}
  open_issues:
    type: array
    items: {type: string}
  self_assessed_confidence: {type: string, enum: [high, medium, low]}
```

Agent skill templates must emit this exact schema. Hermes rejects handoffs
that fail schema validation before running any gate.

### 5. Capability Matrix

File: `.hermes/config/capability-matrix.yaml`
Defines what each agent type is allowed to do in this repo. Reviewed and
updated by a human, not by agents.

```yaml
agents:
  claude_code:
    spawn_mode: worktree       # worktree|container (CONFIRM: container support available?)
    dangerously_skip_permissions: false   # hard no on real host
    allowed_toolsets: [terminal, file, web]
    forbidden_toolsets: [cronjob, send_message, delegation]
    max_parallel_instances: 2
    max_cost_per_run_usd: 5.00
    can_write_prompt_artifacts: false  # .claude/**, CLAUDE.md, AGENTS.md
    can_push_to_main: false
    can_install_packages: false        # MVP: block; Phase 3: allow in container

  codex:
    spawn_mode: worktree               # CONFIRM: Codex sandbox status in current CLI
    sandbox_verified: false            # MUST be set to true before enabling in prod
    # Codex sandbox and approvals are distinct flags; both must be confirmed.
    allowed_operations: [read, write, create, test]
    forbidden_operations: [network_external, git_push_main, global_install]
    max_parallel_instances: 1
    max_cost_per_run_usd: 3.00
    can_write_prompt_artifacts: false
    can_push_to_main: false

  hermes:
    role: orchestrator
    can_spawn_agents: true
    can_read_all_paths: true
    can_write_run_artifacts: true      # .hermes/runs/**, audit logs, manifests
    can_merge_to_main: true            # only after all gates passed
    can_write_prompt_artifacts: true   # Hermes may update AGENTS.md on Yoshio approval
```

### 6. Gate Taxonomy

File: `.hermes/config/gate-taxonomy.yaml`
Defines every gate type, its category, whether it is blocking, and who
evaluates it.

```yaml
gates:
  # -- Static / fast --
  schema_validation:
    category: static
    blocking: true
    evaluator: hermes_skill
    description: Handoff payload matches handoff-v1 schema.

  forbidden_path_writes:
    category: static
    blocking: true
    evaluator: hermes_skill
    description: changed_files contains no path matching forbidden_paths in contract.

  diff_size_limit:
    category: static
    blocking: true
    evaluator: hermes_skill
    description: Total diff KB <= contract.eval_gates.diff_size_limit_kb.

  prompt_artifact_unchanged:
    category: static
    blocking: true
    evaluator: hermes_skill
    description: Prompt artifacts (AGENTS.md, CLAUDE.md, .claude/**, .codex/**,
      .hermes/**) not present in changed_files unless explicitly whitelisted.

  # -- Dynamic / execution --
  lint:
    category: dynamic
    blocking: true
    evaluator: hermes_skill_runs_command
    description: Project linter exits 0 on changed files.
    # CONFIRM: actual lint command (ruff? eslint? mypy?) — inspect repo before hardcoding.

  unit_tests:
    category: dynamic
    blocking: true
    evaluator: hermes_skill_runs_command
    description: scripts/run_tests.sh (or equivalent) exits 0.
    # CONFIRM: actual test command — scripts/run_tests.sh probes .venv first.

  integration_tests:
    category: dynamic
    blocking: false    # non-blocking in Phase 1; promote to blocking in Phase 2
    evaluator: hermes_skill_runs_command
    description: Integration test suite exits 0.

  # -- Human / review --
  human_review:
    category: human
    blocking: true
    evaluator: yoshio
    description: Yoshio reviews diff and approves merge.
    trigger: always   # MVP: always require human approval before merge

  security_scan:
    category: human_or_tool
    blocking: false    # Phase 1: advisory; Phase 2: blocking
    evaluator: hermes_skill_or_yoshio
    description: No obvious supply-chain or injection issues in diff.

  # -- Cost --
  cost_cap:
    category: resource
    blocking: true
    evaluator: hermes_skill
    description: Run total cost <= manifest.total_cost_usd_cap.
```

### 7. Eval Matrix

File: `.hermes/config/eval-matrix.yaml`
Maps task types to required gate sets and thresholds.
Hermes selects the appropriate row based on task_contract.goal classification.

```yaml
# Gate set shortcuts
gate_sets:
  minimal:    [schema_validation, forbidden_path_writes, diff_size_limit,
               prompt_artifact_unchanged, cost_cap]
  standard:   [schema_validation, forbidden_path_writes, diff_size_limit,
               prompt_artifact_unchanged, lint, unit_tests, cost_cap, human_review]
  high_assurance: [schema_validation, forbidden_path_writes, diff_size_limit,
               prompt_artifact_unchanged, lint, unit_tests, integration_tests,
               security_scan, cost_cap, human_review]

task_types:
  docs_only:
    gate_set: minimal
    description: Changes only to .md files outside .hermes/ and prompt artifacts.

  feature:
    gate_set: standard
    description: New functionality in src/ with tests.

  refactor:
    gate_set: standard
    description: No new behavior; existing tests must still pass.

  bugfix:
    gate_set: standard
    description: Targeted fix; regression test required in handoff.

  security_adjacent:
    gate_set: high_assurance
    description: Auth, crypto, input validation, dependency updates, config.

  prompt_artifact_change:
    gate_set: high_assurance   # escalate automatically; human must approve
    description: Any change to AGENTS.md, CLAUDE.md, .claude/**, .codex/**,
      .hermes/config/**.
    blocked_agents: [claude_code, codex]  # only Hermes/Yoshio may propose these

  unknown:
    gate_set: high_assurance   # conservative default
    description: Task type not recognized.
```

### 8. Recovery State / Runbook

File: `.hermes/config/recovery-runbook.md`
Linked from manifests when status=failed|escalated.

```
RECOVERY STATES AND ACTIONS

R1: Agent exceeded cost cap
  Detection: manifest.total_cost_usd_actual >= cap at gate time
  Action:    Hermes blocks further spawns for this run.
             Hermes emits summary of partial work to audit log.
             Yoshio decides: extend cap (edit manifest, re-run) or abandon.
  Risk:      Partial worktree may have uncommitted work — do not delete
             worktree until Yoshio reviews.

R2: Agent wrote to forbidden path
  Detection: gate forbidden_path_writes fails
  Action:    Hermes rejects handoff, does NOT merge worktree.
             Logs exact forbidden paths to audit.jsonl.
             Yoshio inspects worktree diff before cleanup.
  Risk:      If agent modified prompt artifacts, treat as supply-chain
             incident. Audit the full agent output before re-running.

R3: Test suite fails after handoff
  Detection: gate unit_tests fails
  Action:    Hermes rejects handoff. Optionally re-queues task with
             "tests failed, fix before resubmitting" appended to goal.
             MVP: do not auto-retry; escalate to Yoshio.

R4: Schema validation failure
  Detection: handoff payload missing required fields or wrong types
  Action:    Hermes logs raw handoff to audit, requests re-submission from agent.
             If agent cannot produce valid handoff after 2 attempts: escalate.

R5: Lock conflict (two tasks claim overlapping paths)
  Detection: lock acquisition fails before spawn
  Action:    Block second task from spawning. Queue it pending release.
             If first task is stuck (no handoff after iteration_cap): escalate.

R6: Confused-deputy risk — low-trust plan handed to orchestrator
  Detection: plan file not in version control, or modified after last human review.
  Action:    Hermes refuses to spawn agents from unreviewed plans.
             Plan files must have a human_reviewed_at field set by Yoshio.
             CONFIRM: implement this as a mandatory manifest field, not just convention.

R7: Worktree diverged from base
  Detection: git merge-base check at gate time fails or shows unexpected diff
  Action:    Abort merge. Log divergence. Yoshio resolves manually.
             Do not force-merge.

General cleanup:
  - Worktrees are named by run-id; never reuse run-ids.
  - On abandoned run: git worktree remove --force, then delete
    .hermes/runs/<run-id>/ after archiving manifest.
  - Audit log is append-only; never delete .hermes/runs/<run-id>/audit.jsonl.
```

---

## Phases

> Implementation should inspect actual project tooling (linters, test runner,
> existing skills, config schema) before finalizing any commands below.
> Commands marked [CONFIRM] need repo inspection before use.

### Phase 0 — Foundation: Docs, Schemas, Templates (no code)

Goal: establish supply chain hygiene and shared vocabulary. No agent spawning yet.

Tasks:

0.1 Create repo-level canonical instruction file.
    File: AGENTS.md (already exists — inspect before editing)
    Action: Add a "Hybrid Agent Control Plane" section that references
    .hermes/plans/ as the plan source and .hermes/runs/ as the run store.
    Constraint: do not rewrite existing content; append a section.

0.2 Create thin agent adapter files.
    Files:
      CLAUDE.md   — ALREADY EXISTS. Inspect before editing; only append a
                    "Hybrid Agent Control Plane" section if missing. Do not
                    rewrite existing content.
      CODEX.md    — PROVISIONAL / TBD (see C-4). Create only as an explicitly
                    unverified adapter stub. Mark file header with:
                    "PROVISIONAL: Codex CLI behavior unconfirmed — do not use
                    in production until Phase 2 canary (task 2.1) passes."
                    Do NOT assume Codex reads CODEX.md from repo root; mark
                    the read-path as CONFIRM.
    These files must NOT duplicate AGENTS.md content. Reference it.
    CONFIRM: whether Claude Code CLI reads CLAUDE.md from repo root or
    .claude/ directory in the specific worktree.

0.3 Write canonical schemas.
    Files under .hermes/schemas/:
      handoff-v1.yaml
    Use the spec in the Data Model section above as starting point.

0.4 Write config files.
    Files under .hermes/config/:
      capability-matrix.yaml
      gate-taxonomy.yaml
      eval-matrix.yaml
      recovery-runbook.md
    Use the specs above as starting points. These are human-authored; agents
    must not overwrite them.

0.5 Protect prompt artifacts.
    Primary: `scripts/check_hybrid_control_plane.py` (local, runnable without
    PR infrastructure). Run before any commit touching prompt artifacts.
    Secondary (when PRs used): Add a CODEOWNERS or pre-commit hook that
    requires Yoshio approval on:
      AGENTS.md, CLAUDE.md, CODEX.md, .claude/**, .codex/**,
      .hermes/config/**, .hermes/schemas/**
    See C-6: CODEOWNERS alone is insufficient for local workflows.
    CONFIRM: whether repo has CODEOWNERS or pre-commit infrastructure.

0.6 Write run manifest and task contract templates.
    Files:
      .hermes/templates/run-manifest.yaml.j2   (or plain YAML with {{}} markers)
      .hermes/templates/task-contract.yaml.j2
      .hermes/templates/locks.yaml.j2
    Used by the orchestrator skill to generate run artifacts.

Verification for Phase 0:
  - All schema and config files are committed and reviewed by Yoshio.
  - git log --follow on AGENTS.md shows no agent-authored commits.
  - CODEOWNERS (or equivalent) in place and tested with a draft PR.

---

### Phase 1 — Skill Implementation: Orchestrator + Eval Harness

Goal: implement the Hermes skills that wire the control plane together.
Still no agent spawning in production; test with stubs.

Tasks:

1.1 Author skill: hybrid-agent-control-plane
    Location DEFERRED (see C-2): Phase 1 decision — repo-local draft under
    .hermes/templates/skill-draft-hybrid-agent-control-plane.md, OR
    ~/.hermes/profiles/dev/skills/software-development/ after Yoshio review.
    Conservative MVP: create the draft only; do not install to user profile.
    Responsibilities:
      - Accepts a goal string + task type.
      - Reads capability-matrix.yaml and gate-taxonomy.yaml.
      - Generates run manifest (from template).
      - Generates task contract (from template).
      - Acquires path locks.
      - Spawns agent (Claude Code or Codex) with scoped worktree.
      - Polls for handoff payload.
      - Validates handoff against schema.
      - Runs gates in order (static first, then dynamic, then human).
      - Merges or rejects based on gate results.
      - Updates manifest and emits audit log entry.
      - Releases path locks.
    Note: MVP skill calls existing Hermes tools (terminal, file) rather
    than adding new core code. delegate_task is NOT a direct Claude Code/Codex
    spawner — real agent execution uses terminal() to call the CLI. See C-3.

1.2 Author skill: subagent-eval-gate (or extend harness-eval)
    Location: ~/.hermes/profiles/dev/skills/software-development/
              subagent-eval-gate/SKILL.md
    Responsibilities:
      - Receives handoff payload path.
      - Reads gate-taxonomy.yaml and eval-matrix.yaml.
      - Runs each required gate for the task type.
      - Returns a structured gate-result payload (pass/fail per gate, evidence).
    CONFIRM: whether existing harness-eval skill covers this or needs extension.
    Load harness-eval skill before authoring to check overlap.

1.3 Author skill: route-dev-task — DO NOT DUPLICATE (see C-1).
    Existing skill at ~/.hermes/skills/_custom/route-dev-task/SKILL.md
    handles routing to the dev-profile Hermes subprocess. It must NOT be
    recreated. Instead, document in hybrid-agent-control-plane skill how
    it integrates with the existing route-dev-task:
      - route-dev-task routes the overall goal to the dev profile.
      - hybrid-agent-control-plane is called within the dev session to
        actually spawn and gate the external agent worker.
    If the existing route-dev-task needs an extension for agent routing,
    propose the patch to Yoshio first; do not overwrite the file.

1.4 Write stub agent scripts for testing.
    Files under .hermes/test-fixtures/:
      stub-handoff-pass.yaml   — valid handoff, all gates pass
      stub-handoff-fail-forbidden.yaml   — handoff with forbidden path in changed_files
      stub-handoff-fail-schema.yaml      — handoff missing required fields
      stub-handoff-fail-tests.yaml       — handoff with test_results.passed=false
    Used in Phase 1 testing without real agent spawns.

1.5 Write eval harness tests.
    Location: tests/skills/test_hybrid_agent_control_plane.py
              (CONFIRM: actual test path convention — inspect tests/ structure)
    Test cases:
      - Gate: schema_validation passes on valid handoff
      - Gate: schema_validation fails on stub-handoff-fail-schema
      - Gate: forbidden_path_writes blocks forbidden path
      - Gate: unit_tests fail triggers rejection
      - Manifest: run_id is unique per invocation
      - Locks: two tasks with overlapping paths cannot both acquire lock
      - Cost cap: manifest blocks spawn when cap exceeded
    CONFIRM: test runner command.
      Likely: source .venv/bin/activate && scripts/run_tests.sh
      Or: pytest tests/skills/ -x -q

Verification for Phase 1:
  - All stub-based gate tests pass.
  - Skills load without error in Hermes CLI (hermes /hybrid-agent-control-plane).
  - Manifest and contract templates render correctly from stubs.
  - Audit log is written for each stub run.
  - No new core Hermes files modified.

---

### Phase 2 — Integration: Real Agent Spawns (Worktree Mode)

Goal: run real Claude Code and Codex workers against a test task in worktree
isolation. Still no container isolation; document the gap explicitly in each run.

Tasks:

2.1 Verify Codex sandbox status.
    BEFORE spawning Codex: run the Codex CLI with a canary task (echo only, no
    file writes) and confirm sandbox behavior matches documentation.
    Set capability-matrix.yaml codex.sandbox_verified=true only after this check.
    Treat sandbox and approval-prompts as separate features; verify both.

2.2 Select a low-risk integration test task.
    Criteria: docs-only or small bugfix, no security-adjacent paths,
    bounded scope (< 5 files), existing tests cover the area.
    Do not use a feature task for first real spawn.

2.3 Create worktrees under a safe path.
    CONFIRM: worktree naming convention and root.
    Proposed: git worktree add .worktrees/<run-id>-cc <branch-name>
    Ensure .worktrees/ is in .gitignore.

2.4 Spawn Claude Code worker with scoped CLAUDE.md.
    Claude Code reads CLAUDE.md from worktree root.
    Copy (do not symlink) the thin CLAUDE.md adapter into the worktree.
    CONFIRM: whether Claude Code CLI accepts a --workdir flag pointing at the
    worktree, or whether it must be invoked from the worktree cwd.
    Pass task contract as context (file path or inline).

2.5 Collect handoff from agent.
    Agent writes handoff to .hermes/runs/<run-id>/handoffs/<task-id>.yaml
    in the worktree. Hermes reads it from there.
    CONFIRM: whether Codex CLI can be directed to write structured output to
    a file, or whether Hermes must parse stdout.

2.6 Run full gate sequence against real handoff.
    Use subagent-eval-gate skill.
    Log all gate results to audit.jsonl.

2.7 Human gate: Yoshio reviews diff before merge.
    Hermes prints diff summary and waits for explicit /approve or /reject.
    MVP: no automated merge; Yoshio runs git commands manually.
    Phase 3: Hermes can run git merge after human approval signal.

2.8 Post-merge: update manifest to status=completed, release locks.

Verification for Phase 2:
  - A real (small) task was completed by Claude Code or Codex in a worktree.
  - All gates ran and their results are in audit.jsonl.
  - No agent touched prompt artifacts.
  - Cost stayed within cap.
  - Merge was approved by Yoshio, not automated.
  - Worktree cleaned up after merge.

---

### Phase 3 — Hardening (deferred)

Gated on Phase 2 validated.

3.1 Container isolation per agent (Docker or Daytona backend).
    Hermes already supports Docker terminal backend via tools/environments/.
    CONFIRM: whether existing docker backend supports worktree-style git access
    or requires volume mounts.
    Per-agent HOME: set HOME=/tmp/agent-home-<run-id> for each container.

3.2 Codex sandbox canary: run a network-exfil canary test in the container
    to confirm sandbox blocks outbound connections.

3.3 Promote integration_tests gate to blocking in eval-matrix.yaml.

3.4 Promote security_scan gate to blocking.

3.5 Kanban integration (optional).
    The kanban plugin in plugins/kanban/ dispatches workers.
    CONFIRM: whether a new kanban lane type "hybrid-agent" makes sense, or
    whether the existing worker skill pattern is sufficient.
    Do not integrate kanban until Phase 2 is stable.

3.6 Rolling integration: run hybrid agent on 1 real task per week, review
    audit logs, adjust gate thresholds.

3.7 Cost controls: add a per-week cost budget tracked in
    .hermes/config/cost-policy.yaml. Hermes checks this before any spawn.

---

## Integration Points

### Hermes Skills (confirmed needed)

| Skill | Status | Location |
|---|---|---|
| hybrid-agent-control-plane | Draft only (Phase 1 — see C-2) | .hermes/templates/skill-draft-*.md until Yoshio approves profile install |
| subagent-eval-gate | New or extend harness-eval (Phase 1) | TBD — defer profile install |
| route-dev-task | EXISTS — do not duplicate (see C-1) | ~/.hermes/skills/_custom/route-dev-task/SKILL.md |
| subagent-driven-development | Existing — reference | already in skills/ |
| requesting-code-review | Existing — gate step | already in skills/ |
| harness-eval | Existing — inspect before extending | already in skills/ |

### Repo Scaffolding

| File | Action | Notes |
|---|---|---|
| AGENTS.md | Append section | Do not rewrite |
| CLAUDE.md | Create | Thin adapter |
| CODEX.md | Create (PROVISIONAL — see C-4) | Thin adapter stub; mark as unverified |
| .hermes/schemas/handoff-v1.yaml | Create | Schema definition |
| .hermes/config/capability-matrix.yaml | Create | Human-authored, agent-immutable |
| .hermes/config/gate-taxonomy.yaml | Create | Human-authored, agent-immutable |
| .hermes/config/eval-matrix.yaml | Create | Human-authored, agent-immutable |
| .hermes/config/recovery-runbook.md | Create | Human-authored |
| .hermes/templates/*.yaml.j2 | Create | Manifest/contract/lock templates |
| .hermes/test-fixtures/*.yaml | Create | Stub handoffs for testing |
| .worktrees/ | Create dir, add to .gitignore | Worktree root |
| CODEOWNERS | Create or extend | Protect prompt artifacts |

### CLI / Workflow

MVP: skill-based workflow only. No new core CLI commands.

Trigger: Yoshio types:
  /route-dev-task "fix the bug in tools/terminal.py where timeout is ignored"

Or via skill:
  /hybrid-agent-control-plane task_type=bugfix goal="..."

Slash commands are dispatched by Hermes CLI via skill loading (see
agent/skill_commands.py). No new core code needed for Phase 1.

Optional (Phase 3): a /hacp slash command as a thin wrapper that loads
hybrid-agent-control-plane. Only worth adding if the skill invocation UX
is awkward.

---

## Context Health Policy

Agents receive a scoped context: task contract + CLAUDE.md/CODEX.md only.
Hermes does NOT pass full session history or run manifest to agents.
Rationale: limits confused-deputy surface — agent only knows its task, not
the broader orchestration state.

If an agent requests context outside its contract scope, Hermes rejects
the request and logs it to audit.jsonl.

---

## Supply Chain Policy

1. Plan files (.hermes/plans/*.md) must have a human_reviewed_at field
   (date + Yoshio sign-off) before any run references them.
   Hermes refuses to spawn agents from plans missing this field.

2. Prompt artifact changes (AGENTS.md, CLAUDE.md, CODEX.md, .claude/**,
   .codex/**, .hermes/config/**, .hermes/schemas/**) are blocked from
   agent-authored commits via CODEOWNERS (or pre-commit hook).

3. No npx @latest or remote installer scripts. All templates are vendored
   in .hermes/templates/ and version-controlled.

4. Agent skill files themselves (~/.hermes/profiles/dev/skills/**) are
   user-config, not repo files. They must be reviewed before first use and
   after any edit.

---

## Risks and Open Decisions for Yoshio

### Risks

R-1 Codex sandbox is unverified.
    Impact: Codex may have network or filesystem access you don't expect.
    Mitigation: Do not use Codex in Phase 2 until canary test passes.

R-2 Worktrees are not sandboxes.
    Impact: Agent in a worktree can read/write any path on the host accessible
    to the Hermes process. A compromised or hallucinating agent can escape
    the allowed_paths contract via the filesystem.
    Mitigation: Phase 3 containers. For Phase 2, allowed_paths is advisory
    enforcement only (gate-checked post-hoc, not prevented pre-run).
    Document this gap prominently in run manifests.

R-3 Hermes confused deputy.
    Impact: Hermes has high trust. If a malicious plan file or low-trust
    context is handed to Hermes, it can be directed to spawn agents with
    high-trust credentials.
    Mitigation: plan files require human_reviewed_at. Plans from session
    context (not committed files) are never used as run references without
    Yoshio confirmation.

R-4 Prompt artifact injection.
    Impact: Agent modifies AGENTS.md or .claude/commands/ to alter future
    agent behavior.
    Mitigation: CODEOWNERS + forbidden_path_writes gate + prompt_artifact_unchanged
    gate. Both must be in place before Phase 2.

R-5 Cost overrun.
    Impact: Agent loops consume large token budget before cap is enforced.
    Mitigation: cost_cap_usd in task contract + total_cost_usd_cap in manifest.
    Hermes checks cost before each spawn. CONFIRM: whether Hermes AIAgent
    exposes cost tracking per-run (check agent/ internals).

### Open Decisions

D-1 Container vs worktree for Phase 2.
    Recommendation: worktree for Phase 2 with documented gap; containers for
    Phase 3. But if Yoshio has Docker available and Hermes docker backend is
    stable, skip straight to containers.
    CONFIRM: Docker availability and Hermes docker backend status.

D-2 Handoff mechanism: file vs stdout.
    Codex may not write structured files natively.
    Decision needed: does Hermes parse Codex stdout and extract handoff, or
    does the agent skill template write the file?
    Recommendation: agent skill template writes the file; cleaner separation.

D-3 human_reviewed_at enforcement mechanism.
    Options: (a) Hermes skill checks the field at spawn time (soft enforcement),
    (b) pre-commit hook blocks commits without it (hard enforcement).
    Recommendation: (b) for prompt artifacts, (a) for plan files (plan files
    are not committed in all workflows).

D-4 Gate parallelism.
    Static gates can run in parallel; dynamic gates (tests) may be slow in
    serial. Phase 1: serial is fine. Phase 2: consider parallel gate execution
    if test suite is > 2 minutes. CONFIRM: test suite runtime.

D-5 Codex CLI handoff schema — TBD (see C-4).
    Codex CLI behavior is unconfirmed. Do not finalize a Codex-specific
    adapter until Phase 2 canary passes. The handoff schema is designed
    to be agent-agnostic; adapter skill produces the compliant output.
    Mark Codex adapter path as provisional in all config files.

D-6 Cost tracking granularity — estimated only for now (see C-5).
    Hermes may not expose per-external-agent cost. Use token-count ×
    model-pricing as the fallback. Mark cost_usd_actual as estimated=true
    in manifests. Inspect agent/budget.py or equivalent in Phase 1 to
    confirm whether exact per-instance cost is available.

---

## Acceptance Criteria

Phase 0:
- [ ] All schema, config, template, and adapter files committed and reviewed.
- [ ] AGENTS.md has hybrid-agent-control-plane section.
- [ ] CODEOWNERS (or pre-commit) blocks agent writes to prompt artifacts.
- [ ] human_reviewed_at field defined and documented.

Phase 1:
- [x] hybrid-agent-control-plane skill draft created at `.hermes/templates/skill-draft-hybrid-agent-control-plane.md`.
- [x] subagent-eval-gate coverage: `harness-eval` skill is not installed in this profile; gate logic lives in `scripts/check_hybrid_control_plane.py` and `tests/skills/test_hybrid_agent_control_plane.py`. No separate skill-draft needed (documented in skill draft).
- [x] All stub fixture tests pass (`scripts/check_hybrid_control_plane.py` + pytest).
- [x] Locked decisions LD-1 through LD-6 encoded in plan and skill draft.
- [x] `human_reviewed_at: 2026-05-22T23:27:28Z` set and machine-checkable.
- [ ] Skills load without error in Hermes CLI (deferred: not installed to user profile in Phase 1).
- [ ] Manifest and contract render correctly from templates with a real run (Phase 2).
- [ ] Audit log is written and append-only for each real run (Phase 2).

Phase 2:
- [ ] At least one real task completed by Claude Code in worktree mode.
- [ ] All required gates ran; results in audit.jsonl.
- [ ] No prompt artifact modified by agent.
- [ ] Cost stayed within cap.
- [ ] Yoshio approved merge via explicit signal (not automated).
- [ ] Worktree cleaned up post-merge.

---

## Verification Checklist (pre-Phase-2 gate)

Before any real agent spawn:

- [ ] Codex sandbox_verified=true in capability-matrix.yaml (or Codex excluded)
- [ ] forbidden_path_writes gate tested against stub
- [ ] prompt_artifact_unchanged gate tested against stub
- [ ] CODEOWNERS protecting .hermes/config/ and .hermes/schemas/
- [ ] .worktrees/ in .gitignore
- [ ] cost_cap enforced in at least one stub test
- [ ] Recovery runbook reviewed and accessible
- [ ] human_reviewed_at set on this plan file by Yoshio

---

## Assumptions Made in This Plan

1. Hermes AIAgent supports delegate_task to route work internally. Real
   external agent spawning (Claude Code CLI, Codex CLI) uses terminal()
   calling the CLI, NOT delegate_task auto-discovery. See C-3.
   CONFIRM: actual CLI invocation pattern before Phase 2.

2. Claude Code CLI reads CLAUDE.md from the working directory root.
   CONFIRM: may be .claude/settings.json or --config flag instead.

3. Codex CLI behavior is UNCONFIRMED. Do not assume CODEX.md is read;
   do not assume any specific flag or file location. See C-4.
   CONFIRM with current Codex CLI docs before Phase 2.

4. Test runner is scripts/run_tests.sh with .venv activation.
   CONFIRM by inspecting tests/ and scripts/ before writing gate commands.

5. Path lock enforcement is advisory in Phase 1/2 (checked post-hoc by gates).
   Pre-emptive blocking requires either (a) a Hermes lock server or (b)
   container isolation. This is a known gap.

6. Cost tracking per external agent is ESTIMATED only. Hermes does not
   guarantee per-external-process cost data. Use token-count × model-pricing
   as the primary accounting method; mark cost fields `estimated: true`.
   See C-5 and D-6.

---

*Plan saved: 2026-05-22. Implementation should not begin until Yoshio sets
human_reviewed_at and resolves open decisions D-1 through D-6.*

---
# SKILL DRAFT — NOT INSTALLED
# Location: .hermes/templates/skill-draft-hybrid-agent-control-plane.md
# Status: Repo-local draft. Do NOT copy to ~/.hermes/profiles/dev/skills/ without
#         explicit Yoshio approval (see plan C-2).
# Governed by: .hermes/plans/2026-05-22_000000-hybrid-agent-control-plane.md
# Locked decisions encoded: LD-1 through LD-6 (approved 2026-05-22T23:27:28Z)
#
# To install once approved:
#   cp -r .hermes/templates/skill-draft-hybrid-agent-control-plane.md \
#          ~/.hermes/profiles/dev/skills/software-development/hybrid-agent-control-plane/SKILL.md
#
name: hybrid-agent-control-plane
description: >
  Orchestrate bounded Claude Code (and eventually Codex) workers for repo tasks.
  Hermes is the control plane; workers are scoped to a git worktree, a task
  contract, and an explicit gate sequence. No worker executes without a
  human-reviewed plan. No merge proceeds without a human gate.
version: 0.1.0-draft
author: Yoshio (via planning session 2026-05-22)
platforms: [linux, macos]
metadata:
  hermes:
    tags: [orchestration, agents, control-plane, claude-code, worktrees, gates, mvp]
    related_skills:
      - route-dev-task        # existing skill — do NOT duplicate (plan C-1)
      - subagent-driven-development
      - requesting-code-review
      - harness-eval          # gate logic reference (not installed in this profile)
    phase: 1-draft
    human_reviewed_at: 2026-05-22T23:27:28Z
---

# Hybrid Agent Control Plane (DRAFT)

> DRAFT — Not installed to user profile. All artifact paths are repo-local.
> Plan ref: `.hermes/plans/2026-05-22_000000-hybrid-agent-control-plane.md`
> Locked decisions: LD-1 through LD-6 (2026-05-22T23:27:28Z)

---

## Overview and Responsibilities

This skill is the Hermes orchestrator for bounded external agent workers.
It does NOT autonomously spawn real agents. In Phase 1 (MVP) it documents
the intended workflow and is validated against stub fixtures. Real worker
invocations belong in Phase 2 after canary tests pass.

Responsibilities:
1. Accept a goal string and task_type from the user.
2. Verify the plan file has a non-empty `human_reviewed_at` field.
3. Generate a run manifest from `.hermes/templates/run-manifest.yaml.j2`.
4. Generate a task contract from `.hermes/templates/task-contract.yaml.j2`.
5. Acquire path locks (write `.hermes/runs/<run-id>/locks.yaml`).
6. Spawn a worker agent via `terminal()` calling the CLI (NOT delegate_task).
7. Poll for the handoff file at the canonical path.
8. Validate the handoff against `.hermes/schemas/handoff-v1.yaml`.
9. Run gates in serial order (LD-4): static → dynamic → human.
10. Merge or reject based on gate results.
11. Update the manifest and emit an audit log entry.
12. Release path locks.

---

## Hard Constraints (must be checked before any action)

- **No real spawns without human_reviewed_at.** If the plan file does not
  contain `human_reviewed_at: <timestamp>`, refuse to spawn any worker.
  Conservative/docs-only operations (generating templates, reviewing config)
  may proceed without it.
- **No delegate_task for worker spawn.** Real worker execution uses
  `terminal()` to invoke the CLI (e.g. `claude --print --output-format json
  -p "$(cat contract.yaml)" --workdir .worktrees/<run-id>-cc`). The exact
  invocation must be confirmed before Phase 2. See plan C-3.
- **Do not write to ~/.hermes/profiles/ or ~/.hermes/skills/.** All Phase 1
  artifacts are repo-local under `.hermes/`.
- **Do not create a second route-dev-task skill.** The existing skill at
  `~/.hermes/skills/_custom/route-dev-task/SKILL.md` handles routing.
  See integration section below.
- **No --dangerously-skip-permissions on real host filesystems.**
- **Worktrees are merge isolation, not security isolation.** Document this
  gap in every run manifest (`worktrees_are_sandbox: false`). See LD-1.

---

## Integration with Existing route-dev-task Skill

The existing `route-dev-task` skill routes the overall goal to the dev-profile
Hermes subprocess. This skill (`hybrid-agent-control-plane`) is invoked
_inside_ that dev session to spawn and gate the external agent worker.

Flow:
```
User → /route-dev-task "fix bug in tools/terminal.py"
          ↓
    Hermes dev profile session
          ↓
    /hybrid-agent-control-plane task_type=bugfix goal="..."
          ↓
    [this skill] → generates manifest/contract → spawns Claude Code worker
          ↓
    [gate sequence] → human gate → merge or reject
```

If `route-dev-task` needs extension for agent-type routing, propose the
patch to Yoshio. Do not overwrite the existing skill file.

---

## Workflow (Serial Gates — LD-4)

### Step 0: Pre-flight checks

```python
# Pseudo-code — real implementation uses terminal() and file tools

# 1. Check plan has human_reviewed_at
plan = read_file(".hermes/plans/<plan-file>.md")
assert "human_reviewed_at:" in plan and plan has non-empty timestamp
# Enforcement: scripts/check_hybrid_control_plane.py validates this

# 2. Verify capability matrix
matrix = load_yaml(".hermes/config/capability-matrix.yaml")
assert matrix["agents"]["claude_code"]["dangerously_skip_permissions"] == False
```

### Step 1: Generate run artifacts

```bash
# Generate run manifest
run_id=$(python -c "import uuid; print(uuid.uuid4())")
mkdir -p .hermes/runs/$run_id/contracts
mkdir -p .hermes/runs/$run_id/handoffs

# Render manifest from template (Phase 1: manual substitution; Phase 2: Jinja2)
# Template: .hermes/templates/run-manifest.yaml.j2
# Output:   .hermes/runs/$run_id/manifest.yaml
# IMPORTANT: manifest must include:
#   worktrees_are_sandbox: false   (LD-1)
#   container_isolation: false     (LD-1)
#   cost_estimated: true           (LD-6)
#   human_reviewed_at: ~           (filled from plan)

# Generate task contract
task_id=$(python -c "import uuid; print(uuid.uuid4())")
# Template: .hermes/templates/task-contract.yaml.j2
# Output:   .hermes/runs/$run_id/contracts/$task_id.yaml
# Includes: cost_cap_usd, cost_estimated: true, spawn_mechanism: terminal_cli
```

### Step 2: Acquire path locks

```bash
# Write locks.yaml BEFORE spawning worker
# Template: .hermes/templates/locks.yaml.j2
# Output:   .hermes/runs/$run_id/locks.yaml
# Check for conflicts against other active runs (advisory in Phase 1)
```

### Step 3: Spawn worker (Phase 2+ only; Phase 1 uses stubs)

```bash
# Phase 1: stub — no real spawn
# Phase 2: real spawn via terminal()
#
# Claude Code example (CONFIRM exact flags before Phase 2):
git worktree add .worktrees/$run_id-cc -b agent/$run_id
cd .worktrees/$run_id-cc
# Copy (not symlink) thin CLAUDE.md adapter into worktree
cp CLAUDE.md .worktrees/$run_id-cc/CLAUDE.md
# Invoke worker — must write HANDOFF_PATH: <path> to stdout (LD-2)
claude --print --output-format json \
  -p "$(cat .hermes/runs/$run_id/contracts/$task_id.yaml)" \
  2>&1 | tee .hermes/runs/$run_id/agent-stdout.txt

# Extract handoff path from stdout sentinel (LD-2)
HANDOFF_PATH=$(grep '^HANDOFF_PATH:' .hermes/runs/$run_id/agent-stdout.txt \
               | head -1 | cut -d' ' -f2)
# Canonical path convention:
# .hermes/runs/$run_id/handoffs/$task_id.yaml
```

### Stdout Sentinel Convention (LD-2)

Worker agents MUST write the following line to stdout when done:
```
HANDOFF_PATH: .hermes/runs/<run-id>/handoffs/<task-id>.yaml
```

The YAML file at that path is the source of truth. Stdout content outside
this sentinel line is logged but not parsed as structured handoff data.
If the handoff file is absent or unreadable, the handoff is rejected and
the run transitions to `status: failed`.

### Step 4: Gate sequence (serial — LD-4)

Run gates in this exact order. Stop at first blocking failure.

```
[STATIC — fast, no side effects]
1. schema_validation       — handoff has all required fields (handoff-v1.yaml)
2. forbidden_path_writes   — no forbidden paths in changed_files
3. prompt_artifact_unchanged — no AGENTS.md / CLAUDE.md / .hermes/config/** touched
4. diff_size_limit         — diff KB <= contract limit

[DYNAMIC — runs commands]
5. lint                    — project linter exits 0 (CONFIRM command: ruff? mypy?)
6. unit_tests              — scripts/run_tests.sh exits 0

[RESOURCE]
7. cost_cap                — total_cost_usd_actual <= manifest cap

[HUMAN — always last, always blocking in MVP]
8. human_review            — Yoshio reviews diff, types /approve or /reject
```

Each gate result is appended to `.hermes/runs/<run-id>/audit.jsonl`:
```json
{"timestamp": "<iso8601>", "gate": "schema_validation", "result": "pass", "evidence": {}}
```

### Step 5: Merge or reject

```bash
# Only after ALL gates pass (including human_review):
git -C .worktrees/$run_id-cc diff HEAD > review.patch
# Yoshio runs merge manually in Phase 1/2:
#   git apply review.patch   or   git merge agent/$run_id

# Update manifest
# status: completed, closed_at: <timestamp>

# Release locks
# released_at: <timestamp> in locks.yaml

# Cleanup worktree (after Yoshio confirms)
git worktree remove .worktrees/$run_id-cc
git branch -d agent/$run_id
```

---

## Worktree Rules (LD-1)

1. Worktrees are named `<run-id>-cc` (Claude Code) or `<run-id>-cx` (Codex).
2. Root: `.worktrees/` (in `.gitignore`; never committed).
3. Worktrees are merge isolation, NOT security isolation. Document this gap
   in every run manifest with `worktrees_are_sandbox: false`.
4. Container/per-agent HOME isolation is deferred to Phase 3.
5. Never reuse a run_id. Abandoned worktrees: `git worktree remove --force`.
6. Do not force-merge a worktree that has diverged. Log and escalate (R7).

---

## File-Based Handoff Rules (LD-2)

1. Canonical path: `.hermes/runs/<run-id>/handoffs/<task-id>.yaml`
2. Worker stdout sentinel: `HANDOFF_PATH: <path>` (first occurrence used)
3. The YAML file is authoritative; stdout is advisory/logging only.
4. Schema: `.hermes/schemas/handoff-v1.yaml`
5. Handoffs missing required fields are rejected before any gate runs.
6. Handoffs with `test_results.passed: false` fail the `unit_tests` gate.
7. Handoffs with forbidden paths in `changed_files` fail `forbidden_path_writes`.

---

## Human Gate Rules (LD-3)

1. `human_reviewed_at` must be set in the plan before Phase 2+ runs.
2. Enforcement: `scripts/check_hybrid_control_plane.py` checks this field.
3. In Phase 1 (stub testing), the check is validated against the plan.
4. The human_review gate is always the LAST gate in the sequence (LD-4).
5. Hermes presents a diff summary and waits for `/approve` or `/reject`.
6. No automated merge in Phase 1/2. Yoshio runs git commands manually.
7. A rejected handoff transitions the run to `status: failed`; logs to audit.

---

## Cost Fields (LD-6)

All manifests and contracts carry:
```yaml
cost_estimated: true           # always true until exact source confirmed
total_cost_usd_cap: 5.00       # hard cap; spawns blocked beyond this
total_cost_usd_actual: ~       # null until filled; ESTIMATED
```

Task entries in manifests:
```yaml
cost_usd_actual: ~             # ESTIMATED when filled; see plan C-5
cost_estimated: true
```

Handoff `cost_estimated` object (optional, from agent self-report):
```yaml
cost_estimated:
  tokens_input: 12000
  tokens_output: 3500
  model: claude-sonnet-4-5
  estimated_usd: 0.18
  method: token_count_estimate  # "exact" only if provider confirms
```

---

## Gate Evaluation: subagent-eval-gate vs harness-eval

The `harness-eval` skill is NOT installed in this Hermes profile. Gate logic
for Phase 1 lives entirely in:
- `scripts/check_hybrid_control_plane.py` — deterministic checks, no LLM
- `tests/skills/test_hybrid_agent_control_plane.py` — pytest coverage

A separate `subagent-eval-gate` skill draft is NOT created in Phase 1 because:
- No real worker spawns occur in Phase 1
- The gate logic is fully exercised by the check script and pytest
- Adding a second skill draft without real execution would be premature YAGNI

When Phase 2 gates are implemented (real runs), revisit whether a separate
`subagent-eval-gate` skill is warranted or whether the check script is
sufficient.

---

## No Real Spawns in MVP (Phase 1)

Phase 1 explicitly prohibits:
- Real Claude Code CLI invocations
- Real Codex CLI invocations
- Real git worktree creation for agent use
- Any `terminal()` calls that launch external agent processes
- Any `delegate_task()` calls intended to run Claude Code or Codex

All Phase 1 testing uses stub fixtures under `.hermes/test-fixtures/`.
Real invocations are introduced in Phase 2 after:
- Codex canary test passes (task 2.1)
- All Phase 1 gate tests pass
- human_reviewed_at is set on the plan

---

## Verification Commands

```bash
# Syntax check
python -m py_compile scripts/check_hybrid_control_plane.py

# Full deterministic check (no real spawns)
python scripts/check_hybrid_control_plane.py

# Pytest coverage for gate logic
python -m pytest tests/skills/test_hybrid_agent_control_plane.py -q

# Check for whitespace errors
git diff --check

# Confirm unrelated files not modified
git status --short
# Expected dirty: only .hermes/ and new Phase 1 files
# Must NOT be modified: agent/anthropic_adapter.py, hermes_cli/auth.py, AGENTS.md
```

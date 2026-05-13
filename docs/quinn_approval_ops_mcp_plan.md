# Approval-Gated Ops MCP Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Design a tightly gated operations MCP for safe, auditable Hermes maintenance actions such as gateway restart, MCP reload, config backup, doctor runs, and applying pre-reviewed patches.

**Architecture:** Keep this MCP separate from read-only awareness MCPs. Version 1 should implement a two-step prepare/execute protocol: tools generate an action plan and approval challenge; execution only proceeds when Frank supplies the exact approval phrase for the exact plan. If approval cannot be verified, the MCP refuses to act.

**Tech Stack:** Python 3.11, MCP SDK, subprocess argv execution with `shell=False`, JSON action manifests, pytest with monkeypatched command runner and temp files.

---

## Non-Negotiable Rules

- No action runs from a single casual tool call.
- Every mutation requires a prior `prepare_*` call and a matching approval phrase.
- No broad shell execution tool.
- No arbitrary command strings.
- No edits to private auth or environment files.
- No destructive git actions in v1.
- No service stop without restart intent and rollback/verification plan.
- Every execution returns command argv metadata, exit code, verification result, and backup path where relevant.
- Every action has a dry-run/plan mode.

## Action Model

Each operation uses an action manifest with:

- schema version
- action ID
- action type
- created/expires timestamps
- `requires_approval=true`
- exact approval phrase
- argv command list
- verification argv list
- rollback notes if any

Prepared manifests are stored under:

- `$HERMES_HOME/mcp/quinn_ops_actions/pending/`

Completed manifests are moved to:

- `$HERMES_HOME/mcp/quinn_ops_actions/completed/`

Use mode `0600` where possible.

## Tool Set v1

Read/prepare tools:

1. `healthcheck()` — server readiness and action directory metadata.
2. `list_allowed_actions()` — static action definitions and risk levels.
3. `prepare_gateway_restart(reason: str)` — builds action manifest, no execution.
4. `prepare_mcp_reload(reason: str)` — builds reload/restart manifest, no execution.
5. `prepare_config_backup(reason: str)` — builds backup manifest, no execution.
6. `prepare_doctor_run(reason: str)` — builds diagnostic manifest, no execution.
7. `prepare_safe_patch(path_alias: str, patch_text: str, reason: str)` — only for allowlisted paths, no execution.
8. `get_pending_action(action_id: str)` — returns manifest metadata.
9. `cancel_pending_action(action_id: str)` — marks pending action cancelled; this is a state write but not a system mutation.

Execute tool:

10. `execute_approved_action(action_id: str, approval_phrase: str)` — validates manifest, expiration, exact phrase, and allowed command argv before execution.

## Allowed Actions v1

### Gateway Restart

Commands:

```bash
hermes gateway restart
hermes gateway status
hermes mcp test quinn_ops
```

Risk: medium. Interrupts current gateway sessions briefly.

### MCP Reload/Restart

Preferred sequence:

```bash
hermes mcp list
hermes gateway restart
hermes mcp test <server>
```

Risk: medium.

### Config Backup

Allowed source:

- `/home/quinn/.hermes/config.yaml`

Allowed destination:

- `/home/quinn/.hermes/backups/config.yaml.<timestamp>.bak`

Risk: low. Must not print file contents.

### Doctor Run

Commands:

```bash
hermes doctor
```

Risk: low read/diagnostic. Must sanitize output.

### Safe Patch

Allowed targets v1:

- source-of-truth Markdown docs
- MCP server files under `/home/quinn/.hermes/hermes-agent/scripts/mcp/`
- matching tests under `/home/quinn/.hermes/hermes-agent/tests/`

Excluded targets:

- private auth/environment files
- session stores
- logs
- arbitrary platform adapters unless explicitly added later

Risk: medium/high depending target. Must backup target first and run verification command after patch.

## Task 1: Add Failing Manifest and Approval Tests

**Objective:** Prove no mutation can happen without explicit two-step approval.

**Files:**
- Create: `tests/test_quinn_approval_ops_mcp.py`

**Tests:**
- `prepare_gateway_restart()` creates manifest and does not execute command runner.
- `execute_approved_action()` rejects missing/incorrect approval phrase.
- Expired action is rejected.
- Unknown action ID is rejected.
- Manifest command argv must match allowlisted action spec.

**Verification:**
```bash
venv/bin/python -m pytest tests/test_quinn_approval_ops_mcp.py -q
```

Expected: FAIL until server exists.

## Task 2: Scaffold Server and Action Store

**Objective:** Create importable server with safe action persistence.

**Files:**
- Create: `scripts/mcp/quinn_approval_ops_server.py`
- Modify: `tests/test_quinn_approval_ops_mcp.py`

**Implementation requirements:**
- `response()`, `sanitize()`, `now_utc()`, `action_dir()` helpers.
- `create_action_manifest(action_type, reason, commands, verification, rollback)`.
- Atomic manifest writes with mode `0600`.
- Importable without MCP SDK.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_approval_ops_server.py tests/test_quinn_approval_ops_mcp.py
venv/bin/python -m pytest tests/test_quinn_approval_ops_mcp.py -q
```

## Task 3: Prepare Gateway Restart and Config Backup

**Objective:** Implement low-complexity prepare flows.

**Files:**
- Modify: `scripts/mcp/quinn_approval_ops_server.py`
- Modify: `tests/test_quinn_approval_ops_mcp.py`

**Implementation requirements:**
- `prepare_gateway_restart(reason)` creates restart manifest with verification steps.
- `prepare_config_backup(reason)` creates backup manifest with exact source/destination.
- No command runner call during prepare.
- Approval phrase includes action ID and action type.

## Task 4: Execute Approved Action

**Objective:** Safely run only validated pending manifests.

**Files:**
- Modify: `scripts/mcp/quinn_approval_ops_server.py`
- Modify: `tests/test_quinn_approval_ops_mcp.py`

**Implementation requirements:**
- Validate action exists, is pending, is unexpired, has matching phrase, and matches static allowlist.
- Run commands with `shell=False` and timeouts.
- Run verification commands after mutation commands.
- Move manifest to completed with result summary.
- Never print raw config contents.

## Task 5: Doctor Run and MCP Reload Prepare Flows

**Objective:** Add diagnostic and MCP refresh operations.

**Files:**
- Modify: `scripts/mcp/quinn_approval_ops_server.py`
- Modify: `tests/test_quinn_approval_ops_mcp.py`

**Implementation requirements:**
- `prepare_doctor_run(reason)` uses read/diagnostic command and sanitized output.
- `prepare_mcp_reload(reason)` uses list/restart/test sequence.
- Optional server name input must match known safe pattern.

## Task 6: Safe Patch Prepare Flow

**Objective:** Allow pre-reviewed patch application only to allowlisted paths.

**Files:**
- Modify: `scripts/mcp/quinn_approval_ops_server.py`
- Modify: `tests/test_quinn_approval_ops_mcp.py`

**Implementation requirements:**
- Accept structured patch text only.
- Resolve target paths and reject excluded paths.
- Backup target files before patch during execution.
- Use Python patch/apply helper or `git apply --check` then `git apply` with argv only.
- Verification command is required per target type.

## Task 7: Register MCP Tools and Docs

**Objective:** Make server usable and documented without live enablement.

**Files:**
- Modify: `scripts/mcp/quinn_approval_ops_server.py`
- Create: `docs/quinn_approval_ops_mcp.md`

**Implementation requirements:**
- Add `TOOL_FUNCTIONS` and MCP stdio startup.
- Document action model, approval phrases, allowed actions, excluded paths, live promotion steps.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_approval_ops_server.py tests/test_quinn_approval_ops_mcp.py
venv/bin/python -m pytest tests/test_quinn_approval_ops_mcp.py -q
```

## Live Promotion Gate

This MCP is operationally sensitive. Before live use:

1. Frank approval.
2. Dedicated code review.
3. Repo tests pass.
4. Confirm platform approval flow can carry exact approval phrase.
5. Backup existing live server, if any.
6. Copy server to live MCP path.
7. Add MCP config only if approved.
8. Restart gateway.
9. Verify `hermes mcp test quinn_approval_ops`.
10. Dry-run prepare/cancel flow before any execute flow.

## Acceptance Criteria

- No mutation can happen without prepare plus exact approval phrase.
- No arbitrary shell command execution exists.
- Every command is argv-list allowlisted.
- Every state-changing operation records a manifest and result.
- Config backups never print config contents.
- Safe patch flow rejects excluded paths and backs up targets.
- Gateway restart and MCP reload include post-action verification.

## Open Questions Requiring Frank

1. Should the approval phrase be manually typed by Frank, or can Hermes gateway approval metadata be trusted directly?
2. Should safe patch be included in v1, or deferred until after restart/backup/doctor actions prove stable?
3. Should completed action manifests be retained forever or pruned after a retention window?
4. Should this MCP be available only in protected/private contexts?

# Setup Gate Ladder Audit (M2)

> Planning artifact for milestone M2. Read-only by default. No profile/config/credential/gateway/cron mutation without explicit operator approval.

**Parent roadmap:** `/tmp/hermes-workflows/hermes-roadmap-build-plan/20260609-144338/roadmap-and-build-plan.md`  
**Wiki concept:** Hermes setup gate ladder (Obsidian `concepts/hermes-setup-gate-ladder.md`)  
**Prerequisite:** M1 profile-list alias scan fix (`khall/profile-list-fast-alias-scan`, commit `3c434bc9a`)

## Goal

Produce a **repeatable read-only audit** that runs before any setup mutation. Output is a compact JSON + markdown receipt: evidence, blockers, and approval-gated next steps. Distinguish **desired config** (YAML flags) from **runtime truth** (installed checkout, live PIDs, executing symbols).

## Non-goals (M2)

- No edits to `config.yaml`, `.env`, profiles, gateway unit, or cron jobs
- No provider spend-bearing smoke unless operator approves a live ping slice
- No promotion to `hermes doctor setup --json` until one dogfood workflow receipt proves value

## Relationship to `hermes doctor`

`hermes doctor` today is a broad interactive diagnostic (deps, keys shape, models, toolsets). The setup gate ladder is **sequenced and receipt-oriented**:

| Ladder gate | Doctor overlap | Ladder-specific |
|-------------|----------------|-----------------|
| G0 Version/source | partial | git anchor, dirty state, active profile, CLI vs checkout |
| G1 Provider | yes | no-network classifier/router smoke first |
| G2 Tools / Tool Gateway | partial | Nous Tool Gateway vs messaging gateway |
| G3 MCP | partial | server list + auth state without secret values |
| G4 Memory | partial | provider id, Honcho mode — no private content |
| G5 Cron | list only | risk class per job; no create/update |
| G6 Gateway | partial | single-owner rule; no restart |
| G7 Receipt | n/a | synthesis + blockers |

Promotion path: after workflow dogfood, add `hermes doctor setup --json` or a subcommand that emits the schema below.

## Ladder gates (read-only checks)

### G0 — Version and source anchor

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| CLI version | `hermes --version` | Parses; recorded |
| Active profile | `HERMES_HOME` / `hermes profile show` (read-only) | Path exists |
| Profile inventory | `hermes profile list` | Completes within budget (e.g. 5s) after M1 |
| Source checkout (when auditing dev) | `git -C <repo> status --short --branch`, `rev-parse HEAD` | Recorded; stop if unexpected dirty unrelated work |
| Smart routing symbols (if configured) | import/router probe in **authoritative checkout** | Config flag without runtime symbols = blocker |

### G1 — Provider / routing (no-network first)

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| Default provider + model | read `config.yaml` `model:` keys only | Recorded; no secret values |
| Credential **shape** | env var **names** present/absent | e.g. `OPENROUTER_API_KEY=set` not value |
| Routing matrix row | compare config to documented lanes | cheap / routine / hard lanes documented |
| Optional live smoke | single cheap completion | **Approval-gated**; record latency + model id |

### G2 — Tool Gateway and tools

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| Tool inventory | `hermes tools` (truncated in receipt) | Managed vs BYO noted |
| Portal | `hermes portal info` / `portal tools` if safe | Subscription vs BYO keys clear |
| Distinction | docs + config | Messaging gateway ≠ Tool Gateway |

### G3 — MCP

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| Configured servers | `config.yaml` `mcp:` / `hermes mcp` list | Names + transport; no tokens |
| Dynamic toolsets | `mcp-<server>` pattern | Listed |
| Reload policy | `security` / approvals | Manual reload confirm noted |

### G4 — Memory

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| Active provider | config + `hermes memory` status if exists | honcho/mem0/builtin |
| Scope | profile vs default | Recorded |
| Content | **never** dump memories in receipt | summaries only |

### G5 — Cron

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| Job inventory | `hermes cron list` | id, schedule, profile, deliver, script/no_agent |
| Risk class | prompt keywords / toolsets | mutation-capable jobs flagged |
| Side effects | | create/update/remove = approval-gated |

### G6 — Gateway

| Check | Command / source | Pass criteria |
|-------|------------------|---------------|
| Owner | single profile + PID + unit | Mismatch = blocker |
| Status | `hermes gateway status` | Running/stopped recorded |
| Repair | | **Approval-gated**; include rollback in plan |

### G7 — Receipt synthesis

Aggregate gate results into JSON + markdown. List blockers, `needs_operator` items, and safe next actions.

## Secret redaction rules

1. Never include `.env` contents, API keys, OAuth tokens, or `Authorization` headers.
2. Report credentials as: `VAR_NAME=set|unset` or fingerprint `sha256:abcd…` (first 8 hex) if required for drift detection.
3. Redact chat IDs / phone numbers in cron deliver targets to last 4 digits where shown.
4. `security.redact_secrets` and `tirith_enabled` recorded as booleans from config only.

## Receipt schema (`receipt.json`)

```json
{
  "schema_version": 1,
  "workflow": "setup-gate-ladder",
  "run_id": "YYYYMMDD-HHMMSS",
  "started_at_utc": "ISO-8601",
  "hermes_home": "/home/khall/.hermes/profiles/auto-coder",
  "permission_boundary": "read-only",
  "gates": {
    "G0_version_source": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] },
    "G1_provider_routing": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] },
    "G2_tools": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] },
    "G3_mcp": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] },
    "G4_memory": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] },
    "G5_cron": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] },
    "G6_gateway": { "status": "pass|warn|fail|skipped", "evidence": {}, "blockers": [] }
  },
  "overall": "pass|needs_operator|fail",
  "approval_gates": ["push", "gateway_restart", "cron_create", "profile_edit", "live_provider_smoke"],
  "next_actions": []
}
```

## Markdown companion (`synthesis.md`)

Human-readable summary: one section per gate, **Verified** vs **Config-only** labels, blockers, and explicit “do not run without approval” lines.

## Implementation sequence (recommended)

1. **Workflow-only (M2a):** shell/Python script under `/tmp/hermes-workflows/setup-gate-ladder/<run-id>/` or profile-local `scripts/setup_gate_ladder_audit.py` — read-only subprocesses, writes receipt next to run dir.
2. **Dogfood (M2b):** run once on `auto-coder` profile; fix probe timeouts using M1-fast `profile list`.
3. **Promote (M2c, approval):** integrate into `hermes_cli/doctor.py` as `hermes doctor setup --json` after schema stabilizes.

## Verification gates before calling M2 done

- [ ] Spec reviewed by operator
- [ ] One full read-only receipt generated from live environment
- [ ] Receipt contains no secret material (manual spot-check)
- [ ] Blockers correctly separate config-without-runtime vs runtime failures
- [ ] No mutation commands in audit script v1

## Stop rules

- Any gate command blocked by operator approval layer → record `status: skipped`, `blocker: approval_denied`, do not retry alternate phrasing in unattended runs.
- Do not proceed to M3 routing matrix **implementation** in same session unless operator expands scope.
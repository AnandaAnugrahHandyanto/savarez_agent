# Work Queue

Use this file for Moongate, MoonSuite, and other work-context execution.

Lifecycle: `intake -> clarify -> assign -> execute -> audit -> report -> complete/blocked`

## Intake

- none

## Clarify

- none

## Plan

- Evaluate OneCLI Agent Vault as the credential/proxy layer for Hermes rebuild. Owner: Wrench. Status: Pending
  - Goal: Determine fit, risks, and integration pattern for Agent Vault (https://github.com/onecli/onecli). Produce a short recommendation (yes/no/conditional) with an integration design that enforces trust boundaries (per-agent-group identities, rate-limiting, approval hooks) and a migration plan.
  - Deliverables: evaluation_report/onecli_evaluation.md, design/onecli_integration.md, risk_matrix/onecli_risks.md
  - Success criteria: clear mapping to TRUST.md buckets, concrete enforcement points (agent-group identities, rate-limits), and a safe rollback plan.
  - ETA: 3 business days after Forge signals integration pattern validated.

## Assign

- none

## Execute

- Rebuild the Rocky brain into a canonical Hermes-first operating system. Status: Assigned

One-page plan (created by Rocky) — scope, tasks, owners, success criteria, ETAs

Goal: Rebuild Rocky's runtime boot and operating surface so the agent boots reliably from the Hermes-first boot path (SOUL.md -> PRINCIPAL.md -> OPERATING_RULES.md -> TRUST.md -> ROUTING.md -> INTEGRATIONS.md -> MEMORY.md -> runtime/tasks-work.md -> runtime/tasks-personal.md -> latest memory/episodic). Deliver a reproducible repo state, CI checks, and documentation so any subagent or human can re-run the boot and verify behavior.

Tasks (5–7 actionable items):

1) Discovery & Safety Checklist (owner: Rocky) — ETA: 4 hours
   - Verify current repo layout, branch protection, CI, and sensitive files.
   - List external integrations and mark those requiring approvals per TRUST.md.
   - Success: checklist file created at .hermes/boot-checklist.md and a short risk matrix.

2) Define Boot Implementation & Tests (owner: Rocky) — ETA: 8 hours
   - Specify steps the boot process must run (file read order, verification, fail modes).
   - Define automated tests: unit tests for file-loading, integration test for boot sequence, gating rules for edits to SOUL/PRINCIPAL/TRUST files.
   - Success: boot_spec.md + tests scaffold in tests/boot_test.py.

3) Implement Boot Orchestrator (owner: Forge subagent) — ETA: 2–3 days
   - Implement a small orchestrator (Python script / CLI) that loads the boot files in order, validates them, and reports status.
   - Add idempotent commands: hermes boot --check, hermes boot --apply (dry-run first), and hermes boot --snapshot.
   - Success: orchestrator in tools/boot_orchestrator.py, runnable locally, returns structured JSON status.

4) CI & Automated Checks (owner: Forge subagent) — ETA: 1 day
   - Add CI job that runs tests, runs hermes boot --check, and blocks merges to main if failures.
   - Success: .github/workflows/boot.yml added, green on CI for the feature branch.

5) Documentation & Playbooks (owner: Rocky + Forge) — ETA: 8 hours
   - Update AGENTS.md and a new BOOT.md with commands, failure modes, and recovery steps.
   - Success: BOOT.md and updated AGENTS.md committed.

6) Audit, Report, and Promote (owner: Rocky) — ETA: 4 hours
   - Run the orchestrator, collect evidence, produce a report following the Reporting Contract.
   - If stable, promote any durable facts to MEMORY.md or memory/projects/ per policy.
   - Success: audit report in reports/boot_audit.md and PR with promoted docs if approved.

Approvals required (per TRUST.md):
- Any external publish, live deployments, or account/credential changes require explicit approval.
- CI changes are allowed but must leave receipts and be audited.

Notes:
- Default owner for coordination = Rocky. Implementation owner = Forge subagent as requested.
- Subagent must return OUTPUT_SCHEMA as required by OPERATING_RULES.md and commit work to a feature branch with clear PR description.

## Audit

- none

## Report

- none

## Blocked

- none

## Complete

- none

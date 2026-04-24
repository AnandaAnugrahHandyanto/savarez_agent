# Hermes role-team runtime overhaul — implementation plan

> For Hermes: planning only. Do not implement in this turn.

## Current progress snapshot

This plan no longer describes a blank-slate runtime. The role-team runtime implementation is staged on branch `role-team-runtime-overhaul` after recovering from an accidental mixed dashboard/branding commit. The core runtime, `invoke_role`, ACP/API-server session propagation, role-runtime dashboard projections, Org Chart page, restored org-chart data files, and Lead-managed findings/remediation/completion-gate helpers are staged and have passed the focused readiness checks. The latest slices add SessionDB-backed persistent role-session create/resume helpers, `invoke_role` execution wiring for persistent role runs, close/retire semantics for persistent role sessions, automatic structured findings ingestion from role outputs, dashboard/backend projection of role-runtime lineage, waived required roles, execution-mode mismatches, and missing required roles, plus a deterministic live transport exercise covering direct `invoke_role` resume, ACP same-ID resume, and API-server parent-session forwarding; the remaining work is final independent review/packaging.

Last reviewed against the live repo state: `2026-04-24T13:27:12+01:00`

Conceptual update added at `2026-04-23T19:31:14Z`: persistent role instances must become real SessionDB-backed role sessions that execute/resume through the normal agent loop. The current implementation records persistent-role artifacts and session IDs, but `invoke_role` must still be upgraded from an artifact/metadata materializer into a transport-neutral role-session orchestrator.

Conceptual update added at `2026-04-24T08:17:54+01:00`: persistent role instances must carry explicit skill policy, not only role charters and runtime policy. Add `skills.required`, `skills.recommended`, and `skills.triggered` to the org-chart registry and propagate those declarations into generated org-chart data, role packets/prompts, and role utilization reports. Treat NoblePro/Kinni historical Codex skills as first-class role-skill inputs when work runs inside that monorepo.

### Verified implementation status
- Staged for commit: canonical role-runtime schemas, `invoke_role`, role-runtime session/analytics API projections, Org Chart page and route, Sessions/Analytics truth surfaces, ACP/API-server parent-session propagation, bundle validation, and core Lead-managed findings/remediation/completion-gate helpers.
- Restored/force-added during this rebaseline: `web/src/data/hermesOrgChart.registry.yaml` and generated `web/src/data/hermesOrgChart.generated.ts`, which are ignored by the repo-wide `data/` ignore rule unless explicitly force-added.
- Previously verified before reset: final pytest bundle reached `398 passed, 2 warnings`, `cd web && yarn build` passed, static security grep was clean, and independent review passed after adding required data files and gating `/api/dashboard/org-chart`. Treat this as historical evidence until the current staged tree is re-verified after this rebaseline.
- Latest implemented slices: `agent.role_runtime.get_or_create_role_session()` now creates/resumes stable SessionDB-backed role sessions keyed by `(plan_id, canonical_role)`, persists queryable `role_metadata`, and `invoke_role` can run a persistent role through a role runner / `AIAgent` path and write actual role responses to output artifacts. `retire_role_session()` now marks persistent role sessions inactive via SessionDB `ended_at` / `end_reason` plus role metadata status while preserving history, and later `get_or_create_role_session()` calls reopen the same role identity. Structured JSON findings emitted in role outputs are now ingested into the Lead-managed findings ledger as pending Lead review without creating Developer remediation packets. Session detail role-runtime projections now expose lineage, waived required roles, execution-mode mismatches, and missing required roles from the latest bundle artifacts. A deterministic live transport exercise verified direct persistent `invoke_role` resume, ACP same-ID role-session resume, and API-server `parent_session_id` forwarding. The skill-policy declaration slice now adds `skills.required`, `skills.recommended`, and `skills.triggered` mappings for all 12 canonical roles in the org-chart registry, regenerates the TypeScript org-chart data/types, and includes the role skill policy in `role_system_prompt()` so persistent role packets/prompts can inherit the historical Kinni/Codex procedures. The latest skill-loading hardening now resolves required skills from installed Hermes skills or workspace Kinni/Codex skill docs, appends loaded required skill content to role packets, and reports verified/partial compliance plus loaded/missing required-skill evidence in execution-plan records, utilization-report records, and tool results. Independent review findings were fixed by constraining workspace skill roots to the requested workspace, rejecting symlinked skill roots that escape the workspace, enforcing an aggregate loaded-skill byte cap, always appending Hermes-loaded required skill content even when a custom packet already has a matching heading, and adding regressions for `.agents/skills`, parent/symlink escape, aggregate-cap, and recommended/triggered-not-loaded behavior.
- Packaging status at `2026-04-24T13:27:12+01:00`: the persistent role-runtime slice is committed as `de01b531 Implement persistent role team runtime`, the role skill-policy/loading slice is committed as `de836dd4 Add role skill policy loading`, and remaining local Hermes customization changes are being packaged separately before pushing the branch to the user's private fork and opening an upstream PR.

### Present in this checkout
- `agent/role_runtime.py`
- `agent/plan_bundle.py`
- `tools/role_invocation_tool.py`
- `web/scripts/generate_org_chart_data.py`
- `tests/agent/test_plan_bundle.py`
- `tests/hermes_cli/test_web_server.py`
- `tests/tools/test_role_invocation_tool.py`
- `tests/run_agent/test_lead_findings_loop.py`
- `run_agent.py`
- `toolsets.py`
- `tools/registry.py`
- `hermes_state.py`
- `gateway/session.py`
- `acp_adapter/session.py`
- `acp_adapter/tools.py`
- `gateway/platforms/api_server.py`
- `hermes_cli/web_server.py`
- `web/src/lib/api.ts`
- `web/src/pages/SessionsPage.tsx`
- `web/src/pages/OrgChartPage.tsx`
- `web/src/pages/AnalyticsPage.tsx`
- `web/src/App.tsx`
- `agent/prompt_builder.py`
- `cli.py`

### Current blocker / not yet finished
- Commit the remaining local Hermes customization changes and this plan snapshot in a separate local-preservation commit.
- Push `role-team-runtime-overhaul` to the user's private fork `stefanpieter/hermes-agent` before any Hermes update.
- Open an upstream GitHub issue and PR against `NousResearch/hermes-agent` so the role-runtime work can persist beyond this local installation.
- Future Hermes-related work requirement: do not run raw `hermes update` or reset/update this checkout before preserving local commits on the private fork and either rebasing/merging them onto upstream or confirming they have landed upstream.

### Current validation note
- Current rebaseline after implementing SessionDB-backed persistent role-session helpers, close/retire semantics, structured findings ingestion, and richer session-detail role-runtime projections is green for the focused readiness checks:
  - initial RED check for `tests/agent/test_role_sessions.py` failed as expected before persistent-session implementation (`ImportError` / missing `session_db` argument)
  - second RED check for close/retire semantics failed as expected before `retire_role_session()` existed (`ImportError`)
  - third RED check for structured findings ingestion failed as expected before `invoke_role` returned `findings_ingested` (`KeyError`)
  - fourth RED check for richer session-detail role-runtime projections failed as expected before `role_runtime.lineage`, `waivers`, `mode_mismatches`, and `missing_required_roles` were projected
  - `source venv/bin/activate && pytest tests/tools/test_role_invocation_tool.py::test_invoke_role_ingests_structured_findings_from_role_output -q` → `1 passed`
  - `source venv/bin/activate && pytest tests/agent/test_role_sessions.py -q` → `5 passed`
  - `source venv/bin/activate && pytest tests/hermes_cli/test_web_server.py::TestNewEndpoints::test_session_detail_projects_role_runtime_lineage_waivers_and_mismatches tests/hermes_cli/test_web_server.py::TestNewEndpoints::test_session_detail_includes_role_runtime_bundle tests/hermes_cli/test_web_server.py::TestNewEndpoints::test_get_sessions_includes_role_runtime_summary tests/hermes_cli/test_web_server.py::TestNewEndpoints::test_analytics_usage_includes_role_runtime_breakdown -q` → `4 passed`
  - `source venv/bin/activate && pytest tests/tools/test_role_invocation_tool.py tests/agent/test_role_sessions.py tests/run_agent/test_run_agent.py tests/run_agent/test_lead_findings_loop.py tests/hermes_cli/test_web_server.py tests/acp/test_role_sessions.py tests/gateway/test_api_server_role_sessions.py tests/agent/test_plan_bundle.py -q --tb=short` → `402 passed, 2 warnings`
  - `source venv/bin/activate && python3 -m py_compile $(git diff --cached --name-only | grep '\.py$')` → passed
  - security scan of added staged lines for hardcoded secrets, shell injection, dangerous `eval`/`exec`, unsafe pickle, and SQL interpolation patterns → clean
  - deterministic live transport exercise → direct `invoke_role` persistent run resumed the same `(plan_id, Developer)` SessionDB role ID, ACP resumed that same role-session ID with role metadata/parent linkage, and API-server `_run_agent` forwarded `parent_session_id`
  - `source venv/bin/activate && pytest tests/acp/test_tools.py tests/acp/test_role_sessions.py tests/gateway/test_api_server_role_sessions.py tests/agent/test_role_sessions.py tests/tools/test_role_invocation_tool.py -q --tb=short` → `51 passed, 2 warnings`
  - `git diff --check` and `git diff --cached --check` → passed
  - `cd web && yarn build` → passed
  - role skill-policy / required skill-loading slice validation at `2026-04-24T09:55:13+01:00`:
    - `/Users/stefanvanbiljon/.hermes/hermes-agent/venv/bin/python -m pytest tests/tools/test_role_invocation_tool.py tests/agent/test_role_skill_policy.py tests/agent/test_role_sessions.py -q` → `25 passed in 2.77s`
    - `cd web && yarn build` → passed
    - `git diff --check` plus `py_compile` for `tools/role_invocation_tool.py`, `agent/role_runtime.py`, and `web/scripts/generate_org_chart_data.py` → passed
    - added-line security grep over the scoped role skill-policy/loading diff → clean
    - independent `hermes chat --toolsets terminal,file` review initially found workspace parent/symlink escape, stale custom-packet skill-content heading behavior, and aggregate packet-growth issues; fixes were applied and a final independent review returned `passed: true` with no security concerns or logic errors.
  - independent reviewer subagent attempts → failed closed due missing child-agent filesystem/tool access, not due code findings; the successful final independent review used the `hermes chat --quiet --toolsets terminal,file --provider openai-codex --query ...` fallback.
  - operational robustness incident captured at `2026-04-23T21:10:06Z`: the active VS Code ACP session became fragile after repeated context compression (`Session compressed 3 times`) and a queue+interrupt sequence while resuming the independent-review blocker. Treat long-session resilience as a follow-on hardening item, not as evidence of a code-review failure.
- Last known broader pre-reset verification after data/auth fixes: final bundle `398 passed, 2 warnings`; static security grep was clean; independent review passed.
- Historical earlier slices also passed: `tests/agent/test_plan_bundle.py` + `tests/hermes_cli/test_web_server.py` reached `92 passed`; API/dashboard regression reached `143 passed` before packaging recovery.

## Planning posture

This is a hybrid plan:
- harden the role-runtime layer where it already exists
- create the remaining missing role/runtime files and tests where they do not yet exist
- reuse and extend existing session/server/UI/org-chart infrastructure where files already exist
- sequence the work so the runtime truth model exists before APIs/UI depend on it

## Why this work exists

The current org-chart/runtime split is mostly implemented in this branch, but packaging is not yet safe:
- the dashboard now has session and analytics role-runtime projections, and transport parity is covered by ACP/API-server parent-session propagation tests
- runtime orchestration includes `invoke_role` and canonical role-runtime artifacts, with role execution evidence standardized into durable plan-bundle files
- Lead-reviewed findings/remediation/completion gating is implemented at the bundle-helper layer and covered by tests
- the static Org Chart page currently depends on tracked registry/generated data files that are absent after reset recovery and must be restored before verification/commit
- broader live-workflow rollout checks and richer UI views remain follow-on work after the safe commit lands

The desired end state remains:
- Lead / PM orchestrates all work
- roles are execution lanes, not just display labels
- every canonical org-chart role defaults to `persistent_role_instance`
- every persistent role is a real SessionDB-backed Hermes agent session with stable identity, resumable history, role-specific prompting, artifact-first packet/output handoffs, and parent linkage to the Lead session
- reviewer independence comes from separate role identities plus artifact-first handoffs
- shared team memory lives in plan artifacts and session metadata rather than hidden private role context alone
- the system explicitly records which roles were planned, which actually ran, and what mode each used

## Persistent role instance refinement

The role-runtime distinction that still needs to land is:

- **Current partial state:** `persistent_role_instance` is declared by policy and recorded in bundle artifacts; `invoke_role` writes packets/outputs/evidence and records `persistent_session_id`, but it does not yet run or resume a separate role agent conversation.
- **Required final state:** `persistent_role_instance` creates or resumes an actual SessionDB-backed Hermes role session and executes the role through the normal agent loop using the role packet as input.

For a persistent role invocation, the runtime should:

1. Resolve the canonical role from `web/src/data/hermesOrgChart.registry.yaml`.
2. Compute or look up a stable role session ID such as `role-<plan-id>-developer-<hash>`.
3. Create or resume a SessionDB session for that role, linked to the Lead via `parent_session_id`.
4. Store authoritative role metadata with the session, including `plan_id`, `canonical_role`, `execution_mode`, `policy_default_execution_mode`, `task_packet_path`, `artifact_paths`, and Lead/session lineage.
5. Build a role-specific system/context supplement from the org-chart role mission, responsibilities, reporting line, runtime policy, and output requirements.
6. Run `AIAgent`/the normal conversation loop against the persistent role session with the packet as the user/task input.
7. Capture the role's actual final response as the role output artifact, not a synthetic copy of the Lead summary.
8. Update `01-manifest.json`, `02-role-execution-plan.json`, and `04-role-utilization-report.json` from the real role execution result.
9. Return a concise handoff summary to Lead; the role never communicates directly with the user.

The durable shared memory remains artifact-first. Persistent role transcript history is useful working memory for that role, but the plan bundle, findings ledger, utilization report, diffs, and validation evidence remain the cross-role source of truth.

### Role-session lifecycle requirements

Add or harden a role-session lifecycle layer in `agent/role_runtime.py` / `hermes_state.py` with helpers equivalent to:

```python
get_or_create_role_session(
    parent_session_id,
    plan_id,
    role,
    model_config,
    platform,
) -> RoleSession
```

Required behavior:
- stable ID generation per `(plan_id, canonical_role)`
- create-on-missing and resume-on-existing semantics
- parent Lead linkage via `parent_session_id`
- persisted role metadata suitable for dashboard/API queries
- status transitions: `planned` -> `active` -> `completed` / `blocked` / `paused` / `cancelled`
- close/retire semantics so persistent role sessions can be marked inactive without deleting their history

### `invoke_role` execution requirement

`tools/role_invocation_tool.py` should remain the canonical producer of role-runtime facts, but for `persistent_role_instance` it must orchestrate a real role run:

```text
Lead calls invoke_role
  -> write role packet artifact
  -> get/resume persistent role session
  -> instantiate/run the role agent with role-specific context
  -> capture final response and structured findings/output
  -> write output/evidence artifacts
  -> update manifest/execution-plan/utilization report
  -> return role handoff summary to Lead
```

For `delegated_subagent`, the runtime may continue to use isolated delegation, but the resulting metadata shape must match the persistent path so Sessions/Analytics can compare actual execution modes without heuristics.

### Findings loop connection

Validator and specialist role outputs should be ingested into the Lead-managed findings ledger:

```text
Technical Validator persistent session
  -> emits finding(s)
Lead runtime
  -> records findings as Lead-review-pending
  -> Lead accepts/rejects/defer each finding
  -> accepted finding creates Developer remediation packet
  -> Developer persistent session executes remediation
  -> original reviewer role revalidates
  -> finding closes only after accepted revalidation evidence
```

Completion remains blocked while required roles have not run or been explicitly waived, or while accepted findings remain open/in-fix/pending-revalidation.

## Core invariants

### 1. Persistent-by-default for canonical roles
- every canonical org-chart role defaults to `persistent_role_instance`
- `delegated_subagent` remains a valid explicit override
- `scheduled_role_run` remains deferred until implemented, not assumed available just because it appears in schemas
- `Lead / PM` remains the coordinating top-level role and should not downgrade to delegated mode

### 2. No heuristic truth for execution mode
- heuristics may suggest role usage or likely mode
- they must never be treated as authoritative runtime evidence
- authoritative truth must come from explicit role-execution records plus artifact linkage

### 3. Artifact-first shared memory
Source of truth for role-team work must live in:
- approved plan artifacts
- role packets
- role outputs
- role utilization reports
- findings ledgers
- repo diffs and validation outputs
- session metadata with stable session linkage

### 4. Lead-coordinated review loops
- validators and specialists report findings to Lead
- Lead decides disposition and routes remediation
- Developer does not receive autonomous reviewer side-channel work without Lead mediation
- completion requires zero accepted open findings

### 5. Explicit role skill policy
- every canonical role should declare the skills that define its baseline operating standard
- role-skill policy belongs beside runtime policy in `web/src/data/hermesOrgChart.registry.yaml`, then in generated org-chart data
- role packets and role prompts should include required and triggered skills so persistent role sessions know which procedures to load
- role utilization reports should record which skills were required and which triggered skills were declared for the invocation
- initial enforcement may be declaration-only, but the follow-on hardening should verify actual `skill_view()` loading before a role claims compliance

Use this registry shape:

```yaml
skills:
  required:
    - test-driven-development
    - systematic-debugging
  recommended:
    - subagent-driven-development
  triggered:
    - skill: implement-ui-ux-change
      when: "Kinni or Account UI/user-facing surfaces change"
    - skill: change-graphql-contract
      when: "GraphQL schema, resolver, generated types, or client operations change"
```

For NoblePro/Kinni work, historical Codex skills are first-class role-skill inputs and should be resolved from:
- `/Users/stefanvanbiljon/Developer/monorepo/_docs/dev/codex-skills.md`
- `/Users/stefanvanbiljon/Developer/monorepo/_docs/codex-skills/*/SKILL.md`
- `/Users/stefanvanbiljon/Developer/monorepo/.agents/skills/*/SKILL.md`
- `/Users/stefanvanbiljon/Developer/monorepo/skills-lock.json`

## Current implementation status

### Already present in the current working tree / index
- generic delegation plumbing
- session persistence infrastructure
- gateway/session infrastructure
- dashboard backend (`hermes_cli/web_server.py`)
- Sessions and Analytics pages
- role-runtime core primitives (`agent/role_runtime.py`, `agent/plan_bundle.py`)
- `invoke_role` tool scaffolding and registry/toolset wiring (`tools/role_invocation_tool.py`, `toolsets.py`)
- plan-bundle artifacts for manifest, role execution plan, findings ledger, utilization report, packets, outputs, and evidence
- Lead-managed findings/remediation/completion-gate helpers at the bundle layer
- ACP/API-server parent-session propagation tests for role sessions
- Org Chart page and route wiring
- restored/force-added org-chart registry and generated data (`web/src/data/hermesOrgChart.registry.yaml`, `web/src/data/hermesOrgChart.generated.ts`)

### Partially present / not yet runtime-complete
- `persistent_role_instance` now has SessionDB-backed create/resume helpers and can execute through `invoke_role` with a role runner / `AIAgent` path, but it still needs live end-to-end exercise across each transport.
- session/analytics projections can show recorded role-runtime truth, but richer lineage, waiver, mismatch, and live persistent-session views remain follow-on
- findings/remediation lifecycle helpers exist, and structured JSON findings in role outputs are auto-ingested; broader free-form prose findings extraction remains follow-on if desired.

### Still missing or incomplete
- live transport verification that CLI, ACP, API-server, and future dashboard triggers all resume the same `(plan_id, canonical_role)` persistent identity
- richer lineage / waiver / mismatch dashboard views
- optional free-form prose findings extraction beyond structured JSON blocks
- final independent review and packaging/commit readiness

## Target architecture

## A. Canonical runtime truth model

Define one authoritative role-execution model with at least:
- `role`
- `canonical_role`
- `policy_default_execution_mode`
- `execution_mode`
- `invocation_source`
- `status`
- `started_at`
- `ended_at`
- `parent_session_id`
- `child_session_id` or `persistent_session_id`
- `task_packet_path`
- `artifact_paths`
- `summary`
- `error`

Canonical execution modes:
- `persistent_role_instance`
- `delegated_subagent`
- `scheduled_role_run`
- `inline_lead_exception`

Important refinement:
- `scheduled_role_run` and `inline_lead_exception` may exist in the schema before they are fully invokable modes
- runtime/UI must distinguish “declared mode” from “implemented mode” and fail clearly for unsupported invocation paths

## B. Canonical plan-bundle layout

Introduce a bundle layout that fits the current checkout and minimizes future churn:

```text
_plans/<plan-id>/
  00-plan.md
  01-manifest.json
  02-role-execution-plan.json
  03-findings-ledger.json
  04-role-utilization-report.json
  99-summary.md
  roles/
    <role-slug>/
      packets/
      outputs/
      evidence/
```

Why `04-role-utilization-report.json`:
- it keeps findings and utilization separate
- it creates a clean canonical artifact for actual role execution truth
- it avoids renumbering if/when the bundle grows later

Minimum responsibilities:
- `01-manifest.json`
  - bundle index
  - lead session id
  - active role session ids
  - latest artifact pointers
  - recovery metadata
  - approval snapshot
- `02-role-execution-plan.json`
  - required roles
  - planned execution mode per role
  - workflow sequence
  - packet paths
  - waivers/overrides
- `03-findings-ledger.json`
  - findings
  - Lead dispositions
  - remediation routing
  - revalidation status
- `04-role-utilization-report.json`
  - actual roles used
  - actual execution mode per role
  - session lineage
  - artifact linkage
  - actual status per role
  - planned-vs-actual mismatches
  - waiver reasons for required-but-unused roles

## C. Lead workflow state machine

Canonical non-trivial workflow:
1. Lead routes the task
2. Planner drafts or updates the plan artifact
3. Lead reviews and strengthens the plan
4. User approval is captured
5. Developer executes approved scope
6. Technical Validator reviews independently
7. Additional specialists run as required
8. Lead routes remediation and revalidation loops
9. Lead emits final role utilization and findings summary

Required phases:
- `routing`
- `planning`
- `lead_review`
- `awaiting_user_approval`
- `implementation`
- `validation`
- `specialist_review`
- `remediation`
- `complete`

Critical refinement:
- approval/gating must be implemented before Sessions/Analytics claim planned-vs-actual workflow truth

## D. Dashboard/API truth rule

Sessions and Analytics should answer both:
- which roles were required/planned?
- which roles actually ran, and in what mode?

For new role-runtime flows, they must answer from:
- canonical role-runtime facts
- canonical bundle artifacts
- explicit role-utilization data

Legacy fallback behavior may still use older session heuristics, but only for pre-role-runtime sessions.

## E. Transport-neutral runtime rule

Persistent role orchestration must be implemented in the core runtime/session layer, not as a CLI-only trick.

This work must remain compatible with:
- CLI / dashboard
- ACP / VS Code
- API-server clients such as Open WebUI

## F. Long-session robustness rule

Role-team work must not depend on one ever-growing chat transcript staying healthy forever.

For long-running ACP / VS Code and role-team sessions, the runtime should make artifact-first recovery the normal path:
- treat repeated context compression as a degradation signal, not normal steady state
- recommend a fresh session after two compressions, and strongly warn/guard after three compressions
- avoid queue+interrupt handoffs while compression or cancellation is still in flight
- preserve enough `session_id`, `parent_session_id`, role metadata, plan bundle paths, latest task packet, validation evidence, and blocker state for a fresh session to resume from artifacts instead of from the compressed transcript
- run independent review from a fresh reviewer session with repo/tool access and a compact review packet, rather than from the already-large implementation session
- keep VS Code/ACP UI feedback explicit when a turn is compressing, cancelling, stale, or safer to restart

This is a follow-on resilience requirement for transport/runtime hardening. It should not block the current staged role-runtime packaging unless the implementation touches the affected ACP/session code in this same slice.

## G. Role skill policy architecture

Persistent role instances should receive explicit skill policy in the same runtime packet as their role charter. The first implementation can declare role skills and expose them in artifacts; later hardening should prove the role session actually loaded those skills.

Required data flow:
1. Add `skills.required`, `skills.recommended`, and `skills.triggered` to each role in `web/src/data/hermesOrgChart.registry.yaml`.
2. Extend `web/scripts/generate_org_chart_data.py` and `web/src/data/hermesOrgChart.generated.ts` so dashboard/org-chart consumers receive the same skill metadata.
3. Extend role packet construction in `tools/role_invocation_tool.py` / `agent/role_runtime.py` so persistent role sessions are told which role-identity skills are required and which triggered skills match the current task.
4. Extend `04-role-utilization-report.json` entries with fields such as:

```json
{
  "required_skills": ["pre-commit-qc", "run-required-validation"],
  "recommended_skills": ["systematic-debugging"],
  "triggered_skills": ["change-graphql-contract"],
  "skill_compliance": "declared"
}
```

5. Later hardening: record actual skill-load evidence from each role session and upgrade `skill_compliance` from `declared` to `verified` only when loading is proven.

Baseline mapping for canonical Hermes roles:

| Role | Required / baseline skills | Common triggered skills |
| --- | --- | --- |
| Lead / PM | `hermes-lead-workflow`, `hermes-role-team-runtime`, `repo-grounded-plan-review`; NoblePro `manage-gitlab-work-items`, `audit-change-followups` when in the monorepo | `noblepro-plan-cleanup-and-verification`, `pre-commit-qc`, `requesting-code-review`, `run-required-validation` |
| Intake / Routing | `noblepro-gitlab-bug-triage`, `repo-grounded-plan-review`; NoblePro `manage-gitlab-work-items`, `audit-change-followups` | `change-graphql-contract`, `implement-ui-ux-change`, `change-native-update-gate`, `website-migration-phase0-discovery` |
| Planner | `writing-plans`, `repo-grounded-plan-review`, `plan`, `hermes-role-team-runtime` | `run-required-validation`, release skills, migration/discovery skills, UI/contract/domain skills by scope |
| Developer | `test-driven-development`, `systematic-debugging`, `subagent-driven-development` | `implement-ui-ux-change`, `change-graphql-contract`, `change-native-update-gate`, `upgrade-expo-sdk`, Kinni website/OAuth, WordPress, Stripe skills |
| Technical Validator | `requesting-code-review`, `systematic-debugging`; NoblePro `pre-commit-qc`, `run-required-validation`, `audit-change-followups` | `change-graphql-contract`, `implement-ui-ux-change`, `triage-release-pipeline` |
| UX / Evidence Auditor | `dogfood`; NoblePro `implement-ui-ux-change`, `audit-change-followups`, `run-required-validation` | `kinni-pixel-linked-account-verification`, Kinni website skills, WordPress/live UX skills, `popular-web-designs` |
| Release Manager | NoblePro `run-beta-ota-release`, `run-beta-native-release`, `run-production-ota-release`, `run-production-native-release`, `triage-release-pipeline`, `run-required-validation`, `manage-gitlab-work-items` | `change-native-update-gate`, `upgrade-expo-sdk`, `update-docs-and-runbooks`, `pre-commit-qc` |
| Contract Specialist | NoblePro `change-graphql-contract`, `change-native-update-gate`, `run-required-validation`; `systematic-debugging` | Stripe, OAuth, account-hub, WordPress/API contract skills |
| Native / Device Validation Specialist | `kinni-pixel-linked-account-verification`; NoblePro `change-native-update-gate`, `upgrade-expo-sdk`, `run-required-validation` | native release skills, OAuth skills |
| Performance Specialist | `systematic-debugging`; NoblePro `run-required-validation`, `audit-change-followups` | contract/query performance, Kinni website/rendering, QC workflow hardening; gap: add dedicated `noblepro-performance-investigation` later |
| Physical Device Verification Specialist | `kinni-pixel-linked-account-verification`, `dogfood`; NoblePro `run-required-validation` | native gate, Expo, native release, OAuth skills |
| GitLab / Artifact Steward | `noblepro-gitlab-bug-triage`; NoblePro `manage-gitlab-work-items`, `audit-change-followups`, `pre-commit-qc`, `update-docs-and-runbooks` | release skills, plan-cleanup skills, GitHub issue filing when relevant |

## Highest-priority remaining gaps

1. Re-verify and safely package the staged role-runtime foundation after restoring force-added org-chart data files
2. Run independent review from a fresh context with real repo/tool access, then commit only intended role-runtime files
3. Add explicit role skill policy to the org-chart registry and generated data (`skills.required`, `skills.recommended`, `skills.triggered`)
4. Propagate role skill policy into role packets, role prompts, and `04-role-utilization-report.json`
5. Add declaration-level tests for role skill metadata in registry generation, packet construction, and utilization reporting
6. Later harden actual role-session skill loading and compliance verification (`declared` -> `verified`)
7. Complete richer UI polish for lineage / waiver / mismatch views if the current dashboard projection is not sufficient
8. Add long-session robustness guardrails for ACP / VS Code role-team work so compressed or interrupted sessions hand off through artifacts instead of becoming fragile blockers

## Refined rollout order from the exact current checkout

0. Re-verify and commit the staged role-runtime foundation without unrelated dashboard/Kinni branding drift
1. Add explicit role skill policy to `web/src/data/hermesOrgChart.registry.yaml`
2. Regenerate `web/src/data/hermesOrgChart.generated.ts` and update generated/frontend types for role skills
3. Propagate role skills into role packet construction and role-specific prompt/context building
4. Record required/recommended/triggered skill declarations in `04-role-utilization-report.json`
5. Add tests for registry parsing/generation, packet skill metadata, and utilization-report skill declarations
6. Run final declaration-level verification (`pytest` focused backend slice + `cd web && yarn build`)
7. Later harden actual role-session skill loading and compliance proof
8. Add ACP / VS Code long-session guardrails and artifact-first handoff/restart semantics as a follow-on transport-hardening slice
9. Run final end-to-end role-team workflow verification

## Dependency notes

To keep sequencing exact and avoid circular work:
- Task 2 depends on Task 1 because `invoke_role` needs schema and bundle primitives
- Task 3 depends on Task 2 because approval/reporting must emit canonical runtime artifacts
- Task 4 depends on Task 3 because APIs should project canonical Lead/runtime truth rather than invent it
- Task 5 depends on Task 4 because the UI should consume the canonical API model
- Task 6 depends on Task 3 and may proceed in parallel with Task 5 once the runtime truth model is stable
- Task 7 depends on Tasks 4 and 6 because enforcement should work across transports and be visible to backend consumers
- final verification depends on Tasks 5, 6, and 7

## Execution-ready implementation breakdown

### Task 1: Harden canonical role-runtime schemas and plan-bundle primitives

**Status:** complete; core runtime and plan-bundle primitives are green

**Objective:** Harden the existing runtime schema layer and durable plan-bundle helpers, then tighten manifest patch validation before building the `invoke_role` tool.

**Files:**
- Modify: `agent/role_runtime.py`
- Modify: `agent/plan_bundle.py`
- Modify: `web/src/data/hermesOrgChart.registry.yaml`
- Modify: `web/scripts/generate_org_chart_data.py`
- Update: `web/src/data/hermesOrgChart.generated.ts`
- Modify: `tests/agent/test_plan_bundle.py`
- Test: `tests/hermes_cli/test_web_server.py`

**Implement:**
- canonical enums/constants for:
  - execution modes
  - role statuses
  - findings statuses
  - current phases
- role policy schema parsing and org-chart role resolution
- bundle path helpers for `_plans/<plan-id>/`
- default artifact creation for:
  - `00-plan.md`
  - `01-manifest.json`
  - `02-role-execution-plan.json`
  - `03-findings-ledger.json`
  - `04-role-utilization-report.json`
  - `99-summary.md`
- stricter manifest patch validation for scalar-vs-object field shapes
- generated frontend types aligned with the runtime policy fields

**Acceptance criteria:**
- the bundle shape is explicit and stable
- runtime and frontend use the same policy/schema names
- role-runtime helpers exist as real code, not plan assumptions
- invalid nested patch shapes are rejected by the plan bundle validation layer

**Depends on:** none

### Task 2: Add `invoke_role` and canonical runtime/session metadata wiring

**Status:** partially complete; the invoke_role tool, registry wiring, and bundle artifact emission are in place, but true persistent role execution is not yet complete. `invoke_role` currently records `persistent_session_id` and artifacts; it still needs to create/resume real SessionDB-backed role sessions and run the role through the normal agent loop.

**Objective:** Introduce a first-class role-aware tool and make it the canonical producer of role-runtime facts, with `persistent_role_instance` functioning as an actual persistent agent session rather than only a recorded execution mode.

**Files:**
- Modify: `tools/role_invocation_tool.py`
- Modify: `tools/registry.py`
- Modify: `toolsets.py`
- Modify: `tests/tools/test_role_invocation_tool.py`
- Modify: `run_agent.py`
- Modify: `hermes_state.py`
- Modify: `gateway/session.py`
- Test: `tests/run_agent/test_run_agent.py`
- Test: `tests/agent/test_role_sessions.py` (new)
- Test: `tests/acp/test_role_sessions.py` (new)
- Test: `tests/gateway/test_api_server_role_sessions.py` (new)

**Implemented so far:**
- canonical role validation against org-chart roles and aliases
- default mode resolution from role policy
- explicit mode overrides
- packet/output/evidence artifact writing into the plan bundle
- manifest / execution-plan / utilization-report updates
- parent session metadata is preserved in the manifest and role session record
- explicit unsupported-mode behavior for declared-but-unimplemented modes

**Still to wire up:**
- real SessionDB create/resume behavior for `persistent_role_instance`
- role-specific prompt/context construction from the org-chart registry
- actual `AIAgent` execution for persistent role sessions, using the packet as input and saving the role response back to the bundle
- session metadata parity for delegated and persistent role paths
- `run_agent.py` / gateway / ACP / API-server session surfaces
- dedicated runtime, persistence, and transport tests beyond the tool slice

**Acceptance criteria:**
- `invoke_role` exists and is registered
- `toolsets.py` exposes it
- `run_agent.py` dispatches it
- repeated persistent invocations for the same `(plan_id, canonical_role)` resume the same SessionDB role session
- persistent role runs execute through the normal agent loop and write actual role responses to output artifacts
- persistent and delegated role runs emit comparable canonical metadata
- unsupported modes fail clearly and truthfully

**Depends on:** Task 1

### Task 2A: Implement real persistent role-session execution

**Status:** mostly complete for the unit-tested foundation; `get_or_create_role_session()`, role-specific prompt construction, SessionDB role metadata persistence, `invoke_role` persistent execution wiring, and same-role/different-role persistence tests are implemented and green. Remaining work is live end-to-end transport exercise, close/retire semantics, and broader UI/analytics polish.

**Objective:** Make `persistent_role_instance` mean an actual resumable Hermes role session, not only an execution-mode value in plan-bundle metadata.

**Files:**
- Modify: `agent/role_runtime.py`
- Modify: `hermes_state.py`
- Modify: `tools/role_invocation_tool.py`
- Modify: `run_agent.py`
- Modify: `agent/prompt_builder.py`
- Modify: `gateway/session.py`
- Modify: `acp_adapter/session.py`
- Modify: `gateway/platforms/api_server.py`
- Test: `tests/agent/test_role_sessions.py` (new)
- Modify/Test: `tests/tools/test_role_invocation_tool.py`
- Modify/Test: `tests/acp/test_role_sessions.py`
- Modify/Test: `tests/gateway/test_api_server_role_sessions.py`

**Implement:**
- `get_or_create_role_session()` / resume helper keyed by `(plan_id, canonical_role)`
- persisted SessionDB role metadata for `plan_id`, `canonical_role`, `execution_mode`, `policy_default_execution_mode`, `parent_session_id`, `persistent_session_id`, packet path, and artifact paths
- role-specific system/context supplement built from `hermesOrgChart.registry.yaml`
- `invoke_role` persistent path that creates/resumes the role session, runs the normal `AIAgent` loop using the role packet as input, captures the final response, and writes it to the role output artifact
- utilization/manifest updates from the actual run result
- clear failure behavior if a role run cannot be started or resumed

**TDD acceptance tests:**
- same `plan_id` + `Developer` invoked twice resumes the same SessionDB role session
- `Developer` and `Technical Validator` for the same plan receive distinct persistent session IDs
- persistent role session has `parent_session_id` pointing to the Lead session
- role output artifact contains the actual role response from the role session, not the Lead summary fallback
- SessionDB metadata and `04-role-utilization-report.json` agree on role, execution mode, status, and artifact paths
- ACP/API-server initiated invocations preserve the same role identity semantics as CLI

**Depends on:** Task 2 and safe packaging/reverification of the staged foundation

### Task 3: Implement Lead approval/gating and explicit role execution reporting

**Status:** partially complete; the Org Chart page and route wiring are in place, while Sessions/Analytics role-truth surfaces and backend API support still remain.

**Objective:** Enforce the intended workflow before downstream APIs and UI depend on it.

**Files:**
- Modify: `run_agent.py`
- Modify: `agent/prompt_builder.py`
- Modify: `agent/plan_bundle.py`
- Modify: `agent/role_runtime.py`
- Test: `tests/run_agent/test_lead_findings_loop.py` (new)
- Test: `tests/run_agent/test_run_agent.py`

**Implement:**
- explicit role execution plan creation before non-trivial work
- Lead review and user approval gating before implementation
- `04-role-utilization-report.json` emission after execution
- planned-vs-actual mismatch reporting
- explicit role waivers with recorded reasons
- concise final role utilization summary shape for Lead responses

**Acceptance criteria:**
- the runtime can truthfully say which roles were planned and which actually ran
- implementation cannot begin before required approval in workflows that require it
- required roles must either run or be explicitly waived

**Depends on:** Task 2

### Task 4: Add canonical Sessions/Analytics API support for role-runtime truth

**Status:** complete; role-runtime session/detail and analytics payloads now expose canonical truth and are covered by tests.

**Objective:** Make backend projections truthful before UI polish.

**Files:**
- Modify: `hermes_cli/web_server.py`
- Modify: `web/src/lib/api.ts`
- Test: `tests/hermes_cli/test_web_server.py`

**Implement:**
- session payload additions:
  - role execution plan
  - role utilization report
  - findings summary / open findings
  - policy-default vs actual mode
- analytics payload additions:
  - counts by role
  - counts by execution mode
  - default-vs-override counts
  - findings raised/closed by role
  - send-back counts
- compatibility behavior for legacy sessions lacking canonical role facts

**Acceptance criteria:**
- dashboard APIs answer policy questions and actual runtime questions separately
- new role-runtime sessions no longer depend on ad hoc heuristics as their primary truth model
- legacy sessions degrade gracefully

**Depends on:** Task 3

### Task 5: Update Sessions/Analytics UI and complete Org Chart UI

**Status:** partially complete; the Org Chart page and route wiring are in place, and Sessions/Analytics now surface role-runtime summaries, but richer lineage, waiver, and mismatch views still remain.

**Objective:** Surface the role-team model clearly in the current web app.

**Files:**
- Created: `web/src/pages/OrgChartPage.tsx`
- Modify: `web/src/pages/SessionsPage.tsx`
- Modify: `web/src/pages/AnalyticsPage.tsx`
- Modify: `web/src/App.tsx`
- Update: `web/src/data/hermesOrgChart.generated.ts`

**Implement:**
- Org Chart UI for canonical roles and runtime policy badges
- Sessions UI for:
  - planned vs actual role usage
  - role lineage
  - findings state
  - waiver / mismatch visibility
- Analytics UI for:
  - role execution mode counts
  - default-vs-override counts
  - findings raised/closed and send-back counts
- route wiring for the new Org Chart page

**Acceptance criteria:**
- Org Chart shows policy/default identity, not per-run noise
- Sessions/Analytics show actual run truth for new role-runtime flows

**Depends on:** Task 4

### Task 6: Complete transport parity and persistent lifecycle/worktree hardening

**Status:** in progress

**Objective:** Make the runtime model true across CLI, ACP, and API-server initiated work.

**Files:**
- Modify: `gateway/session.py`
- Modify: `acp_adapter/session.py`
- Modify: `acp_adapter/tools.py`
- Modify: `gateway/platforms/api_server.py`
- Modify: `cli.py`
- Modify: `hermes_state.py`
- Test: `tests/acp/test_role_sessions.py` (new)
- Test: `tests/gateway/test_api_server_role_sessions.py` (new)
- Test: `tests/tools/test_role_invocation_tool.py`

**Implement:**
- create/resume/inspect role sessions consistently across transports
- ensure ACP tooling understands `invoke_role`
- persist role metadata in a queryable SessionDB-backed shape, not only in plan-bundle JSON
- preserve parent Lead linkage and role session identity when requests originate from CLI, ACP, API-server, or future dashboard triggers
- implement close/retire semantics for persistent role sessions
- enforce or truthfully defer `worktree_strategy` behavior by role
- keep SessionDB as the source of truth for identity/restoration
- add long-session degradation signals for ACP / VS Code sessions that have compressed repeatedly or have an in-flight cancel/compression state
- make fresh-session handoff recoverable from plan-bundle artifacts, role metadata, latest packet/output/evidence paths, validation evidence, and current blocker state
- ensure independent review can be launched from a fresh reviewer context with compact artifact/diff instructions and real repo/tool access, rather than relying on the already-large implementation session

**Acceptance criteria:**
- ACP and API-server initiated sessions can use the same role identity model as CLI sessions
- transport differences do not change runtime truth or analytics semantics
- a persistent role session created from one transport can be resumed without minting a second role identity for the same `(plan_id, canonical_role)`
- worktree handling is either enforced or explicitly marked deferred by policy/runtime
- ACP / VS Code sessions surface degraded long-context states before they become silent stalls
- a new session can continue a role-team workflow from artifacts without relying on a fragile compressed transcript

**Depends on:** Task 3

**Parallelization note:** may proceed in parallel with Task 5 once Task 4’s backend shape is stable enough for UI consumers.

### Task 7: Enforce findings/remediation loops and completion gating

**Status:** in progress — core bundle-level enforcement verified

**Objective:** Make the team workflow enforceable instead of advisory.

**Files:**
- Modify: `run_agent.py`
- Modify: `agent/plan_bundle.py`
- Modify: `agent/role_runtime.py`
- Modify: `hermes_cli/web_server.py`
- Test: `tests/run_agent/test_lead_findings_loop.py`
- Test: `tests/hermes_cli/test_web_server.py`

**Implement:**
- findings ingestion from validator/specialist outputs
- Lead-reviewed dispositions in `03-findings-ledger.json`
- remediation packet generation for Developer
- revalidation routing back to the original reviewer role
- completion blocking while accepted findings remain open
- required-role and waiver enforcement based on the canonical role execution plan/utilization report

**Acceptance criteria:**
- validators cannot silently send work directly back to Developer
- accepted findings remain blocking until revalidated closed
- completion cannot be declared while required-role execution or accepted findings remain unresolved

**Verified progress:**
- `agent.plan_bundle.record_finding()` records validator/specialist findings as Lead-review-pending and does not create Developer remediation packets directly
- `lead_review_finding()` records Lead disposition and creates Developer remediation packets only for accepted findings
- `mark_finding_pending_revalidation()`, `close_finding()`, and `completion_gate_status()` now enforce the blocking lifecycle for open / in-fix / pending-revalidation findings and required-role waivers
- Verified by `source venv/bin/activate && pytest tests/run_agent/test_lead_findings_loop.py -q` and the combined slice listed below

**Depends on:** Tasks 4 and 6

### Task 8: Final integration verification and rollout checklist

**Status:** blocked on packaging recovery — verification bundle was green before reset

**Objective:** Validate the whole feature as one coherent system before normal use.

**Verification bundle after implementation:**
- `source venv/bin/activate && pytest tests/tools/test_role_invocation_tool.py -q`
- `source venv/bin/activate && pytest tests/run_agent/test_run_agent.py -q`
- `source venv/bin/activate && pytest tests/run_agent/test_lead_findings_loop.py -q`
- `source venv/bin/activate && pytest tests/hermes_cli/test_web_server.py -q`
- `source venv/bin/activate && pytest tests/acp/test_role_sessions.py -q`
- `source venv/bin/activate && pytest tests/gateway/test_api_server_role_sessions.py -q`
- `source venv/bin/activate && pytest tests/agent/test_plan_bundle.py -q`
- `cd web && yarn build`

**Required end-to-end workflow to prove:**
- Lead -> Planner -> Lead review -> user approval -> Developer -> Technical Validator -> Lead remediation loop -> close findings -> final role utilization summary

**Acceptance criteria:**
- one realistic end-to-end role-team workflow passes
- durable artifacts are present and internally consistent
- dashboard/session views can explain what happened truthfully
- transport origin does not change the role-runtime truth model

**Verified progress:**
- Combined verification passed pre-reset, then again after data/auth fixes: `source venv/bin/activate && pytest tests/tools/test_role_invocation_tool.py tests/run_agent/test_run_agent.py tests/run_agent/test_lead_findings_loop.py tests/hermes_cli/test_web_server.py tests/acp/test_role_sessions.py tests/gateway/test_api_server_role_sessions.py tests/agent/test_plan_bundle.py -q --tb=short` → latest historical result `398 passed, 2 warnings`
- Dashboard/API regression slice passed earlier: `source venv/bin/activate && pytest tests/gateway/test_api_server.py tests/gateway/test_api_server_multimodal.py tests/gateway/test_api_server_role_sessions.py -q --tb=short` → 143 passed, 82 warnings
- Frontend build passed: `cd web && yarn build`
- Current post-reset state is not green until `web/src/data/hermesOrgChart.registry.yaml` and `web/src/data/hermesOrgChart.generated.ts` are restored and force-added.

**Immediate packaging checklist:**
- Restore/force-add the two missing org-chart data files.
- Confirm staged diff excludes unrelated dashboard/Kinni branding files (`web/public/kinni-logo.svg`, `web/src/themes/*`, `web/src/pages/QuotaPage.tsx`, `web/src/components/ThemeSwitcher.tsx`, etc.).
- Re-run `git diff --cached --check`, final pytest bundle, `cd web && yarn build`, static security grep, and independent review.
- Commit with `[verified] feat(role-runtime): add role-team orchestration` only after the current tree is green.

**Depends on:** Tasks 5, 6, and 7

### Task 9: Add role skill policy declarations and runtime propagation

**Status:** implemented in current working tree; declaration/reporting layer plus required skill-content load-verification are green for focused coverage

**Objective:** Make role-skill expectations first-class runtime metadata so persistent roles know which procedural skills define their baseline behavior and which domain skills should be loaded for a specific task.

**Files:**
- Modify: `web/src/data/hermesOrgChart.registry.yaml`
- Modify: `web/scripts/generate_org_chart_data.py`
- Update: `web/src/data/hermesOrgChart.generated.ts`
- Modify: `agent/role_runtime.py`
- Modify: `tools/role_invocation_tool.py`
- Modify: `agent/prompt_builder.py`
- Modify/Test: `tests/tools/test_role_invocation_tool.py`
- Modify/Test: `tests/hermes_cli/test_web_server.py`
- Add/Modify frontend type/build coverage as needed via `web/src/lib/api.ts`

**Implement:**
- add `skills.required`, `skills.recommended`, and `skills.triggered` to every canonical role in the org-chart registry
- include baseline NoblePro/Kinni historical Codex skill names in the role mappings where applicable
- regenerate org-chart data and expose skill metadata to the Org Chart page/API consumers
- add role skill metadata to role packets and role-specific prompt/context construction
- record `required_skills`, `recommended_skills`, `triggered_skills`, `skill_compliance`, `loaded_required_skills`, `missing_required_skills`, and `loaded_skill_sources` in role utilization/reporting entries
- load required skill content into role packets where the skill is available from installed Hermes skills or workspace Kinni/Codex skill docs

**Acceptance criteria:**
- the org-chart registry is the source of truth for role skill policy
- generated org-chart data includes role skill metadata without breaking the dashboard build
- `invoke_role` role packets include the relevant skill policy for the invoked role
- utilization reports record skill declarations and required-skill load evidence in a machine-readable shape
- declaration-level tests cover at least one baseline role and one triggered skill
- invocation tests cover required-skill content loading from installed Hermes skills and workspace Kinni/Codex skill docs plus missing-required-skill partial compliance

**Verified progress:**
- Added `skills.required`, `skills.recommended`, and `skills.triggered` to all 12 canonical org-chart roles in `web/src/data/hermesOrgChart.registry.yaml`.
- Added generated TypeScript skill-policy interfaces (`RoleSkillPolicy`, `RoleSkillTrigger`) and `OrgRole.skills` to `web/scripts/generate_org_chart_data.py`, then regenerated `web/src/data/hermesOrgChart.generated.ts`.
- Added `Skill policy: ...` to `agent.role_runtime.role_system_prompt()` so persistent role sessions receive the role's baseline/recommended/triggered skill policy.
- Added skill policy metadata to `invoke_role` packets, execution-plan records, utilization-report records, and tool result payloads (`required_skills`, `recommended_skills`, `triggered_skills`, `skill_policy_source`, `skill_compliance`, `loaded_required_skills`, `missing_required_skills`, `loaded_skill_sources`).
- Added required-skill content resolution in `tools/role_invocation_tool.py`: installed Hermes skills are loaded through `skill_view`, workspace NoblePro/Kinni Codex skills are found under `_docs/codex-skills/*/SKILL.md`, and workspace external skills are found under `.agents/skills/*/SKILL.md`. Loaded required skill content is appended to role packets under `## Loaded required skill content`; missing required skills are reported without blocking the role invocation. Skill names are constrained to a safe path segment pattern and loaded skill content is capped at 100 KB to avoid path traversal and packet bloat.
- `skill_compliance` now reports `verified` when all required skills are loaded and `partial` when any required skill is missing. Recommended and triggered skills remain declared policy until a later task-trigger resolver/content-loader is added.
- Added focused regression coverage in `tests/agent/test_role_skill_policy.py` and `tests/tools/test_role_invocation_tool.py` for registry declarations, generated TypeScript type/data preservation, role prompt skill-policy inclusion, packet metadata, utilization-report metadata, tool-result metadata, installed required-skill loading, workspace Kinni/Codex skill loading, missing-required-skill partial compliance, unsafe skill-name rejection, and oversized skill-content rejection.
- Current focused verification: `/Users/stefanvanbiljon/.hermes/hermes-agent/venv/bin/python -m pytest tests/agent/test_role_skill_policy.py -q` → `3 passed`.
- Current integration-adjacent verification: `/Users/stefanvanbiljon/.hermes/hermes-agent/venv/bin/python -m pytest tests/tools/test_role_invocation_tool.py tests/agent/test_role_skill_policy.py tests/agent/test_role_sessions.py -q` → `19 passed in 3.82s`.
- Current Python compile check: `/Users/stefanvanbiljon/.hermes/hermes-agent/venv/bin/python -m py_compile tools/role_invocation_tool.py` → passed.
- Dashboard build after regenerated org-chart data: `cd web && yarn build` → passed.

**Follow-on hardening:**
- add task-trigger resolution so relevant `skills.triggered` entries are loaded when packet/domain conditions match
- decide whether selected `skills.recommended` entries should be content-loaded for persistent roles or remain guidance-only
- add dashboard/API projections for `loaded_required_skills`, `missing_required_skills`, and `loaded_skill_sources` if role-skill compliance needs to be visible outside bundle artifacts

**Verification:**
- `/Users/stefanvanbiljon/.hermes/hermes-agent/venv/bin/python -m pytest tests/agent/test_role_skill_policy.py -q`
- `/Users/stefanvanbiljon/.hermes/hermes-agent/venv/bin/python -m pytest tests/tools/test_role_invocation_tool.py tests/hermes_cli/test_web_server.py -q --tb=short`
- `cd web && yarn build`

**Depends on:** Task 8 packaging/rebaseline if this is not included in the same commit; otherwise run after the registry/generator files are restored and force-added.

## Files most likely to change

### Runtime / bundle files to harden or add
- `agent/role_runtime.py`
- `agent/plan_bundle.py`
- `tools/role_invocation_tool.py`

### Existing runtime / orchestration files
- `tools/registry.py`
- `toolsets.py`
- `run_agent.py`
- `hermes_state.py`
- `gateway/session.py`
- `acp_adapter/session.py`
- `acp_adapter/tools.py`
- `gateway/platforms/api_server.py`
- `agent/prompt_builder.py`
- `cli.py`

### Existing dashboard / data files
- `hermes_cli/web_server.py`
- `web/src/lib/api.ts`
- `web/src/data/hermesOrgChart.registry.yaml`
- `web/src/data/hermesOrgChart.generated.ts`
- `web/src/pages/SessionsPage.tsx`
- `web/src/pages/AnalyticsPage.tsx`
- `web/src/App.tsx`

### UI / generator files to add or update
- `web/scripts/generate_org_chart_data.py`
- `web/src/pages/OrgChartPage.tsx`

### Tests to add or update
- `tests/tools/test_role_invocation_tool.py`
- `tests/agent/test_plan_bundle.py`
- `tests/agent/test_role_sessions.py`
- `tests/run_agent/test_lead_findings_loop.py`
- `tests/acp/test_role_sessions.py`
- `tests/gateway/test_api_server_role_sessions.py`

## Validation plan

### Runtime truth validation
- verify `invoke_role` emits canonical metadata for delegated and persistent paths
- verify repeated persistent invocations for the same `(plan_id, canonical_role)` resume the same SessionDB session
- verify Developer and Technical Validator receive separate persistent session identities for the same plan
- verify persistent role runs execute through the normal agent loop and save actual role responses into output artifacts
- verify manifest, findings ledger, and utilization report stay internally consistent
- verify planned-vs-actual mismatches and waivers are recorded explicitly

### Workflow validation
- verify approval gating blocks implementation when required
- verify findings/remediation/revalidation loops are Lead-mediated
- verify completion blocks on accepted open findings

### API / UI validation
- verify new role-runtime sessions use canonical runtime facts rather than ad hoc fallback behavior
- verify legacy sessions degrade gracefully
- verify Org Chart shows stable policy identity while Sessions/Analytics show per-run truth

### Transport validation
- verify CLI, ACP, and API-server initiated sessions produce comparable role-runtime truth and lineage

### Role skill policy validation
- verify the org-chart registry accepts `skills.required`, `skills.recommended`, and `skills.triggered` for every canonical role
- verify generated org-chart data preserves required/recommended/triggered skill metadata
- verify role packets and prompt/context supplements include the role skill policy
- verify utilization report entries record `required_skills`, `recommended_skills`, `triggered_skills`, `skill_compliance`, loaded required skills, missing required skills, and loaded skill source evidence
- verify required skill content is loaded into role packets from installed Hermes skills and workspace Kinni/Codex skill docs
- verify missing required skills downgrade compliance to `partial` instead of silently claiming `verified`

## Role skill policy evolution model

Yes: role skills and assignments are expected to evolve over time. Treat them as a governed workflow asset, not a one-time static mapping.

Evolution loop:
1. Capture recurring misses, review findings, release incidents, validation gaps, or repeated Lead corrections as candidates for skill-policy change.
2. Decide whether the fix belongs in an existing skill, a new skill, or a role mapping change.
3. Update the source skill documentation first when procedure changes are needed.
4. Update `web/src/data/hermesOrgChart.registry.yaml` when role ownership or trigger conditions change.
5. Regenerate `web/src/data/hermesOrgChart.generated.ts` and run role-skill policy tests plus dashboard build.
6. Record the change in the plan or MR artifact so future Leads can see why the workflow changed.
7. Periodically audit whether required skills are too broad/noisy or whether triggered skills are missing common surfaces.

Governance rule:
- role assignments may evolve, but they must remain explicit, reviewable, and test-covered; do not let hidden prompt drift or ad hoc Lead memory become the source of truth.

## Risks and tradeoffs

### 1. Overbuilding before the truth model is stable
Mitigation:
- land the runtime schema, bundle primitives, and approval/reporting model before broad UI work

### 2. Dashboard truth drifting from runtime truth
Mitigation:
- make Sessions/Analytics projections read canonical runtime/bundle data for new sessions
- reserve fallbacks for legacy compatibility only

### 3. Persistent sessions becoming opaque private brains
Mitigation:
- require packet/output artifact linkage and Lead-mediated review loops

### 4. Too much friction for normal tasks
Mitigation:
- keep most role-mode selection internal to Lead orchestration
- expose concise summaries to the user rather than every internal detail

### 5. Transport parity lagging behind dashboard polish
Mitigation:
- do not declare the initiative done until Task 6 closes transport parity and lifecycle gaps

### 6. Long-running ACP sessions becoming fragile context buckets
Mitigation:
- use plan bundles, role packets, validation evidence, and SessionDB role metadata as the recoverable source of truth
- warn or hand off before repeated compression turns an implementation session into an unreliable private transcript
- isolate review/packaging work into fresh reviewer contexts with explicit repo/tool access

## Definition of done

This initiative is complete when:
- every canonical org-chart role defaults to `persistent_role_instance`
- `invoke_role` and related runtime/session metadata are the canonical source of role execution truth
- `persistent_role_instance` creates/resumes real SessionDB-backed role sessions rather than only recording planned artifacts
- persistent role sessions execute through the normal Hermes agent loop with role-specific org-chart context and stable resumable history
- role output artifacts contain actual role responses from those sessions, not synthetic copies of Lead summaries
- the plan bundle includes a first-class role utilization report artifact
- Lead approval/gating and planned-vs-actual role reporting are enforced for non-trivial workflows
- dashboard/session APIs can truthfully show policy default vs actual mode per role
- Sessions/Analytics for new runs no longer depend primarily on fallback heuristics
- ACP/API-server/CLI initiated role-team runs share the same persistent role identity model
- accepted validator/specialist findings always route through Lead review and remain blocking until closed
- completion gating uses explicit recorded role execution data plus zero accepted open findings
- every canonical role declares required/recommended/triggered skills in the org-chart registry
- role packets and prompts expose role skill policy to persistent role sessions
- role utilization reports record declared role skill expectations without overstating actual skill-load verification
- artifact-first handoffs remain the durable shared memory for large-codebase work

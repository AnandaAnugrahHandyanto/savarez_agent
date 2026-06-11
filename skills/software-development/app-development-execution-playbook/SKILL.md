---
name: app-development-execution-playbook
description: Use when moving from an app idea or product spec into actual AI-assisted implementation with Claude Code/Codex; creates PRD, source-of-truth docs, MVP locks, phase packets, data/API contracts, test gates, and anti-scope-creep rules.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [app-dev, product, claude-code, execution, mvp, planning]
    related_skills: [claude-code, writing-plans, test-driven-development, requesting-code-review]
---

# App Development Execution Playbook

## Overview

Use this when an app idea, PRD, Figma design, or product note set needs to become a real implementation without Claude Code overbuilding or drifting into unapproved scope.

The core rule is:

```text
Do not build from vague product intent.
Build from one locked product/feature packet at a time.
```

Apps need a different control system from games. Games center on loops, content, balance, assets, and fun validation. Apps center on users, jobs-to-be-done, data, permissions, integrations, privacy, reliability, and measurable workflows.

## When to Use

Use this when the user says things like:

- "앱 개발을 Claude Code로 시작하려는데 뭐부터 하지?"
- "Figma랑 PRD가 있는데 실제 구현 지시로 바꿔줘"
- "앱용 CLAUDE.md 절대 규칙 만들어줘"
- "MVP 앱을 스코프 안 터지게 만들고 싶어"
- "기능별로 AI에게 작업 패킷을 주고 싶어"

Do not use this to replace product discovery. Use it after the product direction is good enough to lock an MVP or prototype.

## Required Project Control Files

Create or verify these files before implementation:

```text
CLAUDE.md                  # absolute rules for AI agents
PROJECT_INDEX.md           # document map and priority
PRODUCT_SSoT.md            # single source of truth for product/app
MVP_LOCK.md                # current build scope: included/excluded
BUILD_PLAN.md              # implementation phase sequence
FEATURE_SPEC_INDEX.md      # feature packets and dependencies
DATA_API_CONTRACT.md       # data model, API, permissions, integrations
QA_CHECKLIST.md            # test gates and acceptance criteria
```

Optional but recommended:

```text
UX_FLOW.md                 # core user flows and states
DESIGN_HANDOFF.md          # Figma/screen/component contract
ENVIRONMENT.md             # env vars, local/dev/prod setup
SECURITY_PRIVACY.md        # secrets, PII, auth, consent, retention
```

## App vs Game: Why a Separate Playbook Exists

Use a separate app playbook because app development has different failure modes.

| Area | Game Playbook | App Playbook |
|---|---|---|
| Primary proof | Fun/core loop | User job completed reliably |
| Scope risk | Too many systems/content | Too many integrations/admin/settings |
| Core docs | GAME_SSoT, MVP_LOCK, loop specs | PRODUCT_SSoT, MVP_LOCK, user flows, data/API contract |
| Testing | manual gameplay loop, balance checks | unit/integration/e2e, permissions, data states |
| Assets | art/audio manifest, runtime text rules | design system, component states, responsive layout |
| Safety | content/asset scope | secrets, PII, auth, privacy, payments |

So yes: make an app-specific version instead of reusing only the game workflow.

## Recommended Project Structure

```text
AppProject/
├── CLAUDE.md
├── PROJECT_INDEX.md
├── PRODUCT_SSoT.md
├── MVP_LOCK.md
├── BUILD_PLAN.md
├── FEATURE_SPEC_INDEX.md
├── DATA_API_CONTRACT.md
├── QA_CHECKLIST.md
│
├── docs/
│   ├── 00_control/
│   │   ├── decision_log.md
│   │   ├── change_request_log.md
│   │   └── terminology.md
│   ├── 01_product/
│   │   ├── product_brief.md
│   │   ├── target_users.md
│   │   ├── jobs_to_be_done.md
│   │   ├── success_metrics.md
│   │   └── non_goals.md
│   ├── 02_ux/
│   │   ├── user_flows.md
│   │   ├── screen_inventory.md
│   │   ├── empty_loading_error_states.md
│   │   └── accessibility.md
│   ├── 03_design/
│   │   ├── design_handoff.md
│   │   ├── component_contract.md
│   │   ├── responsive_rules.md
│   │   └── copy_text_keys.md
│   ├── 04_data_api/
│   │   ├── data_model.md
│   │   ├── api_contract.md
│   │   ├── auth_permissions.md
│   │   └── integrations.md
│   ├── 05_features/
│   │   ├── F001_project_skeleton.md
│   │   ├── F002_auth_or_identity.md
│   │   ├── F003_primary_workflow.md
│   │   ├── F004_data_crud.md
│   │   └── F005_notifications_or_exports.md
│   ├── 06_tech/
│   │   ├── architecture.md
│   │   ├── environment.md
│   │   ├── coding_conventions.md
│   │   └── deployment.md
│   ├── 07_testing/
│   │   ├── test_strategy.md
│   │   ├── e2e_user_paths.md
│   │   └── acceptance_criteria.md
│   └── 08_release/
│       ├── launch_checklist.md
│       ├── monitoring.md
│       └── support_runbook.md
```

## Document Authority Order

Put this in `CLAUDE.md`:

```md
## Source of Truth Priority

If documents conflict, follow this order:

1. CLAUDE.md
2. PRODUCT_SSoT.md
3. MVP_LOCK.md
4. DATA_API_CONTRACT.md
5. BUILD_PLAN.md
6. FEATURE_SPEC_INDEX.md and docs/05_features/*.md
7. docs/reference/** or archived product notes

Never implement lower-priority ideas that conflict with higher-priority files.
```

## CLAUDE.md Absolute Rules for Apps

```md
# CLAUDE.md — App Project Absolute Rules

## Source of Truth
Follow this priority when documents conflict:
1. CLAUDE.md
2. PRODUCT_SSoT.md
3. MVP_LOCK.md
4. DATA_API_CONTRACT.md
5. BUILD_PLAN.md
6. FEATURE_SPEC_INDEX.md and docs/05_features/*.md
7. archived notes, brainstorms, and reference docs

## MVP First
The current target is the MVP/prototype defined in MVP_LOCK.md. Do not implement future roadmap features, admin panels, billing, analytics, notifications, offline sync, AI features, integrations, multi-tenant support, or complex settings unless explicitly included.

## No Scope Invention
Do not add new roles, permissions, screens, database tables, API endpoints, background jobs, webhooks, payment flows, emails, notifications, or external integrations unless the active work packet explicitly asks for them.

## Data/API Contract
Do not change schemas, API shapes, auth rules, environment variables, or external service contracts without updating DATA_API_CONTRACT.md and calling out migration impact.

## Security and Privacy
Never commit secrets. Do not log secrets, tokens, passwords, private keys, or unnecessary PII. Treat auth, permissions, payment, and personal data changes as high risk.

## Work Packet Only
Implement only the current phase packet. Defer related improvements as TODO/change requests.

## UX States Required
For user-facing screens, include loading, empty, error, success, and permission-denied states when relevant.

## No Silent Refactor
Do not perform broad refactors outside the requested work packet. Propose them separately.

## Completion Rule
A feature is complete only when implementation, acceptance criteria, tests, and the primary user flow verification all pass.
```

## First Development Tasks

### Task 0 — Product Control Docs Extraction

Create implementation docs from PRD/Figma/notes:

```text
CLAUDE.md
PROJECT_INDEX.md
PRODUCT_SSoT.md
MVP_LOCK.md
DATA_API_CONTRACT.md
BUILD_PLAN.md
FEATURE_SPEC_INDEX.md
QA_CHECKLIST.md
```

Prompt:

```text
Read the existing app/product/Figma notes and create implementation control docs only.
Do not implement code.
Do not invent new features.
Separate MVP scope from future roadmap.
Identify missing data/API/auth decisions as open questions.
```

### Task 1 — Project Skeleton

Goal: runnable app shell.

Include:

- framework setup;
- routing;
- layout shell;
- design tokens/theme if available;
- basic CI/build/test scripts.

Exclude:

- real integrations;
- auth unless included in this task;
- database migrations unless explicitly part of setup;
- production deployment.

### Task 2 — Primary UX Flow Skeleton

Goal: prove the primary user journey with mock/local data.

Example:

```text
Landing/Login placeholder → Dashboard → Create item → View item → Edit/Delete → Empty/Error states
```

### Task 3 — Data/API Contract Implementation

Goal: implement minimal schemas, API routes, validation, and client data access matching `DATA_API_CONTRACT.md`.

### Task 4 — Real Feature Workflow

Goal: implement the most important feature end-to-end with tests.

### Task 5 — Hardening Pass

Goal: validation, error handling, accessibility, responsive states, and security/privacy checks.

## Work Packet Template

Use this for every Claude Code task:

```text
Task name:
[Feature/phase name]

Goal:
[Concrete user-visible outcome]

Must read:
- CLAUDE.md
- PRODUCT_SSoT.md
- MVP_LOCK.md
- DATA_API_CONTRACT.md
- BUILD_PLAN.md
- FEATURE_SPEC_INDEX.md
- [relevant feature spec]

May edit:
- [paths]

Must not edit:
- [paths]

Absolute no-go:
- Do not add features outside MVP_LOCK.md.
- Do not invent screens, roles, DB tables, API endpoints, integrations, background jobs, billing, or notifications.
- Do not change data/API/auth contracts without updating DATA_API_CONTRACT.md and reporting the impact.
- Do not commit or print secrets.
- Do not perform broad refactors.

Completion criteria:
- [acceptance criterion 1]
- [acceptance criterion 2]
- Tests pass: [command]
- Build passes: [command]
- Primary user path manually verified: [path]

First respond with an implementation plan only. Do not edit files yet.
```

After plan approval:

```text
Proceed with the approved plan only.
Stay inside the task scope.
Run build/tests when finished.
Report changed files, test result, contract changes, MVP_LOCK violations if any, and remaining TODOs.
```

## Feature Spec Template for Apps

```md
# F### — Feature Name

## Purpose
What user problem this solves.

## Users / Permissions
Who can use it and what they can access.

## User Flow
Step-by-step happy path and important alternates.

## UI Requirements
Screens, components, loading/empty/error/success states.

## Data Model
Entities, fields, validation, ownership, retention.

## API / Integration Contract
Endpoints, request/response shapes, errors, external dependencies.

## Edge Cases
Network failure, duplicate submit, unauthorized, no data, invalid input.

## Acceptance Criteria
Observable done conditions.

## Tests
Unit/integration/e2e/manual path.

## Non-Goals
What must not be implemented in this feature.
```

## Phase Completion Report Template

```md
## Phase Result

### Implemented
- ...

### Changed Files
- ...

### Data/API/Auth Contract Changes
- None / listed with migration impact

### Verification
- Build: pass/fail
- Tests: pass/fail
- Primary user flow: pass/fail

### MVP_LOCK Check
- No violations / violations listed

### Security/Privacy Check
- Secrets: none committed
- PII/logging: checked
- Permissions: checked

### Deferred TODOs
- ...

### Next Recommended Packet
- ...
```

## Practical Operating Loop

```text
1. Choose one phase or feature packet.
2. Provide the exact work packet.
3. Ask Claude Code for plan only.
4. Review for scope creep, contract changes, and security risk.
5. Approve implementation.
6. Run build/tests/e2e or manual user path.
7. Run a scope/security review.
8. Fix only blocking issues.
9. Update control docs and work log.
10. Move to next packet.
```

## Stop Signals

Pause and correct the agent if it says or does any of these:

- "I added an admin panel/settings area for completeness."
- "I created a new database table/API route not listed in the spec."
- "I added payments/analytics/notifications because apps usually need them."
- "I changed auth or permissions while implementing a UI task."
- "I used real external services before the integration contract was approved."

Correction:

```text
Stop. MVP_LOCK.md and DATA_API_CONTRACT.md are the boundaries. Remove or defer anything outside the active work packet. Keep it as TODO/change request only.
```

## Common Pitfalls

1. **No DATA_API_CONTRACT.** Apps drift when data and API shapes are implicit.
2. **Building auth/admin too early.** Only include them if MVP_LOCK requires them.
3. **Ignoring empty/error/loading states.** Apps feel broken without these.
4. **Letting Figma become scope.** Figma screens must still be filtered through MVP_LOCK.
5. **Silent schema changes.** Every schema/API change must be documented.
6. **Skipping security/privacy review.** Apps often touch real user data.
7. **Over-refactoring before the primary workflow works.** Prove the user job first.

## Verification Checklist

- [ ] Root control docs exist.
- [ ] `CLAUDE.md` has document priority and no-scope-invention rules.
- [ ] `MVP_LOCK.md` has explicit included and excluded lists.
- [ ] `DATA_API_CONTRACT.md` defines schemas, endpoints, permissions, and env vars.
- [ ] `BUILD_PLAN.md` is split into small user-visible phases.
- [ ] Each feature spec has purpose, permissions, flow, UI states, data/API, acceptance criteria, tests, and non-goals.
- [ ] Every Claude Code task starts with plan-only mode.
- [ ] Every completed phase runs build/test/user path verification.
- [ ] Every phase report includes contract-change and MVP_LOCK checks.

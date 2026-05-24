# Coding-Agent Routing Runbook

This runbook is for Codex when deciding how to manage Hermes software work.

## Current Doctrine

Atlas policy currently says:

```yaml
active_backend: gpt_native
fallback_backend: gpt_native
```

Gabriel has asked not to use Claude Code for now. Treat Codex/GPT-native work as the preferred coding route unless Gabriel explicitly changes that.

## Route Selection

Use Hermes/Codex native planning for:

- system strategy
- inventory
- runbooks
- docs
- policy design
- upgrade analysis
- operational checks

Use specialist coding roles for:

- multi-file changes
- tests or build changes
- frontend quality work
- backend architecture
- gateway/platform changes
- security-sensitive behavior
- refactors

## Planning And Delegation Routing

Hermes uses a steward-plus-planner pattern.

- `Hermes Steward` stays the primary user-facing coordinator in Discord.
- `Planning Architect` is a callable specialist for complex decomposition, routing, checkpoints, and handoff prompts.
- Specialist agents own bounded execution only after the plan names scope, allowed actions, forbidden actions, expected output, and verification.
- Kanban owns durable delegated work, approvals, blocked state, and later resumption.
- Shared context records meaningful architecture, routing, behavior, and verification changes.

Use Planning Architect when a task:

- spans multiple profiles, sessions, apps, services, or subsystems;
- needs parallel work packages or a staged session map;
- could affect live Discord routing, profile config, cron, services, memory, shared context, or Blue/GHL;
- needs a durable handoff prompt before another agent can execute safely.

Do not create a new planner profile unless the profile creation doctrine proves the why, owner, health checks, and retirement conditions. The default implementation is a specialist planning role/tool under Hermes Steward.

Planning output must include:

- goal and assumptions;
- required context;
- work packages with owner profile, scope, allowed actions, forbidden actions, expected output, and verification;
- dependencies and parallelizable work;
- approval boundaries;
- durable state and shared-context requirements;
- handoff prompt.

## Design-To-Code Routing

Use the Penpot design-to-code lane when a task asks for premium UI, concept
design, design-system work, reference screenshots, or high-confidence visual
handoff.

- Route concept/reference work to frontend-eng.
- Route data/API contract work to backend-eng.
- Route mixed app work through `coder`, which should split it into backend contract, frontend implementation, and visual QA when quality matters.
- Blue/GHL customer-facing behavior remains under Blue/GHL doctrine.
- Prefer Penpot or a reference screenshot before high-quality UI implementation.
- Use `docs/runbooks/penpot-design-to-code.md` for design-source handling.
- Use `docs/runbooks/frontend-visual-qa.md` before reporting meaningful UI work complete.

Default stack for new polished internal web UI:

- shadcn/Radix/Tailwind for implementation primitives;
- Playwright/browser screenshots for desktop and mobile proof;
- Storybook MCP only after reusable components exist;
- Penpot MCP read-only first, with no committed MCP keys or `userToken` URLs.

## Role Map

```text
Hermes Steward: overall coordinator
Planning Architect: complex decomposition, routing plans, checkpoints, handoffs
Runtime Operator: live service/process/log/config checks
Upgrade Analyst: upstream comparison and migration
Coding Architect: repo-aware refactors and architecture
Frontend Agent Manager: UI/product/frontend workflows
Backend Agent Manager: backend/runtime/tool/plugin workflows
Security Analyst: prompt injection, permissions, secrets, exploit surface
Quality Evaluator: tests, lint, release readiness, evidence
Knowledge Curator: current docs/research/indexing
```

## Verification Rule

Before reporting code work complete, Codex must know:

- what changed
- why it changed
- how it was tested
- what remains risky

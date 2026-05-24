# Hermes Planning Delegation Architecture - 2026-05-24

Status: implemented in local doctrine and agent files.

Purpose: install the steward-plus-planner pattern so Discord-facing Hermes can plan and delegate complex work without creating a competing command hierarchy or weakening Blue/GHL boundaries.

## Decision

Hermes should keep `Hermes Steward` as the primary user-facing coordinator. A new `Planning Architect` specialist handles complex decomposition, routing, checkpoints, and handoff prompts when the work is too broad or risky for direct execution.

The planner is not a standing profile by default. It is a specialist role/tool called by Hermes Steward. Standing profile creation remains gated by the profile creation doctrine.

## Installed Files

- `agents/planning-architect.md`
- `agents/hermes-steward.md`
- `agents/coding-architect.md`
- `agents/backend-agent-manager.md`
- `agents/frontend-agent-manager.md`
- `agents/quality-evaluator.md`
- `docs/runbooks/coding-agent-routing.md`
- `docs/runbooks/frontend-backend-agent-management.md`
- `docs/architecture/hermes-operating-doctrine-2026-05-16.md`
- `docs/architecture/hermes-runtime-flow-2026-05-16.md`
- `docs/architecture/hermes-spine/hermes-operating-spine-2026-05-17.md`
- `docs/architecture/hermes-spine/profile-and-agent-creation-doctrine-2026-05-17.md`
- `docs/refactor-plans/hermes-background-task-usage-doctrine-2026-05-20.md`
- `docs/architecture/blue-ghl-contracts/current-architecture-contract-2026-05-17.md`

## Operating Flow

1. Hermes Steward receives the Discord request and preserves Gabriel context.
2. If the task is complex, risky, cross-profile, multi-session, or Blue/GHL-adjacent, Hermes Steward calls Planning Architect.
3. Planning Architect returns a structured plan with work packages, owners, allowed actions, forbidden actions, verification, approval boundaries, durable-state needs, and a handoff prompt.
4. Hermes Steward dispatches bounded work to specialists, Kanban, cron, or a separate session.
5. Specialists return evidence.
6. Hermes Steward synthesizes, asks Gabriel for approvals when needed, and records shared context for meaningful routing or behavior changes.

## Blue/GHL Position

Blue can benefit from this planning pattern for large workflow, UI, policy, or integration work. The adoption is boundary-safe:

- Planning Architect may decompose Blue/GHL work.
- Blue remains the accountable GHL operator.
- No planner or generic specialist may send, book, suppress, mutate, or approve customer-facing work outside Blue doctrine.
- Durable Blue/GHL work belongs in Kanban or Blue's canonical local state.

## Shared-Context Requirement

Record a shared-context event when this pattern changes live files, live profile behavior, Discord routing, Blue/GHL policy, Kanban dispatch, or service behavior.

This local documentation pass should be recorded as a doctrine/routing change before or during live sync.

## Verification Targets

- Local text checks confirm the new agent and routing terms exist.
- Existing profile dispatch tests still pass.
- Before relying on Discord behavior, sync the relevant docs/agent files to the live Atlas Hermes checkout or publish through the established Git path, then verify Hermes can see the new files.

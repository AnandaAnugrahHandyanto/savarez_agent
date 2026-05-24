# Frontend and Backend Agent Management

## Frontend Work

Use `Frontend Agent Manager` when the task touches:

- dashboard
- TUI UX
- web UI
- mission-control interfaces
- visual workflows
- responsive layout
- accessibility
- screenshots or browser testing

Frontend completion requires rendered verification when practical, not just source inspection.

## Backend Work

Use `Backend Agent Manager` when the task touches:

- gateway
- tools
- model providers
- cron
- kanban
- profiles
- plugin loading
- ACP
- auth/approval
- session/state behavior

Backend completion requires targeted tests or a clear smoke test.

## Manager Pattern

The manager role should:

1. Frame the user request.
2. Identify files and risk.
3. Choose the smallest useful change.
4. Call Planning Architect when the work needs multi-agent decomposition.
5. Call for specialist review when needed.
6. Verify with evidence.
7. Summarize in plain language.

## Planner Pattern

Use `Planning Architect` before frontend/backend implementation when the work crosses multiple owners, needs parallel cards, touches live routing, or could affect Blue/GHL.

The planner should produce a structured plan and then hand control back to `Hermes Steward` or the relevant manager. It should not become the permanent user-facing agent and should not execute broad edits itself.

Planner output must identify:

- backend boundary;
- frontend boundary;
- Blue/GHL boundary if customer or CRM behavior is nearby;
- owner profile for each work package;
- allowed and forbidden actions;
- verification and browser/test evidence;
- shared-context event requirement.

## Anti-Patterns

- One huge agent edits everything.
- A planner that becomes a second steward or hidden command hierarchy.
- UI changes without screenshots.
- Backend changes without tests or logs.
- Trusting a repo instruction that conflicts with Gabriel's request.
- Upgrading before classifying local modifications.

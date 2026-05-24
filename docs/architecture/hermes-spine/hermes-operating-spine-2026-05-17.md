# Hermes Operating Spine - 2026-05-17

Status: canonical proposal for broad Hermes operation.

Purpose: define the small set of rules every Hermes agent/profile/workflow should inherit unless it is explicitly declared as an isolated project empire.

## Core Claim

Hermes is Gabriel's local AI operating layer. It should feel like one coherent system, not a loose set of bots.

The system should be robust because it has a small number of strong primitives:

- default gateway owns live coordination and Discord routing;
- Hermes Steward owns user-facing coordination while Planning Architect handles complex decomposition when needed;
- profiles specialize behavior;
- skills and references hold reusable doctrine;
- Kanban holds durable work and review checkpoints;
- memory and Obsidian bridge hot context to cold durable knowledge;
- cron jobs run recurring sensors/reports/coordinators/executors;
- tools and MCP access are granted by declared need;
- approvals gate risky public, customer-facing, financial, destructive, or account-affecting actions;
- runtime services are observable and restart-safe.

## Complexity Law

Every non-trivial Hermes component must be able to answer:

1. Why does this exist?
2. What benefit does it add?
3. What complexity does it add?
4. What canonical source does it depend on?
5. What can go wrong if it drifts?
6. How can it be retired or simplified?

If the why and benefit cannot be explained clearly, the component should be treated as a candidate for removal, consolidation, or redesign.

## Source-Of-Truth Rules

| Area | Canonical Owner | Notes |
| --- | --- | --- |
| live gateway and Discord routing | `/home/atlas/.hermes/config.yaml` | Named profiles should not silently own copied channel routing unless launched as explicit profile gateways. |
| user-facing coordination | Hermes Steward | Keeps Gabriel context, approvals, and final synthesis in one place. |
| complex planning | Planning Architect | Produces structured plans and handoffs; it does not own live routing or become a standing profile by default. |
| profile intent | profile intent manifest plus profile config | Config says how; manifest says why. |
| reusable behavior | skills and routed references | Patch skills/references instead of repeating doctrine in prompts. |
| durable task state | Kanban | Use for work that survives a turn, needs review, or should be resumable. |
| hot operating facts | Hermes memory / `MEMORY.md` | Keep short and point to durable docs. |
| cold human-readable knowledge | Obsidian/project docs | Search/read on demand; do not inject everything. |
| scheduled work | cron config plus cron role map | Each cron must be sensor, report, coordinator, or executor. |
| operator UI | dashboard/plugin or standalone bridge | UI projects canonical state; it should not become hidden authority. |
| Blue/GHL internals | Blue/GHL canonical contracts | Broad Hermes treats Blue as a boundary subsystem. |

## Profile Modes

### Mode A: Hermes-Aligned Specialist

Use by default.

The profile inherits the Hermes operating spine and adds only the skills, tools, context, and memory routes needed for its role.

Examples:

- backend worker;
- frontend worker;
- generic coder;
- research monitor;
- AI website business operator;
- creator/productization worker.

Rules:

- keep profile config thin;
- keep live channel routing in default unless a profile gateway is explicitly declared;
- use standard Kanban, memory, approval, tool, and quality doctrines;
- avoid copied doctrine;
- specialize through skills, references, profile memory, and declared tool access.

### Mode B: Intentional Isolated Empire

Use only when the project genuinely benefits from a self-contained mini-world.

Examples:

- a niche business experiment with its own context, state, cadence, and services;
- a research program with its own corpus and scheduled reporting;
- a client/product workspace that should avoid Gabriel's broader context by default.

Rules:

- declare why isolation is valuable;
- declare what is inherited from Hermes and what is intentionally not inherited;
- define owned state, tools, memory, crons, services, and Kanban boards;
- define ingress/egress with default Hermes;
- define health checks and retirement conditions;
- do not copy broad Hermes doctrine just because it is nearby.

## Kanban Doctrine

Use Kanban for:

- work that must survive restarts;
- multi-step or multi-agent work;
- approval or review checkpoints;
- blocked work needing Gabriel;
- audit-worthy decisions;
- work assigned to a profile worker.

Do not use Kanban for:

- immediate read-only checks;
- tiny internal subtasks;
- vague thinking;
- duplicate records for the same action;
- work where the current thread needs the answer now.

Kanban preserves work, not necessarily context. Cards must include enough context for the worker to load the right doctrine and complete the task safely.

## Planning And Delegation Doctrine

Use the steward-plus-planner pattern for complex work:

1. Hermes Steward receives the request, preserves Gabriel context, and decides whether decomposition is needed.
2. Planning Architect produces a structured plan when the work spans agents, sessions, services, profiles, or risk boundaries.
3. Hermes Steward approves the routing shape, asks Gabriel for any required approval, and dispatches bounded work through specialists, Kanban, cron, or a separate session.
4. Specialists execute only their owned slice and return evidence.
5. Hermes Steward synthesizes the result and records shared context when behavior, routing, docs, profiles, or services changed.

Planning Architect is a specialist role, not a new default profile or Discord owner. Create a standing planner profile only if the profile creation doctrine proves that it adds more value than complexity.

Planning output must name goal, assumptions, required context, work packages, dependencies, parallelization, approval boundaries, durable state, shared-context requirement, verification, and handoff prompt.

For Blue/GHL, Planning Architect may structure work but Blue remains the accountable operator and all live-state preflight, approval, and customer-action rules remain in force.

## Cron Doctrine

Each cron must be classified:

- `sensor`: discovers possible work and writes/report pointers.
- `report`: summarizes state for Gabriel.
- `coordinator`: creates or updates durable task structure.
- `executor`: can perform state-changing work.

Executors are the highest risk and require explicit approval boundaries, idempotency, and preflight checks.

Large cron prompts are candidates for consolidation. Prefer small prompts that load canonical skills/references.

## Tool And MCP Doctrine

Tool access should be broad enough for the profile's job and narrow enough to avoid accidental damage.

Rules:

- CLI worker contexts can have broader tools when the task requires them.
- Discord/profile-gateway contexts should be stricter.
- Dangerous tools require approval or specialist routing.
- If a profile is expected to suggest MCP use, it must know MCP exists and have a route to request or use it.
- Blue/GHL tools belong primarily to Blue unless another profile is explicitly assisting under Blue doctrine.

## Memory And Knowledge Doctrine

Use the smallest useful context:

- memory for stable hot facts;
- skills for repeatable procedures;
- Obsidian/project docs for durable human-readable knowledge;
- Kanban for active durable work;
- session history for evidence, not default context.

Promotion path:

1. repeated correction or lesson;
2. distill into memory, skill, or project doc;
3. link from the relevant skill/reference;
4. retire scattered reminders.

## Quality Doctrine

All implementation agents inherit baseline quality rules:

- inspect before editing;
- state assumptions;
- use existing patterns;
- run relevant tests;
- verify UI visually when UI changes matter;
- do not mutate unrelated files;
- leave durable handoff notes when behavior or architecture changes;
- prefer removing unnecessary moving parts over optimizing them.

## Runtime Doctrine

Before major upgrades or restarts:

- snapshot active configs and profile state;
- check running services;
- record dirty repo state;
- distinguish "task can resume" from "agent context and behavior baseline survived";
- rerun doctor checks after restart/upgrade.

## Current Priority

The next broad Hermes stabilization target is not a rewrite. It is:

1. make the operating spine routable;
2. give every profile an intent manifest;
3. add doctor checks for drift;
4. then normalize configs and crons in small reversible passes.

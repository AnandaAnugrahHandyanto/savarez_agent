# Hermes Profile And Agent Creation Doctrine - 2026-05-17

Status: canonical proposal for creating or changing Hermes profiles/agents.

Purpose: make new agents useful without letting accidental complexity multiply.

## Rule

Do not create a new profile, agent, cron, service, board, mirror, or tool route just because it fits the plan.

Create it only when the why is clear and the benefit is greater than the complexity it adds.

## Required Why Contract

Every new or materially changed profile/agent must define:

| Field | Required Answer |
| --- | --- |
| `name` | Stable profile/agent name. |
| `mode` | `hermes_aligned_specialist` or `intentional_isolated_empire`. |
| `purpose` | One clear sentence. |
| `why_exists` | Why this should exist instead of using an existing profile. |
| `benefit` | What capability or focus it adds. |
| `complexity_cost` | What moving parts, cognitive load, or risk it adds. |
| `owner` | Who or what owns it operationally. |
| `inherits` | What it inherits from the Hermes operating spine. |
| `does_not_inherit` | What it deliberately excludes. |
| `skills` | Required skills and whether they are canonical or generated mirrors. |
| `tools` | Required toolsets/MCP access by context: CLI, Discord, cron, webhook. |
| `memory_context` | Memory, Obsidian, project docs, or state it should use. |
| `kanban_policy` | When it creates/uses cards and which boards it owns. |
| `cron_policy` | Any scheduled work and its role: sensor/report/coordinator/executor. |
| `approval_boundaries` | Actions that need Gabriel approval. |
| `runtime_services` | Services/timers it owns, if any. |
| `state_owned` | Files/databases/mirrors it owns. |
| `interfaces` | How Gabriel or other agents interact with it. |
| `health_checks` | How to know it is working. |
| `retirement_conditions` | When to merge, archive, or delete it. |

## Mode A: Hermes-Aligned Specialist

Default choice.

Use when a profile needs a role, not a separate world.

Examples:

- backend implementation worker;
- frontend/product UI worker;
- generic coder;
- planning specialist role when a task needs structured decomposition but not a standing profile;
- research update agent;
- AI website business operator;
- creator/content operator.

Required standards:

- inherit the Hermes operating spine;
- keep config as a thin overlay;
- use default gateway routing unless explicitly launched as a gateway;
- use shared Kanban/task doctrine;
- use shared memory promotion doctrine;
- use shared approval and tool safety doctrine;
- add only role-specific skills, references, memory routes, and tool access.

Avoid:

- copying global channel prompts into profile configs;
- embedding broad doctrine in crons;
- creating new state files without a source-of-truth declaration;
- adding a service when a script or existing dashboard/plugin would do.

## Mode B: Intentional Isolated Empire

Allowed, but must be explicit.

Use when a profile/project really needs its own mini-world.

Good reasons:

- the project has a different context universe;
- broad Gabriel/Hermes context would distract or degrade quality;
- it needs its own cadence, memory, boards, UI, state, or services;
- it may later become a separate product or business process;
- it has a clear boundary with default Hermes.

Bad reasons:

- avoiding the effort of routing through existing skills;
- copying a working subsystem because it is convenient;
- adding a profile for a one-off task;
- preserving a stale experiment;
- hiding uncertainty in more moving parts.

Required extra fields:

- why isolation is valuable;
- what context is intentionally excluded;
- what state must never leak back automatically;
- what minimal bridge back to default Hermes exists;
- how Gabriel sees status and intervenes;
- how the empire can be collapsed back into Hermes if it stops justifying itself.

## Decision Test

Before creating a profile/agent:

1. Can an existing profile do this with one added skill/reference?
2. Can this be a Kanban workflow instead of a profile?
3. Can this be a project doc/runbook instead of a new agent?
4. Can this be a script-only cron instead of an LLM cron?
5. Can this be a dashboard/plugin view instead of a new service?
6. What breaks if this component is deleted?
7. What becomes simpler if this component is deleted?

If the answer points to reuse, do not create the new profile.

Planner-specific rule: `Planning Architect` should start as a specialist role/tool under Hermes Steward. Do not create a standing planner profile just because complex tasks exist. Create one only if recurring evidence shows that a separate profile improves planning quality more than it adds routing, eval, prompt, and ownership complexity.

## Creation Steps

1. Write the why contract.
2. Choose profile mode.
3. Declare inherited baseline and intentional deviations.
4. Add or route skills/references.
5. Add only necessary tool access.
6. Define Kanban and memory behavior.
7. Define approval boundaries.
8. Add health checks.
9. Run the Hermes-wide doctor.
10. Add the profile to the manifest only after the above is clear.

## Change Control

Changing a profile from Hermes-aligned to isolated empire is a design decision.

Changing an isolated empire back into a Hermes-aligned specialist is also a design decision.

Both changes should update:

- profile intent manifest;
- profile config or overlay;
- relevant skills/references;
- Kanban board ownership;
- cron/service ownership;
- health checks;
- retirement notes.

## Minimal Manifest Example

```json
{
  "name": "research-ai-safety",
  "mode": "hermes_aligned_specialist",
  "purpose": "Track and summarize AI safety research for Gabriel.",
  "why_exists": "Recurring research synthesis needs different source-quality doctrine than general coding work.",
  "benefit": "Keeps Gabriel updated without manual scanning.",
  "complexity_cost": "Adds one profile overlay, one research runbook, and one report cron.",
  "owner": "default Hermes gateway",
  "inherits": ["operating-spine", "memory-doctrine", "kanban-doctrine", "approval-doctrine"],
  "does_not_inherit": ["Blue/GHL customer-action authority"],
  "skills": ["hermes-agent", "kanban-worker", "research/arxiv", "research-paper-writing"],
  "tools": {
    "cli": ["web", "file", "memory", "kanban", "skills"],
    "discord": ["hermes-discord", "no_mcp", "kanban"]
  },
  "memory_context": ["Obsidian research folder", "project docs"],
  "kanban_policy": "Create cards only for durable research questions or Gabriel review.",
  "cron_policy": "Report cron only; no executor cron.",
  "approval_boundaries": ["No public posts or account actions without approval."],
  "runtime_services": [],
  "state_owned": [],
  "interfaces": ["Discord report", "Obsidian summary"],
  "health_checks": ["profile show works", "required skills present", "cron classified"],
  "retirement_conditions": "Archive if no useful reports for 30 days or replaced by another research profile."
}
```

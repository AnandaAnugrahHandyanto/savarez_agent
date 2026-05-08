# Hermes AI Office — Smallville / Generative Agents Audit

Last updated: 2026-05-08 11:32 KST
Status: Stage 1 research artifact. Documentation-only; no code cloned, vendored, installed, or modified.

## Sources inspected

- Paper: https://arxiv.org/abs/2304.03442
- ACM page: https://dl.acm.org/doi/fullHtml/10.1145/3586183.3606763
- Original repository: https://github.com/joonspk-research/generative_agents
- Related Smallville implementation: https://github.com/nmatter1/smallville
- Representative original files inspected read-only:
  - `reverie/backend_server/persona/persona.py`
  - `reverie/backend_server/persona/memory_structures/associative_memory.py`
  - `reverie/backend_server/persona/cognitive_modules/plan.py`
  - `reverie/backend_server/persona/cognitive_modules/reflect.py`
- Representative `nmatter1/smallville` dashboard files inspected read-only:
  - `dashboard/lib/smallville.ts`
  - `dashboard/app/page.tsx`

## What it is

The Stanford/Google Generative Agents work introduced believable LLM-driven characters in a simulated town (“Smallville”). It focuses on agents that observe, remember, reflect, plan, and act in a game-like environment.

This is conceptually relevant but not a direct product match. Hermes AI Office is an operational observability dashboard, not a synthetic social simulation.

## License and reuse posture

- `joonspk-research/generative_agents`: Apache-2.0.
- `nmatter1/smallville`: MIT.

Both licenses are generally permissive, but direct code reuse is not recommended for MVP because the architecture and product goal differ.

## Core concepts worth adapting conceptually

### Memory stream

Original code contains an associative memory structure for event/thought/chat nodes. For Hermes, the equivalent is not a synthetic NPC memory stream; it is a real event log:

- Kanban task events,
- cron run history,
- gateway message metadata,
- session/tool events,
- STATUS/NEXT handoff docs.

### Reflection

Generative Agents use reflection to synthesize higher-level thoughts from memories. For Hermes, this could later become:

- short task-event summaries,
- blocked-work explanations,
- daily “what happened in the office” digest,
- speech bubbles based on real task events.

This should be deferred because LLM-generated summaries can fabricate or obscure operational truth.

### Planning

Generative Agents plan daily behavior. Hermes already has real planning mechanisms:

- user instructions,
- `/goal`,
- Kanban tasks,
- cron jobs,
- delegated workers.

AI Office should visualize those existing plans, not create an independent planning engine.

### Spatial social metaphor

The town/office metaphor is useful for readability and emotional salience. It can make multi-agent work feel understandable, but must be subordinate to real status data.

## What not to adopt

- Do not build a synthetic autonomous society as the MVP.
- Do not let characters invent work or conversations.
- Do not model “beliefs” or hidden intentions that do not exist in Hermes state.
- Do not replace Kanban/cron/session truth with LLM narration.

## Related `nmatter1/smallville` observations

The related Smallville project includes a dashboard that fetches agent/location data from HTTP endpoints such as:

- `GET http://localhost:8080/agents`
- `GET http://localhost:8080/info`
- `GET http://localhost:8080/locations`
- `POST http://localhost:8080/agents/{agent}/ask`

This reinforces a useful pattern: separate simulation/state backend from UI dashboard. For Hermes, the backend should be Hermes' own dashboard API and real state adapters.

## Hermes adoption matrix

| Area | Direct reuse? | Adapt conceptually? | Notes |
|---|---:|---:|---|
| Memory/reflection/planning code | No | Partially | Use only as later summarization inspiration. |
| Spatial town metaphor | No | Yes | Useful UX inspiration for rooms/agents. |
| Dashboard/API separation | No | Yes | Backend state feeding UI is relevant. |
| Synthetic social simulation | No | No | Explicitly out of MVP scope. |
| Speech bubbles | No | Later | Must be grounded in real events. |

## MVP implications for Hermes

- Use Smallville as narrative/UX inspiration only.
- Read-only MVP should show real operational state, not simulated inner lives.
- LLM-generated speech bubbles should be a post-MVP feature and must cite underlying event IDs or task logs.

## Recommendation

Treat Smallville/Generative Agents as a mental-model reference for making agents feel legible, not as an implementation dependency. The safest first product remains Hermes-native read-only observability.

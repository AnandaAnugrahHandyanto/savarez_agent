# Hermes AI Office — STAGE MAP

This is the working stage map for the Hermes AI Office / Pixel-Agent Dashboard project.

## Stage 0 — Project charter and operating protocol

Status: mostly complete / maintain as project evolves.

Purpose:
- Establish project scope, context preservation, approval gates, and planning workflow.

Key outputs:
- `STATUS.md`
- `NEXT.md`
- `DECISIONS.md`
- `OPEN-QUESTIONS.md`
- `STAGE-MAP.md`
- Suggested `/goal` wording

Completion criteria:
- User accepts initial stage map.
- Handoff docs exist.
- Next stage is clear.

`/goal` usage:
- Use `/goal` as a session-level operating contract at the start of bounded stage work.
- Keep durable state in `STATUS.md`, `NEXT.md`, decision/open-question logs, and stage outputs.
- Do not treat `/goal` as approval for code/config/service/Kanban/cron mutations.
- Preferred use windows: Stage 3–5 planning/design sessions; Stage 6+ only after explicit implementation-slice approval.

## Stage 1 — Research and reference audit

Status: drafted.

Purpose:
- Study Pixel Agents, standalone/Codex forks, Smallville/Generative Agents, and broader agent observability patterns.

Medium tasks:

1. Pixel Agents original repo audit.
2. Pixel Agents standalone fork audit.
3. Pixel Agents Codex fork audit.
4. Smallville / Generative Agents audit.
5. Agent observability pattern survey.
6. Research synthesis and adopt/reject matrix.

Expected outputs:
- `research/pixel-agents-audit.md`
- `research/pixel-agents-standalone-audit.md`
- `research/pixel-agents-codex-audit.md`
- `research/smallville-generative-agents-audit.md`
- `research/agent-observability-patterns.md`
- `research/synthesis.md`

Implementation allowed:
- No.

## Stage 2 — Hermes data-source audit

Status: drafted.

Purpose:
- Identify what data Hermes already exposes and what must be added for AI Office.

Medium tasks:

1. Dashboard architecture audit.
2. Kanban data model and event audit.
3. Cron data model audit.
4. Gateway/Telegram topic routing audit.
5. Session/provenance audit.
6. Current WSL state snapshot.

Expected outputs:
- `audit/dashboard-architecture.md`
- `audit/kanban-data-model.md`
- `audit/cron-data-model.md`
- `audit/telegram-topic-routing.md`
- `audit/session-provenance.md`
- `audit/current-wsl-state-snapshot.md`

Implementation allowed:
- No. Read-only inspection only.

## Stage 3 — Product requirements and information architecture

Status: drafted.

Purpose:
- Define user stories, screens, UX priorities, `OfficeState`, redaction boundaries, mutation boundaries, and MVP acceptance criteria.

Medium tasks:

1. Personas and use cases.
2. User stories.
3. Information architecture.
4. `OfficeState` object model and field-level redaction boundaries.
5. MVP acceptance criteria.
6. Non-goals/deferred features and mutation boundary.
7. User review.

Expected outputs:
- `product/user-stories.md`
- `architecture/office-state-model.md`
- `product/information-architecture.md`
- `product/non-goals-and-mutation-boundary.md`
- `product/mvp-acceptance-criteria.md`

Implementation allowed:
- No.

## Stage 4 — Provenance and routing design

Status: drafted.

Purpose:
- Design how tasks remember source/delivery information, especially Telegram topic provenance.

Medium tasks:

1. Topic registry spec.
2. Task source metadata spec.
3. Task delivery metadata spec.
4. Backfill strategy.
5. Privacy/security classification.
6. Storage location decision.

Expected outputs:
- `design/topic-registry-spec.md`
- `design/task-provenance-metadata.md`
- `design/provenance-backfill.md`
- `design/privacy-security.md`

Implementation allowed:
- No, unless explicitly approved after design review.

## Stage 5 — Technical architecture design

Status: next.

Purpose:
- Design backend APIs, data adapters, frontend components, tests, and rollout path.

Medium tasks:

1. Backend API spec.
2. Data adapter design.
3. Frontend component design.
4. Pixel renderer adapter design.
5. Test plan.
6. Rollout plan.

Expected outputs:
- `architecture/backend-api.md`
- `architecture/data-adapters.md`
- `architecture/frontend-components.md`
- `architecture/test-plan.md`
- `architecture/rollout-plan.md`
- `architecture/pixel-renderer-adapter.md` (optional/deferred adapter contract only)

Implementation allowed:
- No.

## Stage 6 — Read-only dashboard MVP implementation

Status: not started / requires explicit approval.

Purpose:
- Implement a useful non-pixel observability dashboard first.

Medium tasks:

1. Backend office state DTOs.
2. Kanban read endpoints.
3. Cron read endpoints.
4. Topic registry read endpoint.
5. Basic Office page.
6. Task inspector drawer.
7. Focused tests and local smoke verification.

Implementation allowed:
- Only after explicit approval.

## Stage 7 — Provenance capture implementation

Status: not started / requires explicit approval.

Purpose:
- Store source/delivery metadata for future tasks and Telegram-originated work.

Medium tasks:

1. Storage/migration implementation.
2. Gateway-origin task capture.
3. Cron-origin task/delivery capture.
4. Existing task backfill.
5. Tests and verification.

Implementation allowed:
- Only after separate explicit approval.

## Stage 8 — Pixel office visualization MVP

Status: not started / requires explicit approval.

Purpose:
- Add game-like spatial representation once data is reliable.

Medium tasks:

1. Renderer decision.
2. Visual mapping spec.
3. Static pixel prototype.
4. Live data binding.
5. Inspector integration.

Implementation allowed:
- Only after explicit approval.

## Stage 9 — Browser interaction and control layer

Status: not started / requires explicit approval and security review.

Purpose:
- Add safe browser-side control actions.

Candidate actions:
- Subscribe/unsubscribe to task updates.
- Reclaim/reassign/retry tasks.
- Run cron job manually.
- Mark/block/unblock tasks.

Implementation allowed:
- Only after explicit approval and security review.

## Stage 10 — Multi-device / NAS / Obsidian integration

Status: not started / requires explicit approval.

Purpose:
- Surface shared handoff context read-only without making runtime depend on sync.

Candidate features:
- `STATUS.md` / `NEXT.md` panel.
- START HERE handoff link.
- Shared ledger health indicator.
- Local device role display.

Implementation allowed:
- Only after explicit approval.

## Stage 11 — Polish and long-term evolution

Status: not started.

Purpose:
- Improve visual quality, customization, performance, and extensibility.

Candidate features:
- Profile-specific character skins.
- Timeline replay.
- Korean-friendly office labels.
- LLM-generated event summaries.
- Mobile-friendly view.
- Tailscale-only remote mode.
- Plugin rooms.

Implementation allowed:
- Only after MVP and review.

---

# Approval gates

Explicit user approval is required before:

1. Creating/mutating Kanban boards or tasks.
2. Modifying dashboard/backend/frontend code.
3. Adding dependencies.
4. Changing gateway, cron, systemd, startup scripts, or config.
5. Restarting services.
6. Exposing dashboard beyond localhost.
7. Adding browser-side mutation actions.
8. Writing to NAS/Obsidian shared ledger.
9. Saving or patching memory/skills for this project.

# Current recommended next step

Proceed to Stage 5 technical architecture design. Create documentation-only notes under `docs/ai-office/architecture/` for protected OfficeState API/auth placement, data adapters, frontend components, redaction/test plan, and rollout plan. Do not implement code or mutate runtime state without explicit approval.

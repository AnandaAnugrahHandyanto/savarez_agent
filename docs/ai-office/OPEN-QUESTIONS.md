# Hermes AI Office — OPEN QUESTIONS

This file tracks unresolved questions for the Hermes AI Office / Pixel-Agent Dashboard project.

## High-priority questions

### Q001 — Final product name

Options:
- Hermes AI Office
- Hermes Ops Office
- Hermes Agent Studio
- Hermes Control Room

Current default: Hermes AI Office.

Needed decision:
- Choose a stable name before user-facing docs/UI are written.

### Q002 — Dashboard-first or pixel-first emphasis

Question:
- After research, should MVP optimize for operational usefulness first or game-like visualization first?

Current decision:
- Resolved for planning purposes by D003: operational/read-only dashboard first, pixel layer second.

Follow-up:
- Revisit only after Stage 5 if the user wants to accelerate Stage 8 pixel work.

### Q003 — Where should Telegram topic registry live?

Options:
- `~/.hermes/config.yaml` profile config
- dashboard-specific config section
- Obsidian/NAS ledger note read-only mirror
- new Hermes topic registry file under Hermes home
- hardcoded local memory only, not recommended

Current known mapping:
- Telegram Hermes Hub: `-1003775710032`
- `00-운영실`: thread `2`
- `70-자동화`: thread `11`

Needed decision:
- Choose storage location and editing workflow.

### Q004 — Where should task provenance metadata live?

Options:
- existing Kanban task metadata field if available
- new Kanban metadata table
- new JSON column/migration
- external provenance table keyed by task id

Current Stage 3 position:
- Stage 2 found no first-class Kanban task source columns for Telegram/session provenance. Stage 4 should choose between a new Kanban metadata table, external provenance table, or computed projection.

Needed decision:
- Choose storage and migration/backfill strategy before Stage 5 technical architecture.

### Q005 — How much Telegram source information is safe to show?

Fields to classify:
- platform
- chat id
- thread id
- topic name
- message id
- sender display name
- message text snippet
- session id

Current Stage 4 recommendation:
- Show topic label/purpose from the registry when available.
- Localhost mode may show internal chat/thread ids if clearly labeled; remote mode should hash/hide ids or show label-only after security review.
- Avoid raw message text snippets in MVP.

### Q006 — Should this project get its own Kanban board?

Potential board:
- `hermes-ai-office`

Pros:
- Durable task tracking.
- Good dogfooding for the future AI Office view.

Cons:
- Board creation is a mutation.
- May be premature before Stage 1 research.

Current recommendation:
- Create after Stage 1 or after user explicitly approves project-board tracking.

### Q007 — Which renderer should pixel MVP use?

Options:
- CSS/SVG/pixel sprites
- PixiJS
- Phaser
- Custom Canvas

Current recommendation:
- Start with CSS/SVG or PixiJS.
- Avoid Phaser until interaction complexity requires it.

### Q008 — Should Pixel Agents code be reused or only studied?

Question:
- Is direct code reuse worth the dependency and architecture mismatch?

Current recommendation:
- Study first. Prefer Hermes-native implementation unless audit shows a clearly reusable module.

### Q009 — How should cron failures become visible?

Options:
- Display cron job status only.
- Create incident tasks when cron fails.
- Send Telegram topic alert only.
- All of the above eventually.

Current recommendation:
- MVP displays cron status read-only.
- Incident task creation is deferred.

### Q010 — How should AI Office integrate with Obsidian/NAS handoff?

Question:
- Should dashboard show `STATUS.md` / `NEXT.md` / START HERE notes?

Current recommendation:
- Later read-only panel only.
- No startup dependency and no write sync.

### Q011 — Where should OfficeState API live?

Question:
- Should future `OfficeState` endpoints live under protected built-in dashboard routes such as `/api/office/...`, or under a dashboard plugin route?

Context:
- Stage 2 found `/api/plugins/` HTTP routes are skipped by dashboard auth middleware, while the Kanban WebSocket requires a token.

Current Stage 4 recommendation:
- Prefer protected built-in `/api/office/...` routes or explicitly fix plugin auth before exposing new office state.

Needed decision:
- Decide endpoint/auth placement in Stage 5.

### Q012 — How should source identifier display vary by mode?

Question:
- In localhost mode, should chat ids/thread ids/session ids be shown directly, hashed, or label-only? What changes if remote/Tailscale/public access is ever approved?

Current recommendation:
- Localhost MVP may show internal ids when useful, clearly labeled internal. Remote mode should prefer labels/hashes and require a security review.

Needed decision:
- Add field-level display policy in Stage 4 privacy/security design.

### Q013 — Should session titles/previews be included in AI Office MVP?

Question:
- Session metadata is useful for provenance, but titles/previews can leak user prompts.

Current recommendation:
- Include source, session id, timestamps, model/provider, and counts first. Include title/preview only after a redaction policy and tests exist.

Needed decision:
- Decide in Stage 4/5 whether title/preview is safe enough for MVP.

### Q014 — How should data-source failures affect OfficeState?

Question:
- Should source failures block the entire page, or render as partial state with per-source warnings?

Current recommendation:
- Render partial state with explicit `data_sources[].status`; never treat unavailable sources as zero.

Needed decision:
- Define exact failure semantics in Stage 5 technical architecture.


### Q015 — Should provenance storage be centralized or per-source?

Question:
- Should `office_provenance` live in a profile-level store keyed across sessions/Kanban/cron, or in per-source side tables/files?

Current Stage 4 recommendation:
- Keep a separate provenance layer/projection rather than overloading task body/comment/result fields. Stage 5 should choose profile-level DB/file vs per-board/session side tables.

Needed decision:
- Pick the physical storage and migration approach before Stage 6/7 implementation planning.

### Q016 — Should Stage 6 compute-only backfill read seed registries?

Question:
- Should the first read-only MVP compute unknown/derived provenance entirely in memory from current sources, or also read a user-reviewed topic/provenance seed registry?

Current Stage 4 recommendation:
- A read-only seed registry is acceptable if Stage 5 defines storage/auth/redaction and no write/edit UI is included. Otherwise compute-only and show unknowns.

Needed decision:
- Decide before Stage 6 API implementation.

### Q017 — Which redaction report is user-visible?

Question:
- Should `OfficeState.redactions` be visible in the UI, included only in API/debug payloads, or both?

Current Stage 4 recommendation:
- Include a lightweight report in the DTO and show at least redaction/omission categories in an inspector/debug area so privacy behavior is testable.

Needed decision:
- Decide in Stage 5 frontend/API design.

# Hermes Desktop Agents/Projects/Multi-Gateway Implementation Plan

> **For Hermes:** Use dependency-gated Kanban continuation. First slice must be verified before later implementation starts.

**Goal:** Turn Hermes Desktop from a session/workspace viewer into a control surface for gateways, agents, projects, Telegram topics/chats, and multiple connected Hermes Dashboard backends.

**Architecture:** Add stable backend inventory APIs first, then update Desktop to render typed control-surface entities above raw sessions. Multi-gateway support should be introduced as a connection registry with backwards-compatible migration from the current single remote connection. Read-only aggregation comes before cross-gateway send/routing.

**Tech Stack:** Python FastAPI-style Dashboard handlers in `hermes_cli/web_server.py`, gateway session/config helpers under `gateway/`, Electron main-process connection config in `apps/desktop/electron/main.cjs`, React/Nanostores renderer in `apps/desktop/src/`, Vitest + pytest.

## Current status — 2026-06-04

The implementation chain has passed all planned Kanban gates. Keep this section as the handoff anchor until the project gets a dedicated Telegram topic.

- `t_bcac4710` — **done**: connection registry v0, commit `f01bfcd82`.
- `t_d30feb01` — **done**: QA review of connection registry; approved continuation.
- `t_4b93caf4` — **done**: Dashboard entity APIs `/api/agents`, `/api/conversations`, `/api/projects`, commit `fe620aae2`.
- `t_151bca30` — **done**: one-gateway Agents/Projects/Chats/Workspaces sidebar, commit `832eee500` plus follow-up repairs.
- `t_5b5f2368` — **done**: multi-gateway read-only aggregation, commit `1a4412bf5` plus review-blocker repairs.
- `t_a1139bf4` — **done**: selected-gateway routing for chat actions, commit `fc7776320` plus review repairs.
- `t_c9f2ad7a` — **done**: design review path; changes were repaired and re-reviewed.
- `t_fcb03af9` — **done**: final QA; completed `2026-06-04 00:11`.

Current repo branch is `feat/desktop-control-surface-multigateway`. Desktop implementation evidence is on that branch up through `53ffcae9c`; later commits on the same branch may include unrelated runtime/ops hotfixes.

Topic handoff requested: create a dedicated Telegram project topic in `Dolly Main Projects` named `▸ Hermes Desktop – Control Surface`, then write the resulting `telegram:<chat_id>:<thread_id>` target back to this plan, the knowledge page `projects/hermes-desktop-control-surface.md`, and any remaining follow-up/closeout task metadata.

---

## Source-of-truth model

- **Gateway connection:** transport to one Hermes Dashboard backend, e.g. WSL `http://100.118.95.115:9120` or Mac-local `http://127.0.0.1:9120`.
- **Agent:** live Hermes profile/gateway actor, e.g. `default`, `dollyops`, `dollydesign`, `dollyprivate`, later Donald/Mac if exposed.
- **Conversation:** platform DM/group/topic, e.g. `telegram:<chat_id>` or `telegram:<chat_id>:<thread_id>`.
- **Project:** durable work object, usually backed by a Telegram topic plus `/home/openclaw/knowledge/projects/*.md`.
- **Session:** historical run/conversation record. Sessions attach to gateway, agent/profile where known, conversation/topic, project where known, workspace/cwd fallback.

## Acceptance gates

1. Backwards compatible: existing single-remote `connection.json` still works.
2. Dashboard remains reachable over `/api/status` and `/api/ws` with stable token.
3. No raw tokens in logs/API/UI. Token values stay encrypted/preview-only.
4. Entity IDs are namespaced by gateway before any multi-gateway aggregation.
5. UI does not regress current chat/session loading.
6. Tests cover migration, endpoint shape, grouping, and at least one multi-gateway read-only aggregation case before write/send support.

---

## Task chain

### Task 1: Connection Registry v0, backward-compatible single active gateway

**Objective:** Replace the implicit single remote config with a typed connection registry while preserving the current UX and behavior.

**Files:**
- Modify: `apps/desktop/electron/main.cjs`
- Modify: `apps/desktop/src/global.d.ts`
- Modify: `apps/desktop/src/app/settings/gateway-settings.tsx`
- Test: existing or new desktop/electron config tests if present; otherwise add focused unit helpers around config coercion/migration.

**Implementation notes:**
- Add config shape:
  - `schemaVersion: 2`
  - `activeConnectionId`
  - `connections[]`
- Each connection:
  - `id`
  - `name`
  - `mode: local | remote`
  - `baseUrl`
  - encrypted `token`
  - `kind: hermes-dashboard`
- Migrate old shape:
  - `{ mode: 'remote', remote: { url, token } }` -> one connection `wsl-main` or `remote-1`.
  - `{ mode: 'local' }` -> one local connection.
- Keep only one active connection at runtime in Task 1.

**Verification:**
- Unit test old config migration.
- Unit test token preview still redacts.
- `cd apps/desktop && npm run type-check`
- `cd apps/desktop && npm run build`

**Commit:**
`feat(desktop): add connection registry config`

### Task 1 review: Verify registry migration and no token leak

**Objective:** Review Task 1 before any project/agent UI work starts.

**Reviewer checks:**
- Old `connection.json` still loads.
- Current remote backend can still connect to `/api/status` and `/api/ws`.
- No raw token appears in renderer state/log output/API payloads.
- Build/typecheck/test receipts included.

### Task 2: Backend entity APIs, agents/conversations/projects

**Objective:** Expose read-only Dashboard APIs that model live agents, Telegram conversations/topics, and durable projects separately from sessions.

**Files:**
- Modify: `hermes_cli/web_server.py`
- Modify or add helpers under `gateway/` if needed
- Test: `tests/hermes_cli/test_web_server.py`, `tests/gateway/test_channel_directory.py`

**Endpoints:**
- `GET /api/agents`
- `GET /api/conversations`
- `GET /api/projects`

**Data sources:**
- agents: Hermes profiles + gateway status/service/process/config state available safely from Dashboard runtime.
- conversations: Telegram config `group_topics`, `channel_directory.json`, gateway `sessions/sessions.json`.
- projects: start minimal from known topic bindings + knowledge project page anchors; avoid over-parsing long markdown.

**Verification:**
- pytest for each endpoint shape.
- Verify topic `11648` maps to `Vw AI render`.
- Verify no secret/token fields appear.

**Commit:**
`feat(dashboard): expose agents conversations and projects`

### Task 3: Desktop control-surface sidebar for one gateway

**Objective:** Add sidebar sections for Agents, Projects, Chats, Workspaces, and Recent Sessions using one active gateway.

**Files:**
- Modify: `apps/desktop/src/hermes.ts`
- Modify: `apps/desktop/src/types/hermes.ts`
- Modify: `apps/desktop/src/store/session.ts` or new store files
- Modify: `apps/desktop/src/app/chat/sidebar/*`
- Test: Vitest sidebar grouping/render tests

**UX:**
- Agents section: live gateway/profile rows.
- Projects section: topic/project rows.
- Chats section: DM/group/topic rows not promoted to project.
- Workspaces section: cwd fallback.
- Recent Sessions remains available but not the primary structure.

**Verification:**
- Vitest for one-gateway project/topic grouping.
- Manual API smoke against WSL Dashboard.
- `npm run type-check`, `npm run build`.

**Commit:**
`feat(desktop): add agents projects and chats sidebar`

### Task 4: Multi-gateway read-only aggregation

**Objective:** Allow multiple saved gateway connections and aggregate status/sessions/entities read-only.

**Files:**
- Modify: Electron connection config + preload API
- Modify: `apps/desktop/src/hermes.ts`
- Add gateway registry/store modules
- Test: Vitest/unit tests for namespacing and aggregation

**Rules:**
- Each item gets `gateway_id` and stable composite id.
- One failing gateway must show degraded status without breaking healthy gateways.
- Read-only only. Do not send messages/tasks across non-active gateway yet.

**Verification:**
- Unit test two fake gateways with colliding session IDs.
- UI shows per-gateway online/degraded.
- Existing single-gateway behavior still passes.

**Commit:**
`feat(desktop): aggregate multiple gateways read only`

### Task 5: Multi-gateway send/routing selection

**Objective:** Add explicit selected gateway/agent/project context for new chats or replies, with safe routing rules.

**Files:**
- Modify chat compose/session creation flow.
- Modify gateway client wrapper to target chosen connection.
- Tests for routing target selection.

**Rules:**
- Sending requires one explicit selected gateway.
- Project/topic selection can prefill target context but must not silently cross-post.
- If two gateways expose the same project/topic, UI must ask/select, not guess.

**Verification:**
- Test sends route through selected gateway only.
- Test ambiguous project across gateways blocks or requires selection.
- Build/typecheck.

**Commit:**
`feat(desktop): route chat actions through selected gateway`

### Task 6: Design/UX review against Codex.app-style mental model

**Objective:** Review the control surface for clarity and density, inspired by Codex.app without copying private implementation.

**Reviewer checks:**
- Agents vs Projects vs Chats vs Workspaces are visually distinct.
- Gateway health is visible but low-noise.
- Project rows are useful without expanding every session.
- No stale workspace-first bias.
- Empty/degraded states are understandable.

**Verification:**
- Screenshot/visual review if user approves screenshot capture or local browser/electron evidence is available.
- Issues filed or patch notes for necessary polish.

### Task 7: Final QA and closeout

**Objective:** Verify the whole chain and produce final user-facing receipts.

**Checks:**
- Backend tests.
- Desktop Vitest.
- Desktop typecheck/build.
- Live Dashboard API smoke.
- Desktop launched/rebuilt on Mac if in scope.
- No token leak in logs or API payload.

**Done:** A final report with commits, test receipts, live status, Mac rebuild instruction or installed bundle receipt.

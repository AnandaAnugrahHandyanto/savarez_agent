# Hermes AI Office — Dashboard Architecture Audit

Last updated: 2026-05-08 11:44 KST
Status: Stage 2 read-only audit. No implementation or config changes performed.

## Scope

Audit Hermes' existing dashboard/server/frontend surfaces that can feed a future read-only AI Office view.

Primary source files inspected:

- `hermes_cli/web_server.py`
- `web/src/App.tsx`
- `web/src/lib/api.ts`
- `web/src/pages/SessionsPage.tsx`
- `web/src/pages/CronPage.tsx`
- `plugins/kanban/dashboard/manifest.json`
- `plugins/kanban/dashboard/plugin_api.py`
- `tests/plugins/test_kanban_dashboard_plugin.py`

## Current dashboard shape

Hermes already has a FastAPI dashboard backend plus React frontend.

Important frontend routes from `web/src/App.tsx`:

- `/sessions` — default root redirect target.
- `/analytics`
- `/models`
- `/logs`
- `/cron`
- `/skills`
- `/plugins`
- `/profiles`
- `/config`
- `/env`
- `/docs`
- `/chat` — special persistent embedded TUI route when enabled.

The AI Office should not become a second chat implementation. Existing project guidance says dashboard chat embeds the real `hermes --tui` via PTY; supporting panels are allowed, but transcript/composer behavior belongs in Ink/TUI.

## Backend API surfaces relevant to AI Office

Observed built-in dashboard endpoints from `hermes_cli/web_server.py` and `web/src/lib/api.ts`:

### Status/config/model

- `GET /api/status`
- `GET /api/config`
- `GET /api/config/defaults`
- `GET /api/config/schema`
- `GET /api/model/info`
- `GET /api/model/options`
- `GET /api/model/auxiliary`
- `POST /api/model/set`

These are useful for global office status but are not primary work-state sources.

### Sessions

- `GET /api/sessions?limit=&offset=`
- `GET /api/sessions/search?q=&limit=`
- `GET /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/latest-descendant`
- `GET /api/sessions/{session_id}/messages`
- `DELETE /api/sessions/{session_id}`

AI Office MVP should only consume read-only session endpoints. Raw messages are privacy-sensitive and should be hidden behind deliberate drill-down or omitted in the office map.

### Cron

- `GET /api/cron/jobs`
- `GET /api/cron/jobs/{job_id}`
- `POST /api/cron/jobs`
- `PUT /api/cron/jobs/{job_id}`
- `POST /api/cron/jobs/{job_id}/pause`
- `POST /api/cron/jobs/{job_id}/resume`
- `POST /api/cron/jobs/{job_id}/trigger`
- `DELETE /api/cron/jobs/{job_id}`

The existing `CronPage` uses create/pause/resume/trigger/delete. AI Office read-only MVP should initially use only list/detail unless mutation is explicitly approved later.

### Dashboard plugin system

Plugin asset and API mounting exist:

- Static plugin assets: `GET /dashboard-plugins/{plugin_name}/{file_path:path}`.
- Plugin API files expose a FastAPI `router` and are mounted under `/api/plugins/<name>`.
- Kanban manifest declares:
  - name: `kanban`
  - tab path: `/kanban`
  - entry: `dist/index.js`
  - css: `dist/style.css`
  - api: `plugin_api.py`

Kanban dashboard API is therefore `GET /api/plugins/kanban/...`, not `/api/kanban/...`.

## Authentication and exposure notes

Dashboard HTTP middleware requires the session token for most `/api/` routes, but explicitly skips `/api/plugins/`.

Source observations:

- `auth_middleware` checks `/api/` paths except public paths and paths starting with `/api/plugins/`.
- `plugins/kanban/dashboard/plugin_api.py` documents this explicitly: plugin routes are unauthenticated by design because dashboard normally binds to localhost.
- Kanban WebSocket `/api/plugins/kanban/events` still requires the dashboard session token as `?token=`.

Implication: AI Office should remain localhost-only unless plugin auth policy is changed or all new endpoints are mounted under protected non-plugin routes. Do not expose dashboard with `--host 0.0.0.0` as part of this project without a dedicated security pass.

## Existing frontend data client

`web/src/lib/api.ts` centralizes calls through `fetchJSON`, which injects `X-Hermes-Session-Token` from `window.__HERMES_SESSION_TOKEN__`. It also handles `window.__HERMES_BASE_PATH__` for reverse-proxy prefixes.

Implication: A future AI Office page should use the existing client pattern and respect `HERMES_BASE_PATH` instead of hardcoding root-relative URLs.

## Fit for AI Office MVP

Recommended read-only feeds:

1. Kanban plugin board feed for tasks, statuses, assignees, events, diagnostics, and boards.
2. Cron built-in list/detail feed for automation jobs and health.
3. Session list/search feed for provenance summaries and recent human/agent activity.
4. Telegram topic routing metadata from gateway config/source context; currently no canonical dashboard endpoint dedicated to topic registry.

## Gaps

- No single `OfficeState` API currently aggregates Kanban + cron + sessions + topic provenance.
- Kanban plugin API has many mutation endpoints; AI Office should avoid calling them for MVP.
- Plugin HTTP routes are unauthenticated; this is acceptable only under localhost assumptions.
- Dashboard has sessions and cron pages, but no existing office-like projection or cross-source topology model.
- Telegram topic registry is scattered between memory/config/env/runtime source metadata, not exposed as a clean dashboard model.

## Recommendation for Stage 3/4

Design an explicit read-only `OfficeState` model before implementation. It should be an aggregation layer over existing APIs/data stores, not a replacement for them. Candidate top-level objects:

- `rooms`: Kanban boards and Telegram topics.
- `agents`: Kanban assignees/profiles and cron automation actors.
- `work_items`: Kanban tasks and cron jobs.
- `events`: task events, cron runs, session starts/completions.
- `provenance`: source platform/chat/thread/message/session links, redacted by default.

# PeopleOS Standalone Service + Miya/WebUI Co-Management Spec

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task after Michael approves the architecture.

**Goal:** Separate PeopleOS from the Hermes Agent Dashboard and make Miya plus the PeopleOS WebUI co-manage the same profiles, schedules, notes, updates, and prep state.

**Architecture:** PeopleOS becomes a standalone local-first service, similar to WealthOS: one canonical data root, one FastAPI service contract, one WebUI client, and thin adapters for Miya/Hermes chat workflows. Miya and WebUI never write separate profile stores; both read/write through the same PeopleOS core/service layer with atomic writes, revision checks, actor attribution, and audit history.

**Tech Stack:** Existing `people_manager` Python package, FastAPI, lightweight standalone CLI entrypoint, existing React/Vite UI code adapted or moved to a PeopleOS-specific app, JSON-file storage for v1 with explicit migration/import from Miya profile data.

---

## Current Findings

### Problem 1 — PeopleOS is incorrectly embedded in Hermes Dashboard

Current PeopleOS API routes are mounted inside `hermes_cli/web_server.py` under the Hermes Agent Dashboard app:

- `GET /api/people/profiles`
- `GET /api/people/profiles/{slug}`
- `POST /api/people/profiles`
- `PATCH /api/people/profiles/{slug}`
- `POST /api/people/profiles/{slug}/interactions`
- schedule/prep/open-loop endpoints

The `/people` React surface is also served by the general Hermes dashboard SPA. This mixes product surfaces:

- Hermes Agent Dashboard = config/API keys/sessions/platform management.
- PeopleOS = independent operating system for relationship/profile management.

That should be split.

### Problem 2 — Jack3 PeopleOS data root is empty, while Miya has the real data

Current Jack3 PeopleOS root:

```text
/Users/michael.wu/.hermes/profiles/jack3/projects/people-manager
```

It currently contains only:

```text
registry.json
schedules/one_on_ones.json
```

Miya has the real profile/report state at:

```text
/Users/michael.wu/.hermes/profiles/miya/projects/people-manager
```

Observed Miya data includes:

```text
reports/fiona-cao.json
reports/alex-zhang.json
reports/toh-ghim.json
reports/yi-bao.json
reports/jeffrey-wang.json
reports/leo-que.json
reports/jason-hong.json
reports/hoekit-tan.json
reports/thomas-zhu.json
reports/michael-wu.json
reports/steve-zhang.json
schedules/one_on_ones.json
reminder-log/2026-04.jsonl
prep-queue/*.json
session-notes/2026-04-19-thomas-zhu-setup.md
```

This explains why the WebUI had no real profiles: it was reading Jack3’s empty profile-scoped store instead of the Miya-owned PeopleOS data.

---

## Design Principles

1. **PeopleOS is standalone, not a Hermes Dashboard feature.**
   - Do not expose PeopleOS inside `/dashboard` or `hermes_cli/web_server.py` long-term.
   - Hermes can launch/control PeopleOS, but not host it as the same product UI.

2. **One canonical PeopleOS data root.**
   - Miya and WebUI must share the same source of truth.
   - Avoid profile-scoped split-brain where Miya writes under `profiles/miya` and WebUI reads under `profiles/jack3`.

3. **Miya and WebUI are peers over the same service contract.**
   - WebUI uses REST.
   - Miya uses CLI/service adapter.
   - Neither should mutate raw JSON files directly after this migration.

4. **Local-first like WealthOS.**
   - Canonical state remains on this Mac.
   - Use atomic file writes + revisions before considering a DB.
   - Tailscale-reachable WebUI by default.

5. **Explicit actor attribution and audit.**
   - Every write records actor: `miya`, `web`, `jack3`, `scheduler`, etc.
   - Every write records source surface and timestamp.

6. **Safe concurrent edits.**
   - Use revision/ETag-style optimistic concurrency for profile writes.
   - WebUI should warn if Miya updated a profile after the page loaded.

---

## Proposed Runtime Shape

### Canonical workspace

Create a standalone PeopleOS workspace, analogous to WealthOS:

```text
/Users/michael.wu/.PeopleOS
```

Initial v1 layout:

```text
.PeopleOS/
  peopleos_service_spec.md
  peopleos.toml
  data/
    registry.json
    reports/
    schedules/
      one_on_ones.json
    prep-queue/
    reminder-log/
    session-notes/
    audit-log/
      YYYY-MM.jsonl
    revisions/
      profile-revisions.json
  app/
    main.py              # FastAPI app
    service.py           # service/read/write operations
    storage.py           # canonical root, atomic IO, revisions, locks
    schemas.py           # request/response schemas
    miya_client.py       # Miya-facing service/CLI client helpers
    cli.py               # people CLI
  web/
    ...                  # standalone PeopleOS WebUI
  scripts/
    migrate_from_miya.py
    peopleos_server.py
    peopleos_cli.py
  tests/
```

Alternative if we want less movement for v1: keep code in `hermes-agent/people_manager` temporarily, but set the data root to `/Users/michael.wu/.PeopleOS/data` and expose it via a standalone `peopleos` CLI/server. This is lower-risk and likely the best first implementation slice.

### Ports and binding

Use a dedicated PeopleOS port so it cannot be confused with Hermes Dashboard:

```text
PeopleOS Web/API: http://100.118.42.113:8891
Hermes Dashboard: keep separate, e.g. http://100.118.42.113:9120 if needed
WealthOS: already separate, e.g. http://100.118.42.113:8876
```

PeopleOS should default to Tailscale-reachable binding for this user.

---

## Source-of-Truth Model

### Canonical profile document

Continue with current report JSON shape for v1, but add metadata needed for multi-writer safety:

```json
{
  "version": 1,
  "slug": "fiona-cao",
  "name": "Fiona Cao",
  "role_title": "...",
  "profile_type": "internal",
  "relationship_kind": "direct_report",
  "created_at": "...",
  "updated_at": "...",
  "revision": "sha256:...",
  "last_actor": "miya",
  "last_source": "telegram",
  "role_charter": {},
  "goals": {},
  "operating_state": {},
  "performance": {},
  "management_strategy": {},
  "open_loops": {},
  "open_loop_items": [],
  "interaction_log": []
}
```

### Interaction log as canonical update history

All content updates from Miya and WebUI should go through the existing interaction pattern:

- `update`
- `one_on_one`
- `assessment`
- `todo_report`
- `todo_manager`

Add fields to each interaction:

```json
{
  "id": "int_20260429_...",
  "kind": "update",
  "body": "...",
  "lane_id": "miya-telegram",
  "actor": "miya",
  "source": "telegram",
  "created_at": "...",
  "applied_patch_summary": ["added open loop", "updated performance read"]
}
```

### Audit log

Every write appends JSONL:

```json
{
  "at": "2026-04-29T...Z",
  "actor": "web",
  "source": "peopleos-webui",
  "operation": "profile.patch",
  "slug": "fiona-cao",
  "before_revision": "sha256:...",
  "after_revision": "sha256:...",
  "request_id": "..."
}
```

---

## API Contract

Standalone PeopleOS service exposes only PeopleOS endpoints:

### Health

```http
GET /healthz
GET /readyz
GET /api/status
```

### Profiles

```http
GET    /api/profiles?profile_type=&q=&status=
POST   /api/profiles
GET    /api/profiles/{slug}
PATCH  /api/profiles/{slug}
DELETE /api/profiles/{slug}        # archive, not hard delete, for v1
```

Write requests accept optional revision guard:

```json
{
  "expected_revision": "sha256:abc...",
  "actor": "web",
  "source": "peopleos-webui",
  "patch": {
    "role_title": "..."
  }
}
```

If revision mismatch:

```http
409 Conflict
```

Response includes current server document + revisions so WebUI can offer reload/merge.

### Interactions / notes / updates

```http
GET  /api/profiles/{slug}/interactions
POST /api/profiles/{slug}/interactions
```

Payload:

```json
{
  "kind": "update",
  "body": "Discussed hiring priorities...",
  "actor": "miya",
  "source": "telegram",
  "lane_id": "miya-telegram",
  "expected_revision": "sha256:..."
}
```

### Open loops

```http
POST  /api/profiles/{slug}/open-loops
PATCH /api/profiles/{slug}/open-loops/{loop_id}
```

### Prep

```http
GET  /api/profiles/{slug}/prep?mode=adhoc&minutes_until=5
POST /api/profiles/{slug}/prep/preview
```

### Schedules

```http
GET    /api/schedules
POST   /api/schedules
GET    /api/schedules/{slug}
PATCH  /api/schedules/{slug}
DELETE /api/schedules/{slug}
POST   /api/schedules/{slug}/reschedule-once
POST   /api/schedules/{slug}/enable
POST   /api/schedules/{slug}/disable
```

### Ops / Miya bridge

```http
POST /api/ops/run-due-check
GET  /api/ops/due-now
GET  /api/ops/audit
POST /api/miya/claim-next-prep
POST /api/miya/mark-prep-sent
POST /api/miya/mark-prep-failed
```

These replace raw file access for Miya bridge scripts.

---

## Miya Integration Model

Miya should become a client of PeopleOS, not the private owner of a separate PeopleOS data folder.

### Miya responsibilities

Miya can:

- create profiles
- update profile fields
- append notes/interactions
- create/close open loops
- manage schedules/reschedules
- claim prep jobs
- mark prep delivery status
- read profiles for contextual preparation

Miya should not:

- write `reports/*.json` directly
- own the only copy of PeopleOS data under `profiles/miya`
- force WebUI to sync from chat logs after the fact

### Miya tool/adapter options

#### v1 fastest path: CLI adapter

Add:

```bash
peopleos profile list --json
peopleos profile show fiona-cao --json
peopleos profile create --name ...
peopleos note add fiona-cao --kind update --body ... --actor miya --source telegram
peopleos loop add fiona-cao --text ... --owner manager
peopleos schedule list --json
peopleos prep claim-next --actor miya
```

Miya calls this CLI from its local environment. CLI talks to service when available; fallback can use core storage only if service is down and lock is available.

#### v2 cleaner path: Hermes toolset for Miya

Expose PeopleOS as a dedicated toolset:

- `peopleos_list_profiles`
- `peopleos_get_profile`
- `peopleos_create_profile`
- `peopleos_add_interaction`
- `peopleos_update_open_loop`
- `peopleos_get_prep`

Tool handlers call `http://100.118.42.113:8891/api/...`.

This gives Miya structured access without raw filesystem coupling.

---

## WebUI Model

PeopleOS WebUI should be a separate app shell:

- product title: PeopleOS
- no Hermes provider/API-key/session dashboard nav
- no Hermes config endpoints in the same app
- only PeopleOS routes

Pages:

```text
/                         -> redirect to /profiles
/profiles                 -> roster, filters, create profile
/profiles/:slug           -> profile detail
/schedules                -> 1:1 cadence + reschedules
/prep                     -> due prep queue / previews
/open-loops               -> cross-profile open loops
/audit                    -> audit/debug surface
```

Profile detail sections:

- Profile card
- Facts
- Judgment / management read
- Actions / open loops
- Notes/interactions timeline
- Quick add note/update
- Prep panel
- Schedule card

Important: WebUI writes through same `/api/...` endpoints as Miya.

---

## Migration Plan

### Phase 0 — Stop serving PeopleOS from Hermes Dashboard

- Remove or deprecate PeopleOS routes from `hermes_cli/web_server.py`.
- Remove `/people` nav/route from Hermes Dashboard SPA.
- Optionally keep a temporary redirect/info page: “PeopleOS moved to `http://100.118.42.113:8891`.”

### Phase 1 — Create canonical PeopleOS data root

- Create `/Users/michael.wu/.PeopleOS/data`.
- Copy Miya’s current data into it:

```text
from: /Users/michael.wu/.hermes/profiles/miya/projects/people-manager
to:   /Users/michael.wu/.PeopleOS/data
```

- Preserve Miya folder as backup, not live source.
- Add migration manifest:

```text
/Users/michael.wu/.PeopleOS/data/migrations/2026-04-29-from-miya-profile.json
```

### Phase 2 — Make `people_manager` root configurable

Current root function:

```python
def get_people_manager_root() -> Path:
    root = get_hermes_home() / "projects" / PROJECT_DIRNAME
```

Change to resolve in order:

1. `PEOPLEOS_DATA_ROOT` env var
2. `peopleos.data_root` config, if present
3. fallback: current profile-scoped path for compatibility only

For standalone PeopleOS launch, set:

```bash
PEOPLEOS_DATA_ROOT=/Users/michael.wu/.PeopleOS/data
```

### Phase 3 — Standalone PeopleOS FastAPI service

Add `peopleos_service.py` or `people_manager/web_service.py` with its own FastAPI app:

- title: `PeopleOS`
- only PeopleOS routes
- no Hermes Dashboard auth/session/config endpoints
- CORS limited to its own WebUI origin for v1 local use

Launch command:

```bash
source venv/bin/activate
PEOPLEOS_DATA_ROOT=/Users/michael.wu/.PeopleOS/data \
python -m people_manager.web_service --host 100.118.42.113 --port 8891
```

### Phase 4 — Standalone WebUI

Fastest v1:

- Extract current React PeopleOS pages/components from Hermes dashboard web app.
- Build a tiny PeopleOS-only Vite app or static HTML app.
- Point API client at relative `/api` on the PeopleOS service.

No Hermes dashboard sidebar, sessions, provider settings, or API key surfaces.

### Phase 5 — Miya client migration

Patch Miya-facing scripts:

- `scripts/one_on_one_prep.py`
- `scripts/miya_one_on_one_bridge.py`
- any Miya cron prompts / command paths

So they use one of:

1. `PEOPLEOS_DATA_ROOT=/Users/michael.wu/.PeopleOS/data` for compatibility, then later
2. PeopleOS CLI/API client for all writes.

### Phase 6 — Multi-writer safety

Add:

- file lock around writes
- revision hash per profile
- `expected_revision` on WebUI patch/interactions
- audit log JSONL
- clear `409 Conflict` response on stale edits

---

## Implementation Plan

### Task 1: Add PeopleOS root resolver tests

**Objective:** Make the PeopleOS data root independent from Hermes profile root.

**Files:**
- Modify: `people_manager/storage.py`
- Test: `tests/people_manager/test_peopleos_data_root.py`

**Test cases:**

- `PEOPLEOS_DATA_ROOT` overrides `HERMES_HOME`.
- fallback remains `get_hermes_home() / projects / people-manager`.
- resolver creates required subdirs.

### Task 2: Add Miya migration script

**Objective:** Copy Miya’s existing PeopleOS data into canonical `/Users/michael.wu/.PeopleOS/data` safely.

**Files:**
- Create: `scripts/peopleos_migrate_from_miya.py`
- Test: `tests/people_manager/test_peopleos_migration.py`

**Rules:**

- refuse to overwrite non-empty destination unless `--force`.
- copy reports/schedules/prep-queue/reminder-log/session-notes.
- write migration manifest.
- verify registry/report counts.

### Task 3: Add standalone PeopleOS FastAPI app

**Objective:** Serve PeopleOS API separately from Hermes Dashboard.

**Files:**
- Create: `people_manager/web_service.py`
- Test: `tests/people_manager/test_peopleos_web_service.py`

**Routes:**

- `/healthz`
- `/api/profiles...`
- `/api/schedules...`
- `/api/ops...`

Use existing `people_manager.api_service` internally.

### Task 4: Remove PeopleOS API mounting from Hermes Dashboard

**Objective:** Stop mixing PeopleOS into Hermes Agent Dashboard.

**Files:**
- Modify: `hermes_cli/web_server.py`
- Modify: `web/src/App.tsx` and related dashboard nav/routes
- Test: dashboard tests that assert PeopleOS is not part of Hermes Dashboard

**Temporary compatibility:** Either return `404` for `/api/people/*` or a `410 Gone` JSON pointing to PeopleOS service. Prefer `410` during transition.

### Task 5: Add PeopleOS standalone launch command

**Objective:** Give PeopleOS its own run command, not `hermes dashboard`.

**Options:**

- `python -m people_manager.web_service --host 100.118.42.113 --port 8891`
- or `hermes peopleos --host ... --port ...` if we want Hermes as a supervisor only.

For product separation, prefer a standalone script first:

```bash
scripts/peopleos_server.py --host 100.118.42.113 --port 8891
```

### Task 6: Add revision + audit write wrapper

**Objective:** Make Miya and WebUI safe concurrent writers.

**Files:**
- Modify: `people_manager/storage.py`
- Modify: `people_manager/api_service.py`
- Test: `tests/people_manager/test_peopleos_revisions.py`

**Behavior:**

- profile response includes `revision`.
- patch accepts `expected_revision`.
- stale expected revision returns conflict at API layer.
- writes append audit log.

### Task 7: Add PeopleOS CLI client for Miya

**Objective:** Let Miya manage content through PeopleOS contract.

**Files:**
- Create: `people_manager/cli.py`
- Create: `scripts/peopleos_cli.py`
- Test: `tests/people_manager/test_peopleos_cli.py`

**Commands:**

```bash
peopleos profile list --json
peopleos profile show <slug> --json
peopleos profile create --name ... --role-title ...
peopleos note add <slug> --kind update --body ... --actor miya --source telegram
peopleos loop add <slug> --text ... --owner manager
peopleos prep claim-next --actor miya
```

### Task 8: Patch Miya bridge/scripts to use canonical PeopleOS

**Objective:** Miya and WebUI read/write the same profiles.

**Files:**
- Modify: `scripts/one_on_one_prep.py`
- Modify: `scripts/miya_one_on_one_bridge.py`
- Possibly Miya cron job prompt/config

**Minimum v1:** set `PEOPLEOS_DATA_ROOT=/Users/michael.wu/.PeopleOS/data` in Miya execution environment.

**Better v1.1:** replace direct file calls with PeopleOS CLI/API calls.

### Task 9: Extract PeopleOS WebUI

**Objective:** Create independent PeopleOS web app shell.

**Files:**
- Create: `people_web/` or `.PeopleOS/web/`
- Move/adapt existing People pages from `web/src/pages/PeoplePage.tsx`, `PeopleDetailPage.tsx`.
- API base becomes PeopleOS-local `/api`, not Hermes dashboard `/api/people`.

**Routes:**

- `/profiles`
- `/profiles/:slug`
- `/schedules`
- `/prep`
- `/open-loops`
- `/audit`

### Task 10: Live verification

**Commands:**

```bash
source venv/bin/activate
pytest tests/people_manager -q
pytest tests/hermes_cli/test_people_manager_web_api.py tests/hermes_cli/test_people_manager_web_ui.py -q  # updated expectations
PEOPLEOS_DATA_ROOT=/Users/michael.wu/.PeopleOS/data python -m people_manager.web_service --host 100.118.42.113 --port 8891
curl http://100.118.42.113:8891/healthz
curl http://100.118.42.113:8891/api/profiles
```

Expected profile count after migration: 11+ profiles from Miya.

---

## Open Decisions

1. **Canonical code location:**
   - A. Keep `people_manager` package inside `hermes-agent` for now, standalone service/data root only.
   - B. Move PeopleOS to `/Users/michael.wu/.PeopleOS` as its own repo/app immediately.

   Recommendation: A first, B later if PeopleOS grows. Faster and lower-risk.

2. **Hermes Dashboard compatibility behavior:**
   - A. Remove `/people` completely.
   - B. Show “PeopleOS moved” redirect/info page.

   Recommendation: B for one transition cycle, then remove.

3. **Miya write path:**
   - A. Shared data root via env var immediately.
   - B. Force Miya through PeopleOS service/CLI immediately.

   Recommendation: A for migration day, B as the durable target.

4. **Storage backend:**
   - A. JSON files + revisions/locks.
   - B. SQLite now.

   Recommendation: A for v1 because current report shape is rich JSON and already works; add SQLite only if search/query/concurrency needs grow.

---

## Acceptance Criteria

- Hermes Dashboard no longer serves PeopleOS as part of its app shell.
- PeopleOS has a dedicated Tailscale URL, e.g. `http://100.118.42.113:8891`.
- WebUI roster loads Miya’s existing profiles: Fiona, Alex, Toh Ghim, Yi Bao, Jeffrey, Leo, Jason, Hoekit, Thomas, Michael, Steve.
- Miya-created updates appear in WebUI without manual copy.
- WebUI-created notes/open-loops are visible to Miya prep/bridge flows.
- Profile writes include actor/source and audit history.
- Stale WebUI writes are rejected or prompted with a reload/merge path.
- Existing one-on-one prep queue and schedule logic continue to work.

---

## Non-goals for First Slice

- Cloud sync.
- Multi-user auth beyond local/Tailscale trusted access.
- Full database rewrite.
- Complex CRDT merge.
- Replacing Miya’s product role; Miya remains product/operator user, while Jack3 owns engineering/code execution.

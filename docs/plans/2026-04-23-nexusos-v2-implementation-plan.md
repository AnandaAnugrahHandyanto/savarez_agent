# NexusOS v2 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Turn the existing `people_manager` / NexusOS foundation into a clean, tested v2 system with one shared core and three surfaces: Telegram, Web UI, and Miya CLI.

**Architecture:** Keep deterministic, file-backed state under `HERMES_HOME/projects/people-manager/`. Harden the shared domain/service layer first, then expose it through a thin Web API and a minimal but useful web dashboard. Telegram and CLI remain intercept/ops surfaces only; they must call shared people-manager functions rather than embedding business logic.

**Tech Stack:** Python, existing `people_manager/*` modules, FastAPI in `hermes_cli/web_server.py`, existing CLI script `scripts/one_on_one_prep.py`, pytest, file-backed JSON/JSONL storage.

---

## Implementation principles

- Treat Miya’s spec as product truth.
- Prefer additive evolution over destructive schema rewrites.
- Deterministic mutation only on explicit grammar / explicit API writes.
- No fuzzy name guessing beyond exact normalized full name, exact slug, or unique exact first-name match.
- Scheduled prep and ad hoc prep must share one bullet-selection path; only the title differs.
- Keep judgment separation explicit in interaction records: `facts`, `michael_judgment`, `miya_synthesis`.
- Keep report state project-scoped under `HERMES_HOME/projects/people-manager/`.

## Current repo foundation confirmed

Core:
- `people_manager/storage.py`
- `people_manager/service.py`
- `people_manager/parser.py`
- `people_manager/ad_hoc_prep.py`
- `people_manager/prep_renderer.py`
- `people_manager/renderers.py`
- `people_manager/schedule_store.py`
- `people_manager/prep_queue.py`
- `people_manager/reminder_log.py`
- `people_manager/merge.py`

Surfaces:
- `cli.py` `/people` intercept
- `gateway/run.py` `/people` intercept
- `scripts/one_on_one_prep.py` Miya/operator CLI
- `hermes_cli/web_server.py` existing FastAPI server to extend

Existing tests already cover a large chunk of the people-manager system and should be extended rather than bypassed.

## Main gaps from inspection

1. `render_prep_note()` does not yet support shared ad hoc vs scheduled title modes.
2. Ad hoc prep currently uses separate selection logic in `ad_hoc_prep.py` instead of one shared renderer path.
3. Name resolution still uses prefix-style first-token matching (`startswith`) rather than exact unique first-name matching.
4. Parser does not explicitly support multiline capture guarantees for Telegram bullet blocks.
5. There is no shared web API for profiles/prep/schedules/ops.
6. There is no web UI surface for team overview/profile/prep/team scan/ops.
7. CLI script is still schedule-centric and needs to be treated as the Miya operator surface for v2.

## Phase breakdown

### Phase 1 — Harden and unify the core

**Files:**
- Modify: `people_manager/storage.py`
- Modify: `people_manager/parser.py`
- Modify: `people_manager/ad_hoc_prep.py`
- Modify: `people_manager/prep_renderer.py`
- Modify: `people_manager/service.py`
- Modify: `people_manager/merge.py` (only if needed for multiline normalization)
- Add: `people_manager/api_service.py`
- Add/modify tests under `tests/people_manager/`, `tests/cli/`, `tests/gateway/`, `tests/scripts/`

**Behavior to lock first in tests:**
- supported Telegram grammar
- multiline `1:1 <name>:` bullet-block capture
- deterministic ambiguity handling
- shared ad hoc/scheduled prep rendering path
- sparse prep fallback
- safe non-mutation outside `/people`
- storage normalization/backward compatibility

**Task 1: Lock parser behavior in tests**
- Add parser tests for:
  - multiline `1:1 Fiona:\n- blocker\n- ask`
  - multiline `Update`, `Assessment`, `Todo`
  - `Prep <name>`, `1o1 prep <name>`, `1:1 prep <name>`, `1o1 <name>`, `1:1 <name>`
  - ambiguity-safe name lookup expectations

**Task 2: Lock shared prep behavior in tests**
- Extend `tests/people_manager/test_prep_renderer.py` to require:
  - `title_mode="scheduled"` -> `<Name> 1:1 in 5m`
  - `title_mode="adhoc"` -> `<Name> 1:1`
  - same selected bullets in both modes
  - metadata-ish fields excluded
  - sparse-profile minimal fallback

**Task 3: Lock service and storage normalization behavior in tests**
- Add tests for:
  - exact unique first-name resolution only
  - prefix-like partials do not silently resolve
  - older/sparse report files normalize on load
  - explicit interaction fields preserve `facts` / `michael_judgment` / `miya_synthesis`

**Task 4: Implement report normalization in storage**
- Add `normalize_report()` in `people_manager/storage.py`.
- Ensure `load_report()` normalizes older records and missing nested keys.
- Keep writeback additive and non-destructive.
- Keep registry/report paths under `get_hermes_home()`.

**Task 5: Fix deterministic name resolution**
- Update `resolve_report_by_name()` so allowed matches are only:
  - exact normalized full name
  - exact slug
  - unique exact first-name match
- Reject ambiguous names with short disambiguation text.
- Remove partial-prefix matching behavior.

**Task 6: Make parser multiline-safe**
- Update regex parsing to support multiline bodies via `re.DOTALL` and trimmed body preservation.
- Keep free-form unmatched messages non-mutating.

**Task 7: Unify prep rendering**
- Refactor `people_manager/prep_renderer.py` to own bullet selection.
- Shared selector should pull, in rough order:
  - ritual / cadence line
  - upcoming topics
  - current focus / manager todo / follow-through cues
  - management watchout / escalation / question
  - tone guidance
- Add explicit `title_mode` (`adhoc` | `scheduled`).

**Task 8: Route ad hoc prep through the shared prep renderer**
- Simplify `people_manager/ad_hoc_prep.py` to resolve report + schedule and call `render_prep_note(..., title_mode="adhoc")`.
- Keep `scripts/one_on_one_prep.py` on `render_prep_note(..., title_mode="scheduled")`.

**Task 9: Harden service routing**
- Keep `/people` deterministic-only mutation.
- Ensure prep/review/team-scan/challenge remain non-mutating.
- Keep safe fallthrough outside `/people`.

### Phase 2 — Add shared Web API

**Files:**
- Add: `people_manager/api_service.py`
- Modify: `hermes_cli/web_server.py`
- Add: `tests/hermes_cli/test_people_manager_web_api.py`

**Approach:**
Create one thin API layer backed by `people_manager/api_service.py`. Web handlers should translate HTTP input/output only.

**Endpoints to implement:**
- `GET /api/people/profiles`
- `GET /api/people/profiles/{slug}`
- `POST /api/people/profiles`
- `PATCH /api/people/profiles/{slug}`
- `GET /api/people/profiles/{slug}/interactions`
- `POST /api/people/profiles/{slug}/interactions`
- `POST /api/people/profiles/{slug}/open-loops`
- `PATCH /api/people/profiles/{slug}/open-loops/{id}`
- `GET /api/people/profiles/{slug}/prep?mode=adhoc|scheduled`
- `POST /api/people/profiles/{slug}/prep/preview`
- `GET /api/people/team-scan`
- `GET /api/people/schedules`
- `GET /api/people/schedules/{slug}`
- `POST /api/people/schedules`
- `PATCH /api/people/schedules/{slug}`
- `POST /api/people/schedules/{slug}/enable`
- `POST /api/people/schedules/{slug}/disable`
- `POST /api/people/schedules/{slug}/preview`
- `POST /api/people/schedules/{slug}/reschedule-once`
- `DELETE /api/people/schedules/{slug}`
- `GET /api/people/ops/due-now`
- `GET /api/people/ops/log`
- `GET /api/people/ops/audit`
- `POST /api/people/ops/run-once`

**Task 10: Add failing API tests first**
- Build `TestClient` coverage for profile, prep, schedule, ops, and team-scan endpoints.
- Reuse `_SESSION_TOKEN` auth pattern from `tests/hermes_cli/test_web_server.py`.

**Task 11: Add shared `api_service.py`**
- Provide profile CRUD wrappers.
- Provide interaction and open-loop helpers.
- Provide schedule CRUD / enable / disable / preview / reschedule helpers.
- Provide ops helpers for due-now / log / audit / run-once.
- Keep business logic out of `web_server.py`.

**Task 12: Wire FastAPI routes**
- Add the `/api/people/*` routes in `hermes_cli/web_server.py`.
- Return inspectable JSON and concise preview strings where appropriate.

### Phase 3 — Build first usable Web UI

**Files:**
- Modify: `hermes_cli/web_server.py`
- Add: `hermes_cli/web_dist/nexusos.html` or serve an inline HTML dashboard route if no frontend source tree exists
- Add: `tests/hermes_cli/test_people_manager_web_ui.py` (light smoke coverage)

**Approach:**
Ship a practical local dashboard, not a polished SPA rewrite. Since the repo currently exposes a built web-dist artifact rather than source TSX files, the fastest clean path is a server-served HTML page using the shared `/api/people/*` endpoints.

**Views to ship:**
- Team Overview
- Person Profile
- Prep View
- Team Scan / Calibration
- Ops / Schedule View

**Task 13: Add a minimal UI route**
- Serve `/nexusos` (or similar) with a small dashboard shell.
- Use fetch calls to `/api/people/*`.
- Show team list, profile detail, prep preview, team scan, due-now, and schedules.

**Task 14: Add web UI smoke tests**
- Verify route loads and contains the main section labels.
- Keep tests shallow; domain behavior belongs in API tests.

### Phase 4 — Finish Miya CLI / operator tooling

**Files:**
- Modify: `scripts/one_on_one_prep.py`
- Extend: `tests/scripts/test_one_on_one_prep.py`

**Task 15: Treat `scripts/one_on_one_prep.py` as Miya operator CLI**
- Preserve existing commands.
- Ensure coverage for:
  - list reports/schedules
  - inspect profile/schedule
  - preview prep
  - run-once
  - due-now
  - enable / disable
  - update schedule
  - remove / archive
  - inspect logs
  - audit missing/sparse/malformed state

**Task 16: Add concise migration notes**
- Document normalization behavior and compatibility assumptions.
- Call out any deferred work explicitly.

## Testing commands

Run before and after each phase:

```bash
source venv/bin/activate
pytest tests/people_manager -q
pytest tests/cli/test_people_manager_cli.py tests/gateway/test_people_manager_gateway.py -q
pytest tests/scripts/test_one_on_one_prep.py -q
pytest tests/hermes_cli/test_people_manager_web_api.py -q
pytest tests/hermes_cli/test_people_manager_web_ui.py -q
```

Before finalizing:

```bash
source venv/bin/activate
pytest tests/people_manager -q tests/cli/test_people_manager_cli.py tests/gateway/test_people_manager_gateway.py tests/scripts/test_one_on_one_prep.py tests/hermes_cli/test_people_manager_web_api.py tests/hermes_cli/test_people_manager_web_ui.py
```

## Expected deliverables

1. Hardened shared people-manager service layer
2. Deterministic Telegram capture + prep behavior
3. Shared prep renderer for ad hoc + scheduled flows
4. Thin shared `/api/people/*` API
5. First usable local NexusOS web dashboard
6. Preserved and improved Miya/operator CLI
7. Migration/normalization notes
8. Concise shipped-vs-deferred summary

## Deferred unless blockers force it

- rich frontend polish / SPA rewrite
- database migration
- recruiting / ATS / HR features
- fuzzy semantic entity resolution
- automated background “smart” mutation of records from free chat

# Acta First-Principles Architecture Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Rebuild Acta around a persistent output/library model so important user-requested artifacts and cron-generated reports do not get buried by daily snapshots or latest-run links.

**Architecture:** Acta should be a personal intelligence library, not merely a cron dashboard. Preserve raw cron output files as source events, add a normalized artifact/output catalog with durable IDs, metadata, collections, read state, and pinned/archive behavior, then render Acta pages from that catalog. Cron jobs and chat-triggered “send to outputs” actions both publish into the same catalog, but with different origin metadata.

**Tech Stack:** Python static generator in `cron/acta_dashboard.py`, Hermes cron output files under `~/.hermes/cron/output/`, current durable visual artifacts under `~/.hermes/artifacts/acta-outputs/`, R2/Cloudflare publishing via existing `publish_html_artifact`, tests in `tests/cron/test_acta_dashboard.py`.

---

## Problem Statement

The current Acta implementation has evolved into three overlapping concepts:

1. **Today / Situation Room:** latest cron status dashboard.
2. **Archive:** date snapshots of the situation room.
3. **Outputs:** currently built from the latest output per cron job, so it behaves like “today’s latest cron objects,” not a persistent library.

This breaks the user expectation: when the user says “put this in outputs,” they mean “create a persistent, findable output artifact.” Example: the Hermes OS / Hermes Agent Lanes decision tree still exists in `~/.hermes/artifacts/acta-outputs/`, but the current Situation Room `/outputs` page is generated from cron latest items and can obscure or replace that mental model.

## First-Principles Product Definition

Acta is the user’s personal output surface for Hermes.

It has four jobs:

1. **Publish polished artifacts:** Long explanations, decision trees, research memos, plans, dashboards, and briefing pages.
2. **Preserve outputs durably:** Important outputs should have stable URLs, metadata, collections, search/filter/sort, read/archive/pin state, and should not disappear because a newer cron run happened.
3. **Expose automation runs:** Cron outputs should be browsable by job, category, date, status, freshness, and source, with full run history.
4. **Route follow-up back to work:** Every output should make it obvious how to ask follow-up, rerun, promote, pin, archive, or continue work.

## Proposed Information Architecture

### 1. Home: `/`

Purpose: current operational cockpit.

Contains:
- Today’s active brief/status cards.
- Fresh/unread important items.
- Pinned outputs.
- Alerts from failed/stale jobs.

Does **not** try to be the permanent library.

### 2. Library / Outputs: `/outputs`

Purpose: persistent set of output artifacts.

Contains every item intentionally published as an Acta output:
- User-requested artifacts from chat: “put this in outputs.”
- Promoted cron outputs: a cron run worth keeping beyond the run stream.
- Generated visual pages, decision trees, reports, plans, briefs.

Core controls:
- Search.
- Sort: newest, oldest, updated, pinned first, unread, category.
- Filters: source, category, tag, project/app, origin, read/unread, pinned/archive.
- Views: All, Pinned, Unread, Archived.

Stable object shape:
```json
{
  "id": "hermes-agent-lanes-decision-tree",
  "title": "Hermes Agent Lanes & Specialist Agents",
  "summary": "Visual decision tree for Telegram lanes, profiles, and Kanban/swarm usage.",
  "kind": "visual-explanation",
  "category": "hermes-os",
  "tags": ["hermes", "telegram", "profiles", "kanban", "decision-tree"],
  "origin": "chat",
  "source_ref": {
    "platform": "telegram",
    "chat_id": "[REDACTED]",
    "thread_id": "865",
    "session_id": "20260524_094001_11b32885"
  },
  "artifact_path": "~/.hermes/artifacts/acta-outputs/hermes-agent-lanes-decision-tree.html",
  "public_path": "/outputs/hermes-agent-lanes-decision-tree",
  "created_at": "2026-05-24T16:49:00Z",
  "updated_at": "2026-05-24T16:49:00Z",
  "status": "live",
  "pinned": false,
  "archived": false,
  "read_state": "unread"
}
```

### 3. Runs: `/runs`

Purpose: raw automation run history.

This replaces the confusing idea that `/outputs` means “latest cron runs.”

Controls:
- Filter by job.
- Filter by date range.
- Filter by delivery target/topic.
- Filter by status: ok, failed, silent, skipped.
- Sort by newest/oldest/job/category.
- Promote button: “Save to Outputs.”

### 4. Jobs: `/jobs`

Purpose: cron job management/observability.

Contains:
- Job schedule.
- Enabled/paused state.
- Last run.
- Last status.
- Delivery target.
- Recent runs link.

### 5. Archive: `/archive`

Purpose: historical snapshots and old/archived outputs.

Split into:
- `/archive/days`: day snapshots of Situation Room, if still useful.
- `/outputs?state=archived`: archived persistent outputs.
- `/runs?date=YYYY-MM-DD`: run history for a day.

The current “archive only shows the day’s things” is not wrong for snapshots, but it is wrong if the user expects it to be the output library.

## Data Architecture

### New canonical catalog

Create a catalog file:

`~/.hermes/acta/catalog.json`

This is the durable source of truth for persistent outputs.

Why JSON first:
- Low migration risk.
- Easy to inspect and repair manually.
- Fits current static generator.
- Can be upgraded to SQLite later if needed.

Suggested structure:
```json
{
  "version": 1,
  "items": [
    {
      "id": "...",
      "title": "...",
      "kind": "...",
      "category": "...",
      "tags": [],
      "origin": "chat|cron|manual|system",
      "source_ref": {},
      "artifact_path": "...",
      "public_path": "...",
      "created_at": "...",
      "updated_at": "...",
      "status": "draft|live|archived|deleted",
      "pinned": false,
      "archived": false,
      "read_state": "unread|read"
    }
  ]
}
```

### Existing sources remain source-of-truth for raw content

- Cron raw runs stay in `~/.hermes/cron/output/{job_id}/{timestamp}.md/html`.
- Visual chat artifacts stay under `~/.hermes/artifacts/acta-outputs/` or migrate under `~/.hermes/acta/artifacts/`.
- Published R2 paths remain public serving layer, not canonical metadata.

## Key UX Rule

Clicking `/outputs` should never mean “open today’s output.”

It should show a persistent library. A row/card click should open that exact persistent artifact. If the item is a cron-derived saved output, it opens that exact run/artifact, not whatever the job’s latest run happens to be now.

## Migration Plan

### Task 1: Inventory existing Acta artifacts

**Objective:** Find all current persistent output artifacts and cron run outputs.

**Files:**
- Read: `~/.hermes/artifacts/acta-outputs/index.html`
- Read: `~/.hermes/artifacts/acta-outputs/*.html`
- Read: `~/.hermes/cron/output/*/*.md`
- Modify: none

**Verification:** The Hermes Agent Lanes artifact must be detected as a persistent output candidate.

### Task 2: Create catalog module

**Objective:** Add load/save/upsert helpers for `~/.hermes/acta/catalog.json`.

**Files:**
- Create or modify: `cron/acta_catalog.py`
- Test: `tests/cron/test_acta_catalog.py`

**Behavior:**
- Atomic JSON writes.
- Stable slug IDs.
- Upsert by ID.
- Preserve user state fields like pinned/read/archive.
- Redact private source refs when rendering public HTML.

### Task 3: Import existing persistent artifacts

**Objective:** Build a one-time importer for `~/.hermes/artifacts/acta-outputs/`.

**Files:**
- Create: `scripts/acta_import_existing_outputs.py`
- Test: `tests/cron/test_acta_catalog.py`

**Acceptance:**
- `hermes-agent-lanes-decision-tree` appears in catalog.
- Existing titles/tags/summaries are parsed from index/card metadata when available.
- Re-running importer is idempotent.

### Task 4: Render `/outputs` from catalog, not latest cron items

**Objective:** Make `/outputs` a persistent library.

**Files:**
- Modify: `cron/acta_dashboard.py`
- Test: `tests/cron/test_acta_dashboard.py`

**Acceptance:**
- `/outputs` includes imported persistent artifacts.
- `/outputs` does not collapse cron jobs to only latest run.
- Card links are stable artifact links.
- Filters/sort are present in the HTML structure.

### Task 5: Add `/runs` for cron history

**Objective:** Move cron-output browsing into a dedicated run history page.

**Files:**
- Modify: `cron/acta_dashboard.py`
- Test: `tests/cron/test_acta_dashboard.py`

**Acceptance:**
- `/runs` can show multiple runs per job.
- `/runs?job=<id>` and `/runs?date=<date>` render meaningful filtered pages or static prebuilt equivalents.
- Each run can link to its exact HTML/Markdown-derived artifact.

### Task 6: Add promote-to-output path

**Objective:** Allow valuable cron runs to be saved to the persistent outputs catalog.

**Files:**
- Modify: `cron/acta_dashboard.py`
- Create: `scripts/acta_promote_run.py`
- Test: `tests/cron/test_acta_catalog.py`

**Acceptance:**
- A specific cron run can be promoted into catalog with stable ID/title/category/tags.
- Promoting a newer run does not overwrite older saved outputs unless explicitly same ID.

### Task 7: Add filter/sort/read/archive/pin model

**Objective:** Make outputs usable once the library grows.

**Files:**
- Modify: `cron/acta_dashboard.py`
- Modify: `tests/cron/test_acta_dashboard.py`

**Acceptance:**
- Render controls for category, origin, status, read, pinned, archived.
- Client-side filtering works without server state.
- Server-generated HTML includes all metadata as `data-*` fields.
- Read/archive/pin use local storage/cookies initially, with future server-side state deferred.

### Task 8: Rename navigation for clarity

**Objective:** Remove product ambiguity.

**Recommended nav:**
- Today
- Outputs
- Runs
- Jobs
- Archive

**Acceptance:**
- The user can predict what each section means.
- Archive no longer has to carry both “old day snapshots” and “old important artifacts.”

## Non-Goals for First Pass

- Full database app.
- Auth redesign.
- Multi-user collaboration.
- Complex server-side search.
- Editing metadata from the browser.

## Definition of Done

- Hermes Agent Lanes / Hermes OS artifact appears in `/outputs` again.
- `/outputs` is persistent and catalog-backed.
- Cron runs have a separate `/runs` surface with history.
- Clicking an output opens the specific artifact, never today’s latest replacement.
- Archive semantics are explicit: day snapshots are not the output library.
- Tests cover catalog import, persistent output rendering, and run-history separation.

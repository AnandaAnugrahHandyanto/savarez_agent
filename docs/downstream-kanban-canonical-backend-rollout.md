# Downstream-only Kanban canonical backend rollout

Scope: Yunuen explicitly chose a downstream-only/local redesign for the Hermes Maintenance runtime. Do not open or route an upstream PR for this backend redesign without a new explicit review.

## Canonical backend target

Persist and expose canonical live/user statuses as first-class semantics:

- `working` — active work is underway or immediately spawnable.
- `waiting` — an active task/dependency waits on non-human/system action, including unfinished parents and schedules.
- `blocked` — human action is required; `blocked` is human-only.
- `dormant` — no active actionable assignment exists, such as unspecced triage with no active specifier.
- `done` — completion history, not profile availability.

Legacy values (`todo`, `ready`, `running`, `review`, `triage`, `scheduled`) are compatibility/storage aliases during rollout only. They must not be treated as canonical user-facing truth.

## Implementation sequence

1. Schema/runtime representation
   - Add a schema-versioned canonical task status field or new task state table for `working|waiting|blocked|dormant|done`.
   - Add a runtime/dispatch representation for spawnability, claim state, schedules, review-pending, and triage-needed.
   - Preserve `done` as terminal history; do not use it as a live availability state.

2. Compatibility adapter
   - Keep legacy dispatcher/storage aliases behind an explicit adapter boundary only.
   - Map old dispatcher reads from canonical state + runtime state, for example `working+spawnable -> ready`, `working+running -> running`, `waiting+parents_unfinished -> todo`, `waiting+scheduled -> scheduled`, `dormant+triage_needed -> triage`.
   - Reject new user/API writes of legacy aliases once dry-run backfill proves safe.

3. CLI/API/dashboard user-facing rendering
   - Render `Self status:` and `Lineage status:` with canonical vocabulary where profile status is reported.
   - Show canonical task status first in CLI/API/dashboard. If legacy storage is still present during migration, surface it only as explicit compatibility metadata.
   - Make list filters/counts/columns canonical, with legacy filters accepted only under a clearly named compatibility flag or endpoint.

4. Migration/backfill dry-run and rollback artifact
   - Before mutating any live Kanban DB, produce a deterministic backup path, a dry-run report of each row's old status, proposed canonical status, proposed runtime state, reason, and blocker-human audit outcome.
   - Produce rollback/export tooling that can materialize legacy statuses from canonical + runtime state for old runtimes.
   - Do not run old and new dispatchers against the same live DB concurrently.

5. Acceptance fixtures
   - Parent-gated child with unfinished or blocked parent reports canonical backend/user status `waiting`, not `todo`.
   - Completing/archiving all parents promotes a spawnable child to canonical `working`.
   - A blocked parent does not make descendants `blocked`; descendants remain `waiting` unless they themselves need human action.
   - Non-human blocker migration becomes `waiting`; human blockers remain `blocked`.

## First safe implementation slice in this branch

This branch implements only a non-invasive compatibility/projection slice:

- `hermes_cli.kanban_db.canonical_live_status()` maps legacy storage statuses to canonical downstream live statuses.
- `hermes_cli.kanban_db.canonical_live_status_for_task()` additionally treats any child with unfinished parents as canonical `waiting`, even if a legacy/racy row says `ready`.
- CLI JSON task payloads include `canonical_status`, and plain `kanban show` prints canonical status first with legacy storage status marked as compatibility metadata.
- Dashboard task dictionaries include `canonical_status` for frontend migration.
- Tests cover the observed parent-gated child regression without mutating live DB schema or live board data.

This is intentionally not the full backend redesign. It creates the adapter seam and acceptance fixture needed before the backup/dry-run/backfill slice.

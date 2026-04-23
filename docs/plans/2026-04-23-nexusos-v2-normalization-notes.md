# NexusOS v2 normalization notes

## Storage compatibility

NexusOS v2 keeps the file-backed project layout under:
- `HERMES_HOME/projects/people-manager/registry.json`
- `HERMES_HOME/projects/people-manager/reports/<slug>.json`
- `HERMES_HOME/projects/people-manager/schedules/one_on_ones.json`
- `HERMES_HOME/projects/people-manager/prep-queue/*.json`
- `HERMES_HOME/projects/people-manager/reminder-log/YYYY-MM.jsonl`

No DB migration was introduced.

## Report normalization

`people_manager.storage.load_report()` now normalizes older report files additively by filling missing defaults instead of requiring a destructive rewrite.

Notable additive behavior:
- missing nested sections are backfilled from `default_report()`
- `open_loops.current_focus_topics` is normalized in older/sparse reports
- `open_loop_items` is synthesized from legacy `open_loops` arrays when absent
- writes still persist plain JSON under the same report path

## Name resolution

Deterministic resolution is now:
1. exact normalized full name
2. exact slug
3. unique exact first-name match only

Removed behavior:
- prefix-style partial matches such as `Fi` -> `Fiona` no longer silently resolve

## Prep rendering

Ad hoc prep and scheduled prep now share one renderer path:
- scheduled title: `<Name> 1:1 in 5m`
- ad hoc title: `<Name> 1:1`

Shared bullets prefer ritual/topics/follow-through/watchouts/tone and fall back to a minimal note when context is sparse.

## Web surface

A thin `/api/people/*` layer now exposes profiles, prep, schedules, team scan, and ops over the shared people-manager core.

A first usable local dashboard is available at `/nexusos` on the Hermes web server.

## Deferred

Still intentionally deferred:
- frontend polish / rich SPA rewrite
- any HR / ATS / employee self-service concepts
- fuzzy/semantic entity resolution
- background automatic mutation from free-form chat

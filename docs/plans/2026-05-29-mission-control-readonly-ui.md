# Mission Control read-only UI controls

## Goal

Expose the approved read-only Mission Control actions in the dashboard UI without presenting unsafe write-style operations.

## Scope

- Add a Mission Control dashboard route and sidebar entry.
- Fetch and render only the approved read-only action ids from `GET /api/actions/read-only`.
- Let users run each approved action through `POST /api/actions/read-only/{action_id}/run`.
- Show loading, success/failure status, timestamps, summaries, raw output, and metadata.
- Add read-only external links for Grafana, Prometheus, Homepage, and Hindsight UI from dashboard configuration when present, with same-host fallbacks.

## Non-goals

- No restart, update, deploy, delete, write, install, enable, disable, pause, resume, or trigger controls.
- No direct shell command entry or user-supplied command execution.
- No change to the backend action allowlist semantics.

## Expected files

- `web/src/pages/MissionControlPage.tsx`
- `web/src/lib/api.ts`
- `web/src/App.tsx`

## Test/verification strategy

- Build the web dashboard with `npm run build`.
- Run focused backend tests for the read-only action API.
- Inspect the diff for unsafe action labels or mutating controls.

## Progress

- [x] Repo state inspected and existing feature branch reused.
- [x] Spec/plan written.
- [x] Read-only Mission Control UI implemented.
- [x] Web build passes.
- [x] Backend read-only action tests pass.
- [x] Diff reviewed for unsafe write-style actions.

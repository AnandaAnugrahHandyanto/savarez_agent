# Hermes AI Office — MVP Scope

Last updated: 2026-05-08 11:32 KST
Status: Product planning artifact. No implementation approved.

## MVP name

Working name: Hermes AI Office Read-Only Ops View.

## MVP goal

Provide a localhost browser dashboard view that answers, without mutating anything:

- what work is running,
- what is blocked or needs the user,
- what completed recently,
- which automation/cron jobs are healthy or failing,
- which Telegram topics are associated with work streams,
- which Hermes board/assignee/profile owns each task.

## In scope

### Read-only overview

- Summary counts: running, blocked, ready, todo, done, failed automation.
- Board list with per-status counts.
- Active/blocked tasks first.
- Assignee/profile field if available.
- Parent/child dependency indicator if available.

### Automation panel

- Cron job name.
- Schedule.
- Last run / next run if available.
- Last status/error if available.
- Delivery target redacted to safe platform/topic display.
- `no_agent` vs LLM job classification if available.

### Telegram topic map

- Known local mapping, initially read-only:
  - Hermes Hub `-1003775710032`
  - `00-운영실` thread `2`
  - `70-자동화` thread `11`
- Display topic names and purposes, not secrets.
- Show when a task/job has known source/delivery topic metadata.
- Show “unknown” when provenance is absent.

### Task inspector

- Task id/title/status/board/assignee.
- Safe timestamps.
- Dependencies.
- Safe event summaries.
- Link/reference to session id if safe and available.
- No raw transcript by default.

### Handoff visibility

- Link or display current `docs/ai-office/STATUS.md` and `NEXT.md` in later read-only panel if simple.
- Do not make dashboard startup depend on NAS/Obsidian sync.

## Out of scope for MVP

- Pixel/game renderer.
- Creating/editing/reassigning/retrying tasks from browser.
- Running cron jobs from browser.
- Gateway restart or service controls.
- Public network exposure.
- Raw transcript browsing.
- LLM-generated speech bubbles.
- Automatic incident task creation.
- Obsidian/NAS writes.
- New autonomous planning engine.

## Acceptance criteria

MVP is acceptable only if:

1. Dashboard remains local/read-only.
2. No secrets or credential files are exposed.
3. Missing provenance is shown honestly as missing/unknown.
4. Existing embedded `hermes --tui` dashboard chat is not replaced or reimplemented.
5. UI degrades gracefully when Kanban/cron/gateway data is unavailable.
6. Focused tests cover serializers/API redaction before user-visible rollout.
7. User explicitly approves implementation before any code change begins.

## Post-MVP sequence

1. Provenance capture implementation.
2. Pixel office renderer.
3. Event-driven live updates.
4. User-controlled browser actions after security review.
5. Multi-device/NAS/Obsidian read-only panels.

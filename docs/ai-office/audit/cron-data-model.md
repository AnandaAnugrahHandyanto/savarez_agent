# Hermes AI Office — Cron Data Model Audit

Last updated: 2026-05-08 11:44 KST
Status: Stage 2 read-only audit. No cron jobs were created, updated, triggered, paused, resumed, or deleted.

## Scope

Audit Hermes scheduled job storage/execution/delivery surfaces for a future read-only AI Office view.

Primary files inspected:

- `cron/jobs.py`
- `cron/scheduler.py`
- `hermes_cli/cron.py`
- `hermes_cli/web_server.py`
- `web/src/pages/CronPage.tsx`
- `web/src/lib/api.ts`

## Storage

Cron jobs are JSON-backed, not SQLite-backed.

Current code constants:

- jobs file: `~/.hermes/cron/jobs.json`
- output dir: `~/.hermes/cron/output/{job_id}/{timestamp}.md`
- tick lock: `~/.hermes/cron/.tick.lock`

Current WSL runtime paths observed:

- `/home/lidises/.hermes/cron/jobs.json`
- `/home/lidises/.hermes/cron/output/`

## Current live job snapshot

Read-only snapshot on 2026-05-08 11:44 KST:

- job count: 1
- job id: `70378c4d2890`
- name: `daily-hermes-health-digest`
- schedule: cron `0 8 * * *`
- enabled: true
- state: `scheduled`
- deliver: `telegram:-1003775710032:11`
- last_status: `error`
- last_run_at: `2026-05-08T09:05:41.840217+09:00`
- next_run_at: `2026-05-09T08:00:00+09:00`
- last_error: `Script timed out after 120s: /home/lidises/.hermes/scripts/hermes_daily_health_digest.py`
- last_delivery_error: null

No secrets were read or included.

## Schedule model

`cron/jobs.py::parse_schedule` normalizes schedules into dicts:

- `kind: once`, with `run_at`
- `kind: interval`, with `minutes`
- `kind: cron`, with `expr`
- `display` human-readable string

Accepted user strings include:

- duration one-shot: `30m`, `2h`, `1d`
- interval recurring: `every 30m`, `every 2h`
- cron expressions: `0 9 * * *`
- ISO timestamps: `2026-02-03T14:00:00`

Cron expressions require `croniter`.

## Job fields relevant to AI Office

From `cron.jobs`, `cron.scheduler`, and dashboard API usage, important fields include:

Identity/control:

- `id`
- `name`
- `prompt`
- `schedule`
- `enabled`
- `state`
- `repeat`

Execution routing:

- `deliver`
- `origin`
- `skills`
- `model`
- `script`
- `no_agent`
- `context_from`
- `enabled_toolsets`
- `workdir`

Run health:

- `last_run_at`
- `next_run_at`
- `last_status`
- `last_error`
- `last_delivery_error`

Output/audit:

- saved Markdown outputs under `cron/output/{job_id}/`.

## Dashboard API

Existing built-in dashboard endpoints:

- `GET /api/cron/jobs`
- `GET /api/cron/jobs/{job_id}`
- `POST /api/cron/jobs`
- `PUT /api/cron/jobs/{job_id}`
- `POST /api/cron/jobs/{job_id}/pause`
- `POST /api/cron/jobs/{job_id}/resume`
- `POST /api/cron/jobs/{job_id}/trigger`
- `DELETE /api/cron/jobs/{job_id}`

`web/src/pages/CronPage.tsx` currently uses list/create/pause/resume/trigger/delete with a form containing:

- `prompt`
- `schedule`
- `name`
- `deliver`

The page default delivery target is `local`, but the live job uses a Telegram topic target.

## Scheduler execution model

`cron/scheduler.py` provides `tick()`, called by the gateway every 60 seconds according to module comments. It uses a file-based lock so overlapping processes do not run duplicate ticks.

Important execution features:

- Per-job toolset resolution checks job-level `enabled_toolsets`, then cron platform tool config, then full defaults as fallback.
- Delivery targets support `local`, `origin`, platform names, explicit platform targets such as `telegram:<chat>:<thread>`, and comma-separated combinations.
- Delivery preserves `thread_id` where present and logs warning if origin had a thread but delivery target loses it.
- Live gateway adapter delivery is preferred when available; standalone send path is fallback.
- `MEDIA:` tags are extracted and sent as platform-native files in gateway contexts.
- Script jobs are restricted to `HERMES_HOME/scripts/`, preventing arbitrary path traversal.
- Script timeout default is 120s, configurable by env/config.
- Script stdout/stderr is redacted before being injected/reported.
- `context_from` can inject latest saved output from upstream cron jobs, truncated to 8K chars.
- Cron prompt includes explicit `[SILENT]` behavior guidance.

## Run-state update behavior

`mark_job_run` in `cron/jobs.py` tracks agent errors and delivery errors separately:

- `last_status = ok|error`
- `last_error` for agent/script/job failure
- `last_delivery_error` for delivery failure

Recurring jobs are not silently disabled if next run computation fails. They remain enabled with `state="error"` and a diagnostic, e.g. missing `croniter`.

One-shot jobs with no next run are disabled and marked `state="completed"`.

## Fit for AI Office MVP

Recommended office rendering:

- Cron jobs as automation bots or scheduled machines.
- `state=scheduled/enabled` as idle/healthy.
- `last_status=error` or non-null `last_error` as warning badge.
- `next_run_at` as next wake time.
- `deliver` target as room/topic linkage, redacted or normalized for display.
- Saved outputs as audit artifacts, not default visible speech bubbles.

## Gaps

- Cron jobs are JSON objects, while sessions and Kanban use SQLite. A read-only aggregator must normalize across storage types.
- No first-class run-history table; recent history is mostly current fields plus output files unless additional logs are parsed.
- `deliver` embeds routing strings; it should be parsed into structured `platform/chat_id/thread_id` for AI Office.
- Cron outputs/prompts may contain sensitive content. Office view should show status/health first and require explicit drill-down for output content.
- Current live job has a script timeout error; AI Office should surface this as automation health issue, not silently hide it.

## Recommendation for Stage 4 provenance design

Represent cron jobs in `OfficeState` as scheduled actors with structured fields:

- `job_id`, `name`, `state`, `enabled`
- `schedule_kind`, `schedule_display`, `next_run_at`
- `last_run_at`, `last_status`, `last_error_summary`, `last_delivery_error_summary`
- `delivery_targets`: parsed list of `{platform, chat_id, thread_id, label?}`
- `origin`: parsed when present
- `output_artifacts`: paths/counts only by default, not raw contents

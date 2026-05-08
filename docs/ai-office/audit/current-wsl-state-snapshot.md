# Hermes AI Office — Current WSL State Snapshot

Last updated: 2026-05-08 11:44 KST
Status: Stage 2 read-only audit. No services were restarted and no config was changed.

## Scope

Capture the current local WSL Hermes runtime state relevant to AI Office planning.

Commands were read-only. No secrets, tokens, or environment variable values were printed.

## Host/runtime

Observed on 2026-05-08 11:44:17 KST:

- Working directory: `/home/lidises/hermes-agent`
- Hermes home: `/home/lidises/.hermes`
- OS/kernel: Linux under WSL2, kernel `5.15.167.4-microsoft-standard-WSL2`
- Architecture: `x86_64`
- Python: `Python 3.12.3`
- Hermes executable: `/home/lidises/hermes-agent/.venv/bin/hermes`

## Git checkout

Observed read-only:

- Branch: `main`
- HEAD: `99bdaae8d`
- `git status --short` line count: 2

Note: This differs from the older memory note that referenced local hotfix `902d99b87`; the live checkout at audit time reported `99bdaae8d`. This audit did not inspect the two status lines to avoid drifting into unrelated repo cleanup.

## Gateway service

User systemd service state observed read-only:

- Service: `hermes-gateway.service`
- Active state: `active`
- Enabled state: `enabled`
- MainPID: `5165`

No restart was performed.

## Session database

State DB:

- Path: `/home/lidises/.hermes/state.db`
- Exists: yes

Counts observed read-only:

- Total sessions: 143
- Total messages: 10,443
- Sessions by source:
  - `cli`: 119
  - `telegram`: 24

Implication for AI Office: there is enough existing session data to test metadata-only session summaries, but raw transcript exposure remains a privacy risk.

## Cron state

Cron jobs file:

- Path: `/home/lidises/.hermes/cron/jobs.json`
- Exists: yes
- Job count: 1

Current job:

- id: `70378c4d2890`
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

Implication for AI Office: cron health panel should show this as a scheduled automation with a recent script timeout warning.

## Kanban state

Kanban boards directory:

- `/home/lidises/.hermes/kanban/boards`

Observed boards and counts:

- `hermes-runtime`
  - blocked: 2
  - done: 3
  - notify_subs: 0
- `koreandeer-content`
  - done: 2
  - ready: 1
  - todo: 3
  - notify_subs: 0
- `obsidian-ledger`
  - blocked: 3
  - notify_subs: 0

No board/task mutation was performed.

## Known Telegram routing context

From persistent local memory and cron snapshot:

- Telegram Hermes Hub chat id: `-1003775710032`
- `00-운영실` thread id: `2`
- `70-자동화` thread id: `11`
- Current cron job delivers to `telegram:-1003775710032:11`

Implication for AI Office: these can be used as manual labels during planning, but implementation should use a proper topic registry rather than hardcoding memory facts.

## Current planning implication

The local system already has enough live data for a read-only office MVP prototype later:

- active gateway service
- populated session DB
- one scheduled cron job with a meaningful error state
- multiple Kanban boards with blocked/ready/todo/done counts
- known Telegram topic routing for operations and automation

The immediate blocker is not lack of data; it is the lack of a normalized, privacy-preserving aggregation/provenance model.

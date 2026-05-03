# BusinessOS Architecture and Operations Guide

## Purpose

This document describes how the current BusinessOS system is structured, what is actually working on disk today, how the moving pieces fit together, and where the main operational boundaries are.

Canonical workspace root:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS`

Dropbox mirror root:
- `/home/yuiop/Dropbox/BusinessOS`

## Design principles

BusinessOS follows a local-first design.

Key principles:
- the filesystem is the canonical archive
- SQLite is the query/reporting layer
- raw artifacts are preserved for auditability
- normalized artifacts make reprocessing easier
- Dropbox is a one-way mirror target, not the primary source of truth
- automation should fail safely and visibly rather than silently pretending to ingest live data

## High-level architecture

BusinessOS currently has four practical layers.

### 1. Intake artifact layer
This layer stores original incoming artifacts as close to source form as possible.

Examples:
- raw Telegram JSON under `00_INBOX/communications/telegram/raw/`
- raw email `.eml` files under `00_INBOX/communications/email/raw/`
- email attachments under `00_INBOX/communications/email/attachments/`
- manual operator document drops under `00_INBOX/manual-drop/`

Primary purpose:
- preserve the original evidence
- support audit/reprocessing/debugging

### 2. Structured archive layer
This layer organizes business documents and structured entity metadata.

Examples:
- `01_DOCUMENTS/`
- `02_ENTITIES/email-accounts/`
- `02_ENTITIES/services/`
- `02_ENTITIES/websites/`

Primary purpose:
- keep durable business records in deterministic filesystem locations

### 3. Knowledge/index layer
This is the SQLite-backed stateful operations layer.

DB path:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/03_DATA/db/businessos.db`

Important current tables:
- `documents`
- `expense_tax_treatment`
- `communication_threads`
- `communication_messages`
- `task_items`
- `task_comments`
- `task_documents`
- `task_events`
- `feedback_items`
- `feedback_clusters`
- `bug_candidates`
- `feature_candidates`
- `source_accounts`
- `ingestion_checkpoints`
- `pipeline_runs`
- `operator_notifications`
- `daily_summary_reports`

Current observed counts at the time of documentation:
- `documents`: 1
- `communication_threads`: 23
- `communication_messages`: 34
- `feedback_items`: 36
- `feedback_clusters`: 14
- `bug_candidates`: 2
- `feature_candidates`: 0
- `source_accounts`: 3
- `ingestion_checkpoints`: 2

### 4. Reporting and automation layer
This layer generates operational summaries and mirrors them into Dropbox.

Main report locations:
- `05_REPORTS/support/`
- `05_REPORTS/tasks/`
- `05_REPORTS/monthly/`
- `05_REPORTS/daily/`
- `05_REPORTS/product/`

Main current automation scripts:
- `04_AUTOMATIONS/scripts/run_support_pipeline.py`
- `04_AUTOMATIONS/scripts/build_support_readiness_report.py`
- `04_AUTOMATIONS/scripts/build_support_health_report.py`
- `04_AUTOMATIONS/scripts/manage_tasks.py`
- `04_AUTOMATIONS/scripts/mirror_to_dropbox.py`
- `04_AUTOMATIONS/scripts/operator_updates.py`
- `04_AUTOMATIONS/scripts/poll_telegram_updates.py`

Current config:
- `04_AUTOMATIONS/configs/dropbox-mirror.yaml`
- `04_AUTOMATIONS/configs/operator-updates.yaml`

## Current data flow

The currently-restored flow is:

1. `poll_support_email.py` polls the configured live IMAP inbox and records new mail
2. `poll_telegram_updates.py` polls the configured Steady Telegram support group with `getUpdates`
3. task-formatted emails and Telegram messages can create or update tasks in SQLite
4. email attachments and manual-drop documents are auto-filed into `01_DOCUMENTS/` with metadata sidecars
5. the task dashboard/transcript layer writes the current task queue and task histories
6. the finance reporting layer writes income/expense and deductible summaries
7. `build_support_readiness_report.py` inspects the on-disk script/config/env surface and writes a readiness audit
8. `build_support_health_report.py` summarizes:
   - source checkpoints
   - queue counts / needs-reply counts
   - latest messages
9. `operator_updates.py` records pipeline run state, sends operator Telegram updates, and writes/sends previous-day summary reports
10. the reports are written into `05_REPORTS/support/`, `05_REPORTS/tasks/`, `05_REPORTS/monthly/`, and `05_REPORTS/daily/`
11. `mirror_to_dropbox.py` mirrors configured subtrees into Dropbox
12. a systemd service/timer can run the wrapper unattended every 15 minutes

That means the current automated flow is now:
- poll live intake
- file manual and email-sourced business documents
- keep a task ledger with reminders/comments/document links
- generate finance/tax summaries
- record raw and normalized artifacts
- summarize current state
- mirror current state

It is still not the full historical flow of:
- rebuild clusters
- generate candidates
- rebuild all downstream reports
- export reply drafts
- mirror everything

## Source accounts and checkpoints

Current known source accounts in the DB:
- `helix-admin` (email)
- `telegram-steady-support` (telegram)
- `telegram-support-main` (legacy telegram row)

Current known checkpoints:
- `email / helix-admin`
- `telegram / telegram-steady-support`

Interpretation:
- the DB still preserves evidence of real prior ingestion work
- the current on-disk script set now reproduces live intake for the Helix email lane and Steady Telegram support lane
- older richer downstream rebuild/export behaviors referenced in prior sessions are still separate restoration work

## Reporting model

### Support operations summary
The support summary report is intended to answer:
- what is urgent?
- how many open threads exist by source?
- which queues need reply?
- how much admin/system traffic is present?

Recent support reports include files like:
- `2026-05-02-support-operations-summary.md`

### Support health check
The support health check is newer and intentionally operational.

It answers:
- what happened in the current pipeline run?
- how many new items were imported per source in that run?
- what are the latest sent/imported message timestamps by source?
- when did each source last advance?
- how stale are the checkpoints?
- which queues currently have needs-reply pressure?
- what are the newest visible messages?

Recent example:
- `2026-05-02-support-health-check.md`

### Task dashboard and transcripts
The task dashboard/reporting layer is intended to answer:
- what business/admin work is currently open?
- which tasks are in `created`, `in_progress`, or `completed` status?
- which reminders are pending?
- which documents and comments belong to a specific task?

Paths:
- `05_REPORTS/tasks/2026-05-02-task-dashboard.md`
- `05_REPORTS/tasks/transcripts/task-0001.md`

### Finance and deductible summaries
The finance reporting layer is intended to answer:
- what business income has been recorded?
- what business expenses have been recorded?
- which deductible category does each expense appear to belong to?
- what totals should be easy to review at tax time?

Paths:
- `05_REPORTS/monthly/2026-05-02-finance-summary.md`
- `05_REPORTS/monthly/2026-05-02-deductible-summary.md`

### Support readiness audit
The support readiness audit is the pipeline-surface reality check.

It answers:
- which live-ingestion scripts are actually present on disk right now?
- is the Telegram script a real `getUpdates` poller?
- are the expected email/Telegram config files present?
- which source accounts and checkpoints still exist in the DB from historical ingestion?

Recent example:
- `2026-05-02-support-readiness-audit.md`

### Product reports
Product reports summarize product-facing feedback patterns and candidates.

Recent files exist under:
- `05_REPORTS/product/`

## Queueing and separation logic

A key design requirement has been keeping internal/operator behavior separate from real customer support.

Important policy:
- operator self-tests should not pollute real support threads
- internal admin traffic should be kept out of customer-facing urgent/support views where possible
- customer-facing support should remain actionable for human follow-up
- owner/operator Telegram control traffic should live on a separate operator-control lane from the customer-facing support bot

See also:
- `docs/communications-lane-policy.md`

Why this matters:
- the same person may send both internal tests and real user-facing content
- without thread separation and queue separation, internal flags like no-reply/admin can contaminate real support state

Operationally, BusinessOS has already been used with this principle in mind, and the current reports reflect separate admin/internal categories.

## Dropbox mirror architecture

Dropbox is used as a convenience sync/mirror layer.

Config path:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/04_AUTOMATIONS/configs/dropbox-mirror.yaml`

Current included paths:
- `01_DOCUMENTS`
- `02_ENTITIES`
- `03_DATA/exports`
- `03_DATA/metadata`
- `03_DATA/normalized`
- `05_REPORTS`

Current prune mode:
- `false`

Meaning:
- the mirror is conservative
- it avoids destructive deletion by default
- it focuses on durable outputs and structured artifacts rather than treating Dropbox as the live working database

## Scheduled automation

BusinessOS currently uses a user-level systemd timer pattern.

Wrapper:
- `/home/yuiop/.local/bin/businessos-support-pipeline.sh`

Service:
- `/home/yuiop/.config/systemd/user/businessos-support-pipeline.service`

Timer:
- `/home/yuiop/.config/systemd/user/businessos-support-pipeline.timer`

Schedule:
- every 15 minutes

Responsibilities of the wrapper:
- enter the Hermes checkout working directory
- load the local env file if present
- log output into the BusinessOS state log location
- fail early if a required env variable is missing
- invoke the pipeline entrypoint with the project virtualenv Python

Why systemd is the right current pattern here:
- better visibility than cron
- easier status inspection
- cleaner reruns
- persistent scheduling behavior

## Current scripts and what they actually do

### `run_support_pipeline.py`
Current role:
- live pipeline entrypoint
- runs the configured email poller when its script/config/env are present
- runs the configured Telegram poller when its script/config/env are present
- scans the manual document inbox
- files new business documents and updates finance/tax reports
- rebuilds the task dashboard and task transcripts
- writes the readiness and health reports
- runs Dropbox mirroring


Important nuance:
- the pipeline now restores fresh intake for the current live email + Telegram lanes
- it still does not recreate the older fuller cluster/candidate/export chain from prior sessions

### `build_support_readiness_report.py`
Current role:
- inspects the on-disk pipeline surface rather than only the DB contents
- reports whether email and Telegram live-ingestion components are present
- records whether the expected config files and wrapper env file exist
- helps explain whether recent checkpoint movement came from a runnable on-disk pipeline or older historical state

### `build_support_health_report.py`
Current role:
- reads `ingestion_checkpoints`, `communication_threads`, and `communication_messages`
- writes a support-health markdown report

### `mirror_to_dropbox.py`
Current role:
- reads YAML config
- copies only configured subtrees
- skips unchanged files
- optionally prunes, but current config keeps prune disabled

### `poll_support_email.py`
Current role:
- polls the configured Helix IMAP inbox for fresh messages
- routes known aliases into their support/admin/legal/privacy/billing queues
- writes raw email artifacts, normalized JSON, DB rows, and checkpoint updates

### `poll_telegram_updates.py`
Current role:
- polls the configured Steady support group through Telegram `getUpdates`
- separates obvious operator self-tests into internal/admin traffic
- writes raw Telegram JSON, normalized JSON, DB rows, and checkpoint updates
- still includes the privacy-mode warning helper so Telegram group-access issues remain diagnosable

## What is real today vs what is historical context

Real and working now:
- BusinessOS directory structure
- SQLite DB with real data
- support and product report artifacts on disk
- live support email polling
- live Telegram support polling
- support health check generation
- Dropbox mirror script and config
- user-level scheduled service/timer
- operator docs in `docs/`

Historical / partially-restored context:
- prior sessions referenced a fuller live pipeline with additional downstream scripts
- the DB and reports show that richer behavior existed at some point
- those older downstream rebuild/export scripts are not all present in the current filesystem snapshot

This distinction matters because fresh live intake can be restored before every historical downstream processing stage is restored.

## Operational audit checklist

When evaluating whether BusinessOS is healthy, check these in order:

1. Confirm the canonical root exists
2. Confirm the DB exists
3. Confirm the latest support health check exists
4. Confirm the latest support operations summary exists
5. Confirm the Dropbox root exists
6. Confirm the systemd timer is active
7. Manually trigger the service once after changes
8. Confirm the status shows success
9. Verify the newest report was mirrored into Dropbox
10. Inspect whether the scripts referenced by the wrapper actually exist on disk

This prevents the common false-positive state where:
- the timer is enabled
- but the wrapper points to a missing script
- so every scheduled run fails

## How the system should be used right now

Best use cases today:
- local archive of business/admin/support artifacts
- live support intake + reporting workspace
- checkpoint/health monitoring workspace
- Dropbox-mirrored reporting/output workspace
- foundation for restoring fuller downstream rebuild/export steps later

Still not the best use case today:
- assuming the older cluster/candidate/draft-export chain from prior sessions is fully restored

## Next restoration priorities

When resuming engineering work, the most valuable next steps are:

1. restore cluster/candidate/report rebuild steps into the pipeline entrypoint
2. reintroduce draft-export steps if desired
3. extend tests around richer downstream processing
4. keep the health-check and mirror steps as part of the final pipeline

## Recommended operator posture

Treat the current system as:
- trustworthy for local state inspection
- trustworthy for current live email + Telegram intake
- trustworthy for current report generation and mirroring
- useful for support/admin operations review
- still incomplete only in the richer downstream rebuild/export layers

## Related docs

- `docs/user-manual.md`

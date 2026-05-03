# BusinessOS User Manual

## What this system is

BusinessOS is a local-first operations workspace for Steady and related business/admin work.

The system currently gives you:
- a canonical local filesystem archive
- a SQLite database for support/product/admin records
- raw and normalized intake artifacts for auditability
- automatic document filing from manual drops and forwarded email attachments
- task tracking with status, comments, reminders, and task-document links
- finance/tax summaries for business income and expenses
- support and product reports on disk
- operator Telegram updates during pipeline activity, including item-level detail for imported email/Telegram items, BusinessOS classification labels, processed documents, and Dropbox copied paths
- previous-day daily summary reports with a stored ledger for later mining
- a Dropbox mirror for selected outputs
- a scheduled health-check pipeline that refreshes operational visibility

Canonical local root:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS`

Dropbox mirror root:
- `/home/yuiop/Dropbox/BusinessOS`

## Current status in plain English

As of now, BusinessOS is good for:
- polling the live Helix support inbox over IMAP
- polling the live Steady support Telegram group with `getUpdates`
- scanning `00_INBOX/manual-drop/` for documents to auto-file
- auto-classifying forwarded business email attachments into `01_DOCUMENTS/`
- creating tasks from CLI, email subjects like `TODO: ...`, and Telegram messages like `/todo ...`
- storing task comments, status changes, reminders, and linked documents in the DB + transcript files
- generating a task dashboard and finance/tax summaries on each pipeline run
- reviewing support state
- reviewing queue workload
- checking intake freshness
- inspecting raw and normalized support artifacts
- mirroring important outputs into Dropbox

Important limitation:
- the current scheduled pipeline now restores live email + Telegram intake, health reporting, readiness reporting, and Dropbox mirroring
- it still is not the full previously-described rebuild stack for clustering, candidate generation, and reply-draft exports

So: fresh live ingestion is back for the current email and Telegram lanes, while the richer downstream rebuild chain is still a later restoration step.

## Folder layout

Main folders under the BusinessOS root:

- `00_INBOX/`
  - raw intake artifacts
  - example: raw Telegram JSON and raw email artifacts
- `01_DOCUMENTS/`
  - filed business documents
- `02_ENTITIES/`
  - structured entity records such as email accounts, services, websites
- `03_DATA/`
  - SQLite DB, normalized data, imports, exports, extracted text
- `04_AUTOMATIONS/`
  - scripts and configs
- `05_REPORTS/`
  - generated reports
- `99_ARCHIVE/`
  - reserved archive space
- `docs/`
  - operator documentation

## The most important places to look

### 1. Support readiness audit
Use this first when you want to know whether the current on-disk pipeline is wired for fresh support ingestion and whether the required scripts/config/env surfaces are present.

Path example:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/support/2026-05-02-support-readiness-audit.md`

This report shows:
- whether the live email poller script is present
- whether the Telegram script is a real `getUpdates` poller
- whether the expected email/Telegram config files exist
- whether the wrapper env file and key env-var names are present
- which source accounts and checkpoints still exist in the DB

Use it to answer:
- Is the current filesystem snapshot ready for fresh live intake?
- Are the current checkpoints advancing after a run?
- Am I looking at old DB state or recent pipeline activity?

### 2. Support health check
Use this when you want to know whether the system looks alive at the data/reporting level.

Path example:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/support/2026-05-02-support-health-check.md`

This report shows:
- a current pipeline run summary
- per-source new imports for that run
- latest message sent/imported timestamps by source
- source checkpoints
- checkpoint age
- queue snapshot
- latest messages

Use it to answer:
- Is intake moving?
- Which queues need reply?
- What was the latest support activity?

### 3. Support operations summary
Use this to understand triage and workload.

Path example:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/support/2026-05-02-support-operations-summary.md`

This report shows:
- urgent threads
- open thread counts
- queue workload summary
- queue SLA/reply-focus view
- administrative/system-message counts

### 4. Task dashboard
Use this to review the current todo queue and reminder schedule.

Path example:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/tasks/2026-05-02-task-dashboard.md`

This report shows:
- all tracked tasks
- current task status
- reminder/due timestamps
- today's explicit priorities
- suggested follow-up items inferred from non-task intake
- pending reminder rows

### 5. Finance summary
Use this to review business income/expense records and deductible categories.

Path examples:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/monthly/2026-05-02-finance-summary.md`
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/monthly/2026-05-02-deductible-summary.md`

These reports show:
- total business income
- total business expenses
- per-document ledger rows
- deductible totals by federal/NJ category

### 6. Daily summary ledger
Use this to review the previous local day's work/action and to mine accumulated daily summaries over time.

Path example:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/daily/2026-05-02-daily-summary.md`

This report shows:
- prior-day pipeline activity
- imported communications totals
- new/updated task activity
- newly recorded expense activity
- remaining open work carried into today
- today's explicitly recorded priorities
- suggested follow-up items inferred from non-task intake
- a highlight list of notable captured work

The underlying ledger is also stored in SQLite table:
- `daily_summary_reports`

### 7. Product feedback summary
Use this to review product-level themes and bug pressure.

Recent location:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/product/`

### 8. Raw intake artifacts
Use raw artifacts when you want the original evidence.

Examples:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/00_INBOX/communications/telegram/raw/`
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/00_INBOX/communications/email/raw/`

### 8. Normalized artifacts
Use normalized artifacts when you want structured per-message data.

Example:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/03_DATA/normalized/`

### 9. Database
Use the SQLite DB when you want structured querying.

Path:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/03_DATA/db/businessos.db`

## Day-to-day usage

### Check the latest system state
1. Open the latest support readiness audit in `05_REPORTS/support/`
2. Open the latest support health check in `05_REPORTS/support/`
3. Open the latest support operations summary in `05_REPORTS/support/`
4. Open the latest task dashboard in `05_REPORTS/tasks/`
5. Open the latest finance summary in `05_REPORTS/monthly/`
4. If needed, inspect the corresponding raw/normalized artifacts

### Manually run the live pipeline
Run this when you want to ingest fresh mail + Telegram updates, refresh the reports, and mirror the latest outputs.

Command:
- `cd /home/yuiop/.hermes/hermes-agent && set -a && source /home/yuiop/.config/businessos/support-email.env >/dev/null 2>&1 && set +a && venv/bin/python BusinessOS/04_AUTOMATIONS/scripts/run_support_pipeline.py`

What it currently does:
- polls the configured live email inbox over IMAP
- polls the configured Steady Telegram support group via `getUpdates`
- scans `00_INBOX/manual-drop/` and files new documents into `01_DOCUMENTS/`
- auto-processes forwarded email attachments as business documents
- creates/updates tasks from task-formatted email and Telegram messages
- records today's priorities from `/focus ...`, `Focus: ...`, `/priority ...`, or `Priority: ...`
- writes non-committing suggested follow-up items for non-task intake instead of auto-creating tasks
- writes a task dashboard and per-task transcript files
- writes finance and deductible expense summaries
- writes a previous-day daily summary report on the first eligible morning run, including remaining open work and today's priorities
- sends operator Telegram updates for run start, significant intake activity, and run completion
- writes a fresh support readiness audit
- writes a fresh support health check
- runs Dropbox mirroring
- prints a JSON result summary

### Drop in a business document manually
1. Put the file under `00_INBOX/manual-drop/`
2. Run the pipeline manually or wait for the next scheduled run
3. Check `01_DOCUMENTS/` for the filed copy
4. Check `03_DATA/metadata/` for the sidecar metadata
5. Check `05_REPORTS/monthly/` for the updated finance/tax summaries if the document was an income/expense record

### Create a task by email or Telegram
Supported task-creation formats:
- Email subject: `TODO: Reconcile April receipts`
- Telegram message: `/todo Reconcile April receipts`

Supported daily-priority formats:
- Email subject: `Focus: task-0001`
- Email subject: `Priority: Finish Play Console registration`
- Telegram message: `/focus task-0001`
- Telegram message: `/priority Finish Play Console registration`

Optional body lines for email or Telegram:
- `Due: 2026-05-15T17:00:00-04:00`
- `Reminder: 2026-05-14T09:00:00-04:00`

Task update formats:
- `/task task-0001 start`
- `/task task-0001 done`
- `/task task-0001 comment Waiting on accountant reply`

### Create or update a task from the CLI
Examples:
- `cd /home/yuiop/.hermes/hermes-agent && venv/bin/python BusinessOS/04_AUTOMATIONS/scripts/manage_tasks.py add --title "Reconcile April receipts" --description "Match all Helix/Steady receipts" --reminder-at 2026-05-14T09:00:00-04:00`
- `cd /home/yuiop/.hermes/hermes-agent && venv/bin/python BusinessOS/04_AUTOMATIONS/scripts/manage_tasks.py status task-0001 in_progress`
- `cd /home/yuiop/.hermes/hermes-agent && venv/bin/python BusinessOS/04_AUTOMATIONS/scripts/manage_tasks.py comment task-0001 "Waiting on invoice attachment"`

### Link a document to a task and review the transcript
1. Use the CLI link command or send a task-formatted email with attachments
2. The document-task relationship is stored in SQLite
3. The task transcript is written under `05_REPORTS/tasks/transcripts/`

Example transcript path:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/05_REPORTS/tasks/transcripts/task-0001.md`

### Run Dropbox mirroring only
Command:
- `cd /home/yuiop/.hermes/hermes-agent && venv/bin/python BusinessOS/04_AUTOMATIONS/scripts/mirror_to_dropbox.py`

Mirror config:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS/04_AUTOMATIONS/configs/dropbox-mirror.yaml`

Current mirrored areas:
- `01_DOCUMENTS`
- `02_ENTITIES`
- `03_DATA/exports`
- `03_DATA/metadata`
- `03_DATA/normalized`
- `05_REPORTS`

### Check scheduled automation
The system uses a user-level systemd service and timer.

Service:
- `/home/yuiop/.config/systemd/user/businessos-support-pipeline.service`

Timer:
- `/home/yuiop/.config/systemd/user/businessos-support-pipeline.timer`

Wrapper:
- `/home/yuiop/.local/bin/businessos-support-pipeline.sh`

Useful commands:
- `systemctl --user status businessos-support-pipeline.service --no-pager -l`
- `systemctl --user list-timers --all | grep -i businessos`
- `systemctl --user start businessos-support-pipeline.service`

### Check Dropbox sync health
Useful command:
- `dropbox status`

Expected healthy result:
- `Up to date`

## How to interpret current data

### Queue meaning
From the current reports, queues include things like:
- `urgent`
- `billing-support`
- `general`
- `community-support`
- `customer-support`
- `legal-review`
- `privacy-review`
- `admin`

Practical interpretation:
- `urgent` means fast human attention
- `admin` is for internal/system/operator-oriented items
- queue-specific lanes help keep billing/legal/privacy/support work from collapsing into one pile

### Operator/internal test separation
BusinessOS has previously been hardened so operator self-tests do not pollute customer support state.

Meaning:
- obvious operator self-tests should land as internal/admin traffic
- real customer-facing support should remain in customer support flow
- this prevents the same sender from contaminating a real thread with admin/no-reply state

## Typical operator workflows

### Workflow A: Morning support check
1. Open the latest support health check
2. Open the latest support operations summary
3. Review queues with `Needs reply`
4. Drill into raw/normalized artifacts if anything looks ambiguous

### Workflow B: Validate that a support message made it through
1. Open the latest support readiness audit first to confirm the live email/Telegram lane is configured on disk
2. Find the latest message in the health check or support summary
3. Check the raw artifact under `00_INBOX/.../raw/`
4. Check the normalized artifact under `03_DATA/normalized/...`
5. If needed, query the DB for the related thread/message

### Workflow C: Refresh outputs before reviewing Dropbox
1. Run the live pipeline manually
2. Confirm the generated report path printed in the JSON output
3. Confirm the mirrored file appears under `/home/yuiop/Dropbox/BusinessOS/`

### Workflow D: Capture a receipt or invoice for taxes
1. Drop the file into `00_INBOX/manual-drop/` or forward the email with its attachment into the monitored inbox
2. Run the pipeline or wait for the next scheduled run
3. Confirm the document was filed under `01_DOCUMENTS/finance/...`
4. Confirm the metadata sidecar exists under `03_DATA/metadata/`
5. Open the latest finance and deductible summaries under `05_REPORTS/monthly/`

### Workflow E: Track a business task with supporting documents
1. Create the task from CLI, email, or Telegram
2. Add comments/status updates as work progresses
3. Link related documents by attachment or CLI link command
4. Open the task dashboard for the current queue view
5. Open the task transcript if you need the full operations history for that task

## Safety model

BusinessOS is intentionally local-first.

Rules to remember:
- local storage is canonical
- Dropbox is a mirror, not the source of truth
- do not put secrets into repo config files
- use the local env file / wrapper pattern for unattended runs
- treat live email sending, schema changes, and production automation changes as safe-mode operations

## Known limitations

Current on-disk automation scripts include:
- `run_support_pipeline.py`
- `build_support_readiness_report.py`
- `manage_tasks.py`
- `build_support_health_report.py`
- `mirror_to_dropbox.py`
- `poll_support_email.py`
- `poll_telegram_updates.py`

Still not restored in the current stack:
- the older fuller cluster/candidate rebuild pipeline
- draft-export/reply-export steps that existed in earlier sessions

Operational consequence:
- BusinessOS can currently ingest fresh email and Telegram support traffic, monitor it, report on it, and mirror the durable outputs safely
- the richer downstream analysis/export chain is still a later restoration step

## Best way to use it right now

Use BusinessOS today as:
- the source-of-truth local archive
- a live support intake + reporting workspace
- an auditable intake evidence store
- a Dropbox-mirrored output workspace
- a stable base for restoring the fuller downstream rebuild chain later

## Related docs

- `docs/architecture-and-operations-guide.md`
- `docs/communications-lane-policy.md`

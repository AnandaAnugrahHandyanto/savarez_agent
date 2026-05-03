# BusinessOS Architecture

## Canonical paths

Workspace root:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS`

Dropbox mirror root:
- `/home/yuiop/Dropbox/BusinessOS`

SQLite database:
- `03_DATA/db/businessos.db`

## Design principles

- local-first filesystem archive
- SQLite as the operational query layer
- raw artifacts preserved for auditability
- normalized artifacts preserved for reprocessing
- repo markdown as engineering source of truth
- Dropbox as mirror, not source of truth
- fail visibly rather than pretending ingestion worked

## Main layers

### 1. Intake artifact layer
Original or near-original inputs.

Examples:
- `00_INBOX/communications/telegram/raw/`
- `00_INBOX/communications/email/raw/`
- `00_INBOX/communications/email/attachments/`
- `00_INBOX/manual-drop/`

### 2. Structured archive layer
Deterministic archive and entity records.

Examples:
- `01_DOCUMENTS/`
- `02_ENTITIES/email-accounts/`
- `02_ENTITIES/services/`
- `02_ENTITIES/websites/`

### 3. Knowledge/index layer
Stateful operational layer backed by SQLite.

Key tables currently relied on:
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

### 4. Reporting and automation layer
Automation entrypoints and generated summaries.

Automation scripts:
- `04_AUTOMATIONS/scripts/run_support_pipeline.py`
- `04_AUTOMATIONS/scripts/poll_support_email.py`
- `04_AUTOMATIONS/scripts/poll_telegram_updates.py`
- `04_AUTOMATIONS/scripts/build_support_readiness_report.py`
- `04_AUTOMATIONS/scripts/build_support_health_report.py`
- `04_AUTOMATIONS/scripts/manage_tasks.py`
- `04_AUTOMATIONS/scripts/operator_updates.py`
- `04_AUTOMATIONS/scripts/mirror_to_dropbox.py`

Primary configs:
- `04_AUTOMATIONS/configs/support-inboxes.yaml`
- `04_AUTOMATIONS/configs/telegram-sources.yaml`
- `04_AUTOMATIONS/configs/communication-lane-policy.yaml`
- `04_AUTOMATIONS/configs/operator-updates.yaml`
- `04_AUTOMATIONS/configs/dropbox-mirror.yaml`

## Intake architecture

### Email
Current live mailbox account:
- `helix-admin`

Routing is alias-based across:
- `admin@helixsystems.cc`
- `support@helixsystems.cc`
- `billing@helixsystems.cc`
- `hello@helixsystems.cc`
- `legal@helixsystems.cc`
- `privacy@helixsystems.cc`
- `owner@helixsystems.cc`
- `expenses@helixsystems.cc`

### Telegram
Configured source accounts:
- `telegram-steady-support` — customer-support lane, live poll enabled
- `telegram-businessos-operator` — operator-control lane
- `telegram-watson-operator` — manual/export-oriented lane scaffold

## Lane separation model

BusinessOS deliberately separates:
- customer-facing support intake
- owner/operator control traffic
- sensitive approval lanes such as legal, privacy, and billing

This separation protects support triage from contamination by admin chatter and keeps risky outbound flows gated.

## Reporting outputs

Primary report directories:
- `05_REPORTS/support/`
- `05_REPORTS/tasks/`
- `05_REPORTS/monthly/`
- `05_REPORTS/daily/`
- `05_REPORTS/product/`

Important report families:
- support operations summary
- support health check
- support readiness audit
- task dashboard
- finance summary
- deductible summary
- previous-day daily summary
- product feedback summary

## Mirror architecture

Mirror config:
- `04_AUTOMATIONS/configs/dropbox-mirror.yaml`

Currently mirrored include paths:
- `01_DOCUMENTS`
- `02_ENTITIES`
- `03_DATA/exports`
- `03_DATA/metadata`
- `03_DATA/normalized`
- `05_REPORTS`
- `docs`
- `README.md`

## Current state summary

What the current on-disk stack supports:
- live IMAP polling for the Helix mailbox
- live Telegram polling for the Steady support lane
- task capture from CLI, TODO emails, and Telegram task commands
- manual-drop and forwarded-attachment filing into `01_DOCUMENTS/`
- finance and deductible summaries
- support health/readiness reporting
- operator Telegram updates and morning summary reporting
- Dropbox mirroring

What is still a later restoration step:
- full downstream rebuild chain for clustering refreshes, candidate generation, and reply-draft export/approval/send

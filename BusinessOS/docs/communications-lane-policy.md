# Communications Lane Policy

## Purpose

This document defines how BusinessOS should treat communications between:
- customers and support lanes
- mailbox aliases under `@helixsystems.cc`
- Poiuy as the business owner
- the internal BusinessOS operator/control lane

The core rule is separation:
- customer support intake should stay customer-facing
- owner/operator comms should stay internal
- legal/privacy/billing lanes should never auto-send without owner approval

## Helix mailbox policy

BusinessOS should read all mail arriving through the Helix mailbox account and route by recipient alias.

### `admin@helixsystems.cc`
- queue: `admin`
- reaction mode: `log-only`
- intended behavior:
  - ingest
  - categorize
  - preserve artifacts
  - file attachments when business-relevant
  - no automatic outbound reply by default

### `support@helixsystems.cc`
- queue: `customer-support`
- reaction mode: `draft-only`
- intended behavior:
  - ingest
  - categorize
  - mark needs-reply
  - generate suggested reply text
  - preserve thread history and attachments

### `billing@helixsystems.cc`
- queue: `billing-support`
- reaction mode: `owner-approval-required`
- intended behavior:
  - ingest
  - categorize
  - mark high priority when refund/charge terms appear
  - generate suggested reply text
  - require owner approval before any outbound send

### `hello@helixsystems.cc`
- queue: `community-support`
- reaction mode: `draft-only`
- intended behavior:
  - ingest
  - categorize
  - generate suggested reply text
  - owner can send or ignore based on context

### `legal@helixsystems.cc`
- queue: `legal-review`
- reaction mode: `owner-approval-required`
- intended behavior:
  - ingest
  - categorize
  - hold for owner review
  - no automatic outbound send

### `privacy@helixsystems.cc`
- queue: `privacy-review`
- reaction mode: `owner-approval-required`
- intended behavior:
  - ingest
  - categorize
  - hold for owner review
  - no automatic outbound send

### `expenses@helixsystems.cc`
- queue: `finance-review`
- reaction mode: `log-only`
- intended behavior:
  - ingest
  - classify expense/bill forwards as `business-expense-record` when applicable
  - preserve raw email + normalized metadata
  - file linked documents into the finance expense archive
  - extract vendor/amount/date when possible
  - create tax-treatment records for deductible business expenses
  - no automatic outbound reply by default

## Telegram policy

## 1. Customer-facing support bot

Configured lane:
- `telegram-steady-support`

Policy:
- lane: `customer-support`
- reaction mode: `draft-only`
- intended behavior:
  - ingest customer support messages
  - categorize/triage
  - generate suggested replies
  - mark needs-reply
  - keep operator self-tests out of customer-facing support state

This lane should remain narrow and customer-facing.

## 2. Owner/operator BusinessOS bot

Configured scaffold:
- `telegram-businessos-operator`

Policy:
- lane: `operator-control`
- reaction mode: `internal-ops`
- intended behavior:
  - ingest internal owner/operator messages
  - treat messages as internal ops, not customer support
  - allow task commands such as `/todo ...` and `/task ...`
  - allow reminder metadata via `Reminder:` lines in task commands
  - never create customer feedback items from this lane
  - never mark customer needs-reply from this lane
  - never generate customer-facing support replies from this lane

Current command examples:
- `/todo Reconcile April receipts`
- `/focus task-0001`
- `/priority Finish Play Console registration`
- `/task task-0001 start`
- `/task task-0001 done`
- `/task task-0001 comment Waiting on accountant`

Current reminder syntax:
- `Reminder: 2026-05-14T09:00:00-04:00`

Operator update behavior:
- BusinessOS can now send internal Telegram updates on the operator-control lane when a pipeline run starts, when email/Telegram/document/Dropbox steps complete, and when the run completes; those step and completion messages include item-level detail such as imported emails, processed documents, copied Dropbox paths, generated report paths, BusinessOS classification labels, and suggested follow-up task titles when applicable
- on the first eligible morning run after local midnight, BusinessOS generates a previous-day summary under `05_REPORTS/daily/` and sends it to the operator lane
- those daily summaries are also stored in SQLite for later mining via `daily_summary_reports`
- the daily summary now includes remaining open work, today's explicitly recorded priorities, and suggested follow-up items that were inferred from non-task intake without auto-creating real tasks

Important limitation:
- natural-language reminder commands like `remind me tomorrow` are not implemented yet
- current reminder capture is task-command based

## Outbound approval rules

If/when outbound sending is restored, use these rules:
- support email: draft-only
- community email: draft-only
- billing email: owner approval required
- legal email: owner approval required
- privacy email: owner approval required
- customer-support Telegram: draft-only
- operator-control Telegram: internal only, never customer-facing

## Why separate bots are better

Separate bots are preferred because they:
- reduce contamination between internal ops chatter and customer support
- make reminder/approval/task workflows safer
- keep support reporting cleaner
- create a clean place for future owner-facing automations such as digests and approval requests

## Current implementation status

Implemented now:
- alias-based email routing for the Helix mailbox
- customer-support Telegram lane ingestion
- dedicated operator-control Telegram lane behavior in the poller
- task command parsing from Telegram/email
- reminder storage in tasks
- operator-control messages stay out of customer feedback items

Not yet restored:
- full outbound send + approval execution pipeline
- natural-language reminder parsing
- fully automated acknowledgements/replies

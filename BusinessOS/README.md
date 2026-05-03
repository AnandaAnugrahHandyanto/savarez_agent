# BusinessOS

BusinessOS is the local-first operations workspace for Steady.

Canonical root:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS`

## Canonical engineering docs

Start here for source-of-truth documentation:
- `PROJECT.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/runbook.md`
- `docs/open-questions.md`

## Supplemental operator docs

These remain useful for longer-form context and operator guidance:
- `docs/user-manual.md`
- `docs/architecture-and-operations-guide.md`
- `docs/communications-lane-policy.md`

## What is in this workspace

- `00_INBOX/` for raw intake artifacts
- `01_DOCUMENTS/` for filed business documents
- `02_ENTITIES/` for entity records and registries
- `03_DATA/` for SQLite, metadata, exports, logs, and normalized artifacts
- `04_AUTOMATIONS/` for scripts and configs
- `05_REPORTS/` for generated operational reports
- `docs/` for stable human-facing and engineering documentation

## Current operating model

- local filesystem is canonical
- SQLite is the query and operational state layer
- repo markdown is the engineering source of truth
- Dropbox is a one-way mirror target
- the scheduled pipeline handles live IMAP intake, live Steady Telegram support intake, manual/email document filing, task dashboard generation, finance/tax summaries, operator Telegram updates, and previous-day summary reporting
- full downstream rebuild/export behavior is still only partially restored

## Recommended first reads

1. `PROJECT.md`
2. `docs/architecture.md`
3. `docs/runbook.md`
4. latest relevant reports under `05_REPORTS/`

# BusinessOS Project Charter

BusinessOS is the local-first operations workspace for Steady.

Canonical workspace root:
- `/home/yuiop/.hermes/hermes-agent/BusinessOS`

Dropbox mirror root:
- `/home/yuiop/Dropbox/BusinessOS`

## Purpose

BusinessOS exists to turn business operations into a local-first, auditable system that can:
- ingest support and operations signals
- preserve raw evidence
- normalize and classify activity
- file business documents deterministically
- maintain a queryable SQLite state layer
- generate operator-facing reports
- mirror selected artifacts into Dropbox without making Dropbox the source of truth

## Sources of truth

Use this precedence order:

1. Filesystem artifacts under this repo workspace
   - canonical archive for documents, raw artifacts, normalized artifacts, configs, and generated reports
2. SQLite database
   - operational/query layer at `03_DATA/db/businessos.db`
3. Git-backed markdown docs
   - engineering and operator truth for architecture, runbooks, decisions, and open questions
4. Dropbox mirror
   - convenience distribution layer only

## Core scope

BusinessOS currently covers:
- Helix mailbox ingestion and alias-based routing
- Steady Telegram support intake
- separate operator-control Telegram handling
- manual document drop filing
- forwarded attachment processing for business records
- task capture and task reporting
- finance and deductible summaries
- support health and readiness reporting
- operator Telegram updates and previous-day summary reporting
- Dropbox mirroring for selected outputs

## Current lane model

Customer-facing lanes:
- `support@helixsystems.cc`
- `billing@helixsystems.cc`
- `hello@helixsystems.cc`
- `legal@helixsystems.cc`
- `privacy@helixsystems.cc`
- `telegram-steady-support`

Internal/ops lanes:
- `admin@helixsystems.cc`
- `owner@helixsystems.cc`
- `expenses@helixsystems.cc`
- `telegram-businessos-operator`

## Invariants

- Local filesystem is canonical.
- Dropbox is a one-way mirror target.
- Raw and normalized artifacts are preserved for auditability.
- Customer support intake must stay separate from owner/operator control traffic.
- Legal, privacy, and billing outbound replies must not be auto-sent without owner approval.
- Engineering truth should live in repo markdown, not only in chat history.

## Canonical engineering docs

- `PROJECT.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/runbook.md`
- `docs/open-questions.md`

## Supplemental operator docs

- `README.md`
- `docs/user-manual.md`
- `docs/architecture-and-operations-guide.md`
- `docs/communications-lane-policy.md`

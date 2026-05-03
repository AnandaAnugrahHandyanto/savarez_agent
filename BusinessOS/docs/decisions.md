# BusinessOS Decisions

This file records current architectural decisions that should be treated as stable unless explicitly changed.

## D-001: Local-first archive
Status: active

Decision:
- The local filesystem under `BusinessOS/` is the canonical store.
- Dropbox is only a mirror/distribution layer.

Why:
- keeps control local
- preserves offline/auditable state
- avoids treating cloud sync as truth

## D-002: Repo markdown is engineering source of truth
Status: active

Decision:
- Architecture, runbooks, decisions, and open questions belong in git-backed markdown inside the repo.

Why:
- reviewable in git
- easy for Hermes to read/search
- avoids relying on chat transcripts as the only memory of how the system works

## D-003: Raw + normalized artifact preservation
Status: active

Decision:
- Preserve raw intake artifacts and normalized artifacts.

Why:
- supports auditability
- enables reprocessing and debugging
- reduces silent data loss when classification logic changes

## D-004: Alias-based email routing
Status: active

Decision:
- Ingest mail from the Helix mailbox account and route by recipient alias queue and reaction mode.

Why:
- operational meaning lives in the alias, not just the mailbox account
- allows support, billing, privacy, legal, and admin traffic to remain distinct

## D-005: Separate customer-support and operator-control lanes
Status: active

Decision:
- Customer-facing support intake and owner/operator control traffic must remain separate.

Why:
- prevents admin chatter from polluting customer triage
- keeps customer-facing reports actionable
- makes operator automations safer

## D-006: Sensitive outbound approval gating
Status: active

Decision:
- Legal, privacy, and billing replies require owner approval before any outbound send.

Why:
- these lanes are higher-risk
- reduces accidental live-impacting automation

## D-007: SQLite as operational state layer
Status: active

Decision:
- SQLite remains the core local operational/query database.

Why:
- local, simple, inspectable
- good fit for reports, checkpoints, tasks, and communication state

## D-008: Holographic is the active Hermes external memory provider
Status: active

Decision:
- Hermes built-in `MEMORY.md` and `USER.md` remain canonical memory.
- Holographic is the single active external provider for local structured recall.
- Hindsight is optional later and would replace Holographic unless Hermes gains a composite provider.

Why:
- stays fully local
- avoids extra paid provider dependence
- fits Hermes’s current one-external-provider architecture

## D-009: Canonical BusinessOS docs sync automatically into Holographic
Status: active

Decision:
- Canonical BusinessOS markdown facts from `PROJECT.md`, `docs/architecture.md`, and `docs/decisions.md` are mirrored into Holographic automatically.
- Sync is event-driven on doc changes and also runs on a periodic safety-net timer.

Why:
- keeps Hermes recall aligned with the repo source of truth
- removes operator dependence on manual sync commands
- preserves a local-first memory workflow with deterministic inputs

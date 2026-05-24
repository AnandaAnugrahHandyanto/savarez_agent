# Hermes Backend Engineering Doctrine - 2026-05-17

Status: canonical proposal for `backend-eng` and backend-heavy coding work.

Purpose: define how Hermes backend agents should build, change, verify, and hand off backend systems.

## Scope

Use this doctrine for:

- APIs and service contracts;
- databases, migrations, schemas, and state stores;
- background jobs, queues, cron scripts, and webhooks;
- auth, permissions, secrets, and integrations;
- reliability, idempotency, observability, and operational safety;
- backend portions of full-stack work.

## Backend Priorities

1. Preserve data integrity.
2. Preserve clear API and integration contracts.
3. Make mutations idempotent or guarded where practical.
4. Prefer boring, debuggable architecture over clever abstraction.
5. Add tests at the boundary where regressions would hurt.
6. Leave operational handoff notes when behavior changes.
7. Support frontend contracts with predictable states and errors.

## Discovery Before Editing

Before editing, identify:

- app entry points and framework;
- source-of-truth data stores;
- generated files and migrations;
- API contracts and clients;
- UI-facing loading, empty, error, partial, stale, long-content, disabled, and success states;
- auth and permission boundaries;
- queue, cron, webhook, or background worker ownership;
- relevant tests and existing fixtures;
- deployment or runtime assumptions.

If source-of-truth is unclear, stop and map it before editing.

## Mutation Safety

Pause for Gabriel approval before:

- production database changes;
- destructive migrations;
- live credential or secret changes;
- payment, invoice, customer, CRM, calendar, or account-affecting mutation;
- broad deletion, reset, or force-push operations;
- changing GHL-facing execution paths without Blue/GHL preflight.

For local development state:

- prefer reversible changes;
- back up important state before schema or migration experiments;
- document any command that changes persistent state.

## API And Data Contract Rules

- Treat public APIs, internal APIs, database schemas, and queue payloads as contracts.
- When changing a contract, update producer, consumer, tests, docs, and migration path together.
- Preserve backward compatibility unless the card explicitly authorizes a break.
- Validate inputs at the boundary.
- Return useful errors without leaking secrets or private data.
- Keep idempotency keys or duplicate checks for retries, webhooks, and scheduled jobs.
- For backend-for-frontend work, document the state and error contract before frontend implementation depends on it.

## Test Expectations

Choose the smallest test set that proves the change:

- unit tests for pure logic;
- integration tests for database/API/queue behavior;
- migration tests or dry-runs for schema changes;
- regression tests for fixed bugs;
- smoke checks for scripts and CLIs;
- contract tests when another component depends on the output.

If tests cannot run, say exactly why and run the next best static or smoke check.

## Handoff Checklist

Backend handoff must include:

- files changed;
- API/data behavior changed;
- migrations or persistent state touched;
- tests/checks run and result;
- idempotency or duplicate-safety notes;
- UI-state contract notes when a frontend depends on the backend;
- auth/permission impact;
- operational or rollback notes;
- unresolved risks or needed approvals.

## Backend Kanban Done Definition

A backend card is done when:

- implementation matches the card goal;
- source-of-truth files were edited, not generated mirrors alone;
- relevant tests/checks were run;
- state/migration effects are documented;
- no approval-gated action was taken without approval;
- handoff evidence is concise enough for Gabriel or a reviewer to trust.

# Read/Write Contracts — Canonical Memory and Executor State

## Scope

This document defines what can be read and written by each side of the architecture.

- VPS 1: canonical memory owner
- VPS 2: execution and read node
- Tailscale: private transport between the two

## Read contract

VPS 2 may read the following canonical surfaces from VPS 1:
- facts
- decisions
- entities
- summaries
- event metadata
- source provenance needed for context

Reads must be:
- authenticated
- private to the tailnet
- traceable
- safe to retry

## Write contract

Only approved systems may write canonical memory on VPS 1.

Approved writers:
- ingestion pipeline
- explicit write tools
- vetted administrative workflows
- replay worker after recovery, once VPS 1 confirms receipt

## Canonical write rules

- writes must include provenance
- writes must be idempotent or deduplicated
- writes must not bypass the event log
- writes must not rely on public endpoints
- writes must not be accepted from VPS 2 unless they go through the approved canonical path

## Event log rule

The event log is append-only.

Forbidden operations:
- update existing events
- delete existing events
- reassign provenance after the fact
- rewrite history to simplify downstream consumers

## Local execution state rule

VPS 2 may persist local state for execution, but it is not canonical.

Local-only state includes:
- pending queue entries
- cache snapshots
- task leases
- retry bookkeeping
- observability data

This state may be lost and rebuilt.

## Degraded mode

If Tailscale is down or VPS 1 is unreachable:
- no remote writes are attempted
- VPS 2 continues with local cache only
- new actions are appended to a local pending queue
- stale reads are explicitly marked stale
- replay happens only after reachability returns
- replay must be ordered and idempotent

## Recovery contract

When connectivity returns:
1. validate Tailscale reachability
2. replay local pending queue
3. wait for VPS 1 acknowledgement
4. reconcile any conflicts in favor of VPS 1
5. clear only the entries that were acknowledged

## Failure policy

Fail closed when any of these happen:
- provenance is missing
- target surface is ambiguous
- write destination is not canonical
- remote state cannot be authenticated
- a task attempts to escalate itself into a canonical writer

## Acceptance criteria

This contract is satisfied when:
- VPS 2 can read canonical state safely over Tailscale
- VPS 2 can operate locally without unsafe writes when disconnected
- canonical memory remains only on VPS 1
- replay is safe, ordered, and verifiable

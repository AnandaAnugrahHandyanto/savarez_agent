# Agent Permissions — VPS 2 Executor Model

## Goal

Allow VPS 2 to run agents and read canonical memory without becoming a second source of truth.

## Permission tiers

### 1) Read-only by default
Applies to all routine agent work on VPS 2.

Allowed:
- read canonical facts
- read decisions
- read summaries
- read entity registry
- read event metadata needed for context
- read local cache and local execution state

Forbidden:
- create or modify canonical memory directly
- mutate the append-only event log
- expose public write endpoints
- write across machines without Tailscale
- promote VPS 2 to memory owner

### 2) Narrow approved writes
Only specific flows may write, and only through the canonical write path on VPS 1.

Allowed write flows:
- approved ingestion pipelines
- explicit memory write tools
- administrative maintenance with audit trail
- replay of queued events after reconnect, with VPS 1 acknowledgement

### 3) Execution-state writes
VPS 2 may write its own local execution state.

Allowed local-only writes:
- task progress markers
- temporary cache entries
- retry counters
- append-only pending queue entries
- local logs and traces

These writes must never be treated as canonical memory.

## Separation rule

Canonical memory lives on VPS 1.

VPS 2 owns only:
- ephemeral runtime state
- local queue state
- cache state
- agent execution artifacts

If VPS 2 loses access to VPS 1, it may keep working in degraded mode, but it must not invent canonical facts or accept remote writes.

## Retry and loop guardrails

### Retry limits
- retries must be bounded
- exponential backoff must cap out
- repeated failures must degrade to local queueing
- no infinite retry loops

### Loop protection
- agent recursion must be capped
- write retries must be idempotent
- duplicate events must be deduplicated by source/event id
- unsafe writes must fail closed

## Unsafe patterns

These are forbidden:
- "best effort" writes to canonical memory without confirmation
- writing directly to Postgres from a task runner on VPS 2
- silent fallback from remote write failure to local canonical mutation
- using execution state as a substitute for canonical state
- opening a public API just to simplify write access

## Verification checklist

Before VPS 2 is treated as an executor:
- Tailscale reachability is confirmed
- read-only access works over the tailnet
- local execution state is isolated from canonical memory
- write paths are explicit, narrow, and audited
- degraded mode does not create unsafe writes

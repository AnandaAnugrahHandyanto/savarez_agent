# Memory Model — Canonical Layer on VPS 1

## Objective

VPS 1 is the single source of truth for memory. Agents may read from it; only controlled workflows may write to it.

## Core rules

- `event_log` is append-only.
- `facts`, `decisions`, `episodes`, `entities`, and `summaries` are derived or curated records.
- Every durable record must link back to one or more source events.
- No public exposure of memory services.
- Tailscale is the primary transport between nodes; degraded mode must preserve safety if it fails.
- VPS 2 is an execution node, not the memory master.

## Data layers

### 1) `event_log`
Immutable audit trail of everything important that happened.

### 2) `sources`
Traceability layer for where a record came from.

### 3) `entities`
Canonical references for people, projects, systems, and resources.

### 4) `facts`
Short durable statements with provenance.

### 5) `decisions`
Explicit decisions with rationale and status.

### 6) `episodes`
Time-bounded clusters of activity or context.

### 7) `summaries`
Compressed views over episodes, entities, or time windows.

## Write policy

- Agents default to read-only.
- Writes require an approved memory-write path.
- Derived records should be recomputable from source events.
- If provenance is missing, the record is not canonical.

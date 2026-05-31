# Memory Contracts — Read/Write Boundaries

## Read contract

Agents on VPS 2 may read:
- canonical facts
- decisions
- entity registry
- summaries
- event metadata required for context

## Write contract

Only approved flows may write:
- ingestion pipelines
- explicit memory write tools
- controlled administrative operations

## Forbidden by default

- direct update/delete of `event_log`
- silent mutation of provenance
- public API exposure for write endpoints
- cross-machine writes without Tailscale
- promotion of VPS 2 to canonical memory owner

## Degraded-mode rule

If Tailscale is unavailable or unreachable:
- VPS 2 may continue with local cache and append-only pending queue
- no remote writes are attempted
- stale reads must be labeled as stale
- recovery requires replay and acknowledgement from VPS 1

## Operational rule

If a record cannot answer:
- who created it
- when it was created
- why it exists
- which source produced it

then it does not belong in canonical memory.

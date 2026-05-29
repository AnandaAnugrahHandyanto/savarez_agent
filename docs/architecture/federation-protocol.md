# Federation Protocol — VPS 1 ↔ VPS 2

This document defines the private control channel between the canonical node and the executor node.

## Non-negotiable invariants

- VPS 1 is the only canonical writer.
- VPS 2 never promotes itself to memory owner.
- All federation traffic stays inside Tailscale.
- Messages are signed and time-bounded.
- Replay is append-only and idempotent.
- Conflicts resolve in favor of VPS 1.

## Participants

- **VPS 1**: canonical control plane, memory owner, ack authority.
- **VPS 2**: executor/worker, local queue owner, replay sender.

## Message types

### 1) Read request

Used by VPS 2 to fetch canonical state.

Payload:
- `request_id`
- `scope`
- `cursor` or `since`
- `timestamp`
- `nonce`
- `signature`

Response:
- `status`
- `data`
- `snapshot_id`
- `freshness`
- `signature`

### 2) Event replay

Used by VPS 2 to submit queued local actions once reachability returns.

Payload:
- `job_id`
- `event_id`
- `kind`
- `payload`
- `provenance`
- `created_at`
- `source_node`
- `timestamp`
- `nonce`
- `signature`

Rules:
- event IDs must be stable
- event order must be preserved
- duplicate events must be deduplicated
- missing provenance fails closed

### 3) Acknowledgement

Used by VPS 1 to confirm accepted events.

Payload:
- `job_id`
- `event_id`
- `ack_status`
- `canonical_ref`
- `timestamp`
- `signature`

Ack status values:
- `accepted`
- `rejected`
- `duplicate`
- `stale`

## Canonical write path

1. VPS 2 creates local events while executing.
2. Events are appended to the local pending queue.
3. When Tailscale is healthy, VPS 2 sends queued events to VPS 1.
4. VPS 1 validates signature, provenance, and idempotency.
5. VPS 1 appends accepted events to canonical storage.
6. VPS 1 returns per-event acknowledgements.
7. VPS 2 clears only acknowledged queue entries.

## Signature and freshness rules

- Every message includes a timestamp.
- Every message includes a nonce.
- Messages older than the freshness window are rejected.
- Signatures cover the full envelope.
- Messages without a valid signature are rejected.

## Retry rules

- Retry only on transport failure or transient rejection.
- Do not retry rejected canonical writes blindly.
- Duplicate delivery must be safe.
- Replay remains append-only until acked.

## Conflict rules

When canonical state and local state diverge:
- VPS 1 wins.
- VPS 2 replays only the still-pending entries.
- Local cache is refreshed from canonical state.
- No local overwrite can replace canonical history.

## Failure modes

### Tailnet down

- VPS 2 keeps working locally.
- New actions enter the pending queue.
- No remote write is attempted.

### VPS 1 unreachable

- Treat as degraded mode.
- Read stale local cache only.
- Do not invent canonical facts.

### Invalid signature

- Reject immediately.
- Log locally on VPS 2 and on VPS 1 if observed.

### Replay conflict

- Mark stale or duplicate.
- Preserve canonical history.
- Requeue only unresolved entries.

## Acceptance criteria

This protocol is acceptable when:
- VPS 2 can read canonical state privately over Tailscale.
- VPS 2 can replay local events safely after reconnect.
- VPS 1 can ack or reject each event individually.
- No message path allows VPS 2 to become canonical.

# VPS Topology — Service and Directory Map

This document turns the two-VPS split into an operational map.

## Hard invariants

- VPS 1 is the canonical memory and decision owner.
- VPS 2 is execution-only.
- Tailscale is the only inter-VPS transport.
- No sensitive port is publicly exposed.
- VPS 2 may keep only ephemeral, replayable, or disposable state.
- Canonical writes must land on VPS 1.

## VPS 1 — canonical control plane

### Responsibilities

- own canonical memory
- store append-only event history
- derive facts, decisions, summaries, and traceability data
- accept approved writes through the canonical path only
- expose read-only access to VPS 2 over Tailscale
- validate and acknowledge replayed events

### Service set

- `postgresql.service` — canonical memory database
- `hermes-memory.service` — memory API / read path
- `hermes-orchestrator.service` — decision and routing layer
- `hermes-federation-server.service` — signed inbound envelopes from trusted peers
- `hermes-router.service` — request routing and policy enforcement
- `tailscaled.service` — private transport

### Runtime layout

- `~/.hermes/config.yaml` — Hermes configuration
- `~/.hermes/.env` — local secrets and tokens
- `~/.hermes/logs/` — agent, gateway, and service logs
- `~/.hermes/sessions/` — session history
- `~/.hermes/data/` — non-canonical local artifacts, if needed
- `~/.hermes/federation/` — federation config, peer registry, delivery log

### Canonical storage boundary

Canonical data lives in Postgres on VPS 1. Any local files under `~/.hermes/` are support state, not the source of truth.

## VPS 2 — execution plane

### Responsibilities

- run agents, workers, and sandboxes
- read canonical state from VPS 1 over Tailscale
- queue local actions when disconnected
- replay pending actions when reachability returns
- keep execution state separate from canonical memory

### Service set

- `hermes-worker.service` — general task execution
- `browser-worker.service` — browser automation jobs
- `batch-worker.service` — batch / queued work
- `render-worker.service` — image or media generation jobs
- `job-sandbox.service` — isolated local execution
- `tailscaled.service` — private transport

### Runtime layout

- `~/.hermes/config.yaml` — local agent config
- `~/.hermes/.env` — local credentials required only for execution
- `~/.hermes/cache/` — rebuildable caches
- `~/.hermes/pending/` — append-only local queue while disconnected
- `~/.hermes/artifacts/` — disposable outputs waiting for validation
- `~/.hermes/logs/` — worker logs and diagnostics
- `~/.hermes/sandbox/` — ephemeral job workspaces

### Non-goals

- no canonical writes
- no memory-master promotion
- no public API for write operations
- no direct database ownership for canonical state

## Shared network contract

- Private hostnames or Tailscale IPs only.
- Reachability checks must cover resolution, ping, and sensitive-port binding.
- If Tailscale is down, VPS 2 keeps working locally but must not invent canonical facts.
- Remote writes resume only after VPS 1 acknowledges replay.

## Recommended startup order

1. Start `tailscaled.service`
2. Start `postgresql.service` on VPS 1
3. Start `hermes-memory.service` on VPS 1
4. Start worker services on VPS 2
5. Run `scripts/check_tailnet_health.py`
6. Run `scripts/check_two_vps_readiness.py --expect-role executor` before promoting VPS 2 to executor mode
7. Run the schema validator on VPS 1 before enabling any write path

## Recommended stop order

1. Quiesce worker queues on VPS 2
2. Stop worker services
3. Stop federation and router services on VPS 1
4. Stop the memory service on VPS 1
5. Leave the database last unless an upgrade or rollback requires otherwise

## Safety boundary

If a proposed change blurs the line between executor state and canonical memory, the change is out of scope for VPS 2.

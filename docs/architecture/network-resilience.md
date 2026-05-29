# Network Resilience — Tailscale-First, Degraded-Mode Safe

## Goal
Keep all inter-machine traffic private over Tailscale while ensuring the system degrades safely if the tailnet becomes unavailable.

## Principle
- Tailscale is the *primary transport*.
- Public exposure of sensitive ports remains forbidden.
- A tailnet outage must reduce freshness, not correctness.
- No remote write is allowed when canonical connectivity is unavailable.

## Operating modes

### 1) Healthy
- VPS 2 reaches VPS 1 over Tailscale.
- Reads come from canonical services on VPS 1.
- Approved writes flow through the controlled write path.

### 2) Degraded
Triggered when Tailscale is down, unreachable, or partially broken.

Behavior:
- Reads use the last known local cache or snapshot.
- Writes are appended locally to a durable queue.
- No cross-machine mutation is attempted.
- Responses that depend on stale data are marked as stale.

### 3) Recovery
Triggered when Tailscale returns.

Behavior:
- Re-establish reachability checks.
- Replay queued events in order.
- Resolve conflicts using VPS 1 as the source of truth.
- Verify that the remote canonical state matches the replay result.

## Data-plane rules
- Canonical writes only land on VPS 1.
- VPS 2 may keep local execution state, cache, and a pending event queue.
- The queue must be append-only until acknowledged by VPS 1.
- Replays must be idempotent.

## Health checks
Minimum checks:
- DNS resolution of tailnet hostname
- TCP reachability to the memory/API endpoint
- Authenticated request to a read-only health endpoint
- Clock skew sanity for signed or time-sensitive requests

Reference implementation:
- `scripts/check_tailnet_health.py` validates DNS, Tailscale ping, and non-public binds for sensitive ports.
- `scripts/check_two_vps_readiness.py` is the rollout gate that combines schema validation with tailnet health before VPS 2 promotion.

## Emergency fallback
If the tailnet is down for an extended period:
- Continue local-only execution on VPS 2.
- Do not invent canonical state.
- Require manual intervention to restore sync before writes resume.

## Non-goals
- No public fallback port
- No alternate internet-facing write API
- No automatic promotion of VPS 2 to memory master

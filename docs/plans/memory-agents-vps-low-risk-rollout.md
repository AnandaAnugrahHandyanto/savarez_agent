# Memory, Agents & VPS — Low-Risk Rollout Plan

> **For Hermes:** Execute this plan in the safest order first: memory canônica on VPS 1, then private connectivity via Tailscale, then VPS 2 as consumer/executor.

**Goal:** Establish a canonical memory layer on VPS 1, keep all sensitive services private, and connect VPS 2 only after the schema and access rules are stable.

**Architecture:** VPS 1 is the source of truth for memory and decision records. VPS 2 is a worker/execution node that reads from VPS 1 over Tailscale and never becomes the master copy of state. No sensitive ports are exposed publicly; internal access happens through the tailnet only.

**Tech Stack:** Postgres, Tailscale, Hermes Workspace/Gateway, internal API contracts, append-only event log, derived facts/decisions.

---

## Phase 1 — Canonical memory first

**Objective:** Define and deploy the memory model on VPS 1 without touching execution workloads.

**Files:**
- Create: `docs/architecture/memory-model.md`
- Create: `docs/architecture/memory-contracts.md`
- Create: `docs/architecture/memory-schema.sql`
- Create: `docs/architecture/memory-indexing.md`

**Tasks:**
1. Define append-only `event_log`.
2. Define derived `facts`, `decisions`, `episodes`, `entities`, and `summaries`.
3. Define `sources` as the traceability layer for every record.
4. Write the initial SQL schema.
5. Verify the schema is self-consistent and migration-safe.

**Success criteria:**
- Single source of truth exists on VPS 1.
- No writes from agents yet.
- Every fact/decision can be traced back to source events.

---

## Phase 2 — Private access only

**Objective:** Make the memory service reachable only through the tailnet.

**Files:**
- Modify: network/service configuration for VPS 1
- Modify: network/service configuration for VPS 2
- Create: `docs/architecture/network-resilience.md`
- Create: `scripts/check_tailnet_health.py`
- Create: `scripts/check_two_vps_readiness.py`

**Tasks:**
1. Keep ports private/localhost-only.
2. Expose access only via Tailscale MagicDNS / Tailscale IP.
3. Verify SSH and service reachability over the tailnet.
4. Define degraded-mode behavior for tailnet outage.
5. Block public exposure of sensitive ports.
6. Add a repeatable health check for DNS, Tailscale reachability, and unsafe port binds.
7. Gate phase 3 on the combined readiness check, not on ad-hoc manual inspection.

**Success criteria:**
- No public exposure for workspace/gateway/memory endpoints.
- Access works from VPS 2 to VPS 1 over Tailscale.
- `python3 scripts/check_two_vps_readiness.py --expect-role executor` passes before VPS 2 is promoted to executor mode.

---

## Phase 3 — VPS 2 as execution node

**Objective:** Allow VPS 2 to read from canonical memory and run agents/tasks.

**Files:**
- Create: `docs/architecture/agent-permissions.md`
- Create: `docs/architecture/read-write-contracts.md`
- Create: `docs/architecture/federation-protocol.md`

**Tasks:**
1. Define read-only access for most agent operations.
2. Define the minimal write path for approved memory writes.
3. Separate execution state from canonical memory.
4. Add guardrails for retries, loops, and unsafe writes.

**Success criteria:**
- VPS 2 can execute tasks without owning the memory source of truth.
- Write permissions are explicit and narrow.

---

## Phase 4 — Observability and fallback

**Objective:** Add visibility without increasing blast radius.

**Files:**
- Create: `docs/architecture/observability.md`
- Create: `docs/architecture/rollback.md`
- Create: `docs/architecture/network-resilience.md`

**Tasks:**
1. Add logs and audit trails.
2. Add a restore/fallback path for memory corruption.
3. Define backup and verification checkpoints.
4. Confirm tailnet outage handling is safe and non-destructive.

**Success criteria:**
- Failures are diagnosable.
- Memory can be restored without guessing.

---

## Rollout order

1. Memory schema on VPS 1
2. Private connectivity via Tailscale
3. Combined readiness check passes
4. Read-only access from VPS 2
5. Controlled write path
6. Observability / rollback

## Risk rule

If a step increases public exposure, write authority, or cross-machine coupling before the schema is stable, stop and redesign.

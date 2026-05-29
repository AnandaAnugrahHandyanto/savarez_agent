# Architecture Notes

This directory captures the rollout boundaries for memory, agents, networking, and safety.

## Current documents
- [Memory model](memory-model.md)
- [Memory contracts](memory-contracts.md)
- [Memory indexing](memory-indexing.md)
- [Memory schema](memory-schema.sql)
- [Agent permissions](agent-permissions.md)
- [Read/write contracts](read-write-contracts.md)
- [Network resilience](network-resilience.md)
- [VPS topology](vps-topology.md)
- [Federation protocol](federation-protocol.md)
- [Observability](observability.md)
- [Rollback](rollback.md)
- [Visual architecture diagram](../../memory-agents-vps-architecture.html)

## Validation helpers
- `scripts/validate_memory_schema.py` loads the canonical schema into a temporary Postgres database and checks the core tables plus the append-only trigger.
- `scripts/check_two_vps_readiness.py` composes schema validation and tailnet health validation into a single rollout checkpoint. On VPS 2, pass `--expect-role executor` before the service starts.

## Rollout order
1. Canonical memory on VPS 1
2. Private connectivity via Tailscale
3. Combined readiness check passes
4. VPS 2 as read-only executor
5. Controlled write path
6. Observability and rollback

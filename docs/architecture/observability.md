# Observability — Safe Visibility Without Expanding Blast Radius

## Goal
Add logs, metrics, and traces that make the system diagnosable without exposing canonical memory or write paths publicly.

## Principles
- Observability is read-only.
- Logs must not become a hidden source of truth.
- Metrics should summarize behavior, not replace the underlying records.
- Traces must preserve provenance across VPS 1 and VPS 2.
- Sensitive ports remain private to the tailnet.

## What to observe
- memory ingestion latency
- replay queue depth
- Tailscale reachability
- stale-read frequency
- write failure rate
- append-only violations
- retry counts and loop caps

## Required outputs
- structured logs with source identifiers
- metrics for health and backlog
- audit trail for every canonical write
- alerts when stale mode persists too long

## Safety rules
- No public debug endpoint for canonical memory.
- No write capability through telemetry systems.
- No auto-repair that mutates state without audit.

## Acceptance criteria
- Operators can tell when the system is unhealthy.
- Operators can diagnose failures without granting broader write access.
- Observability works even when the system degrades.

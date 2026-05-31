# Rollback — Safe Recovery Without Losing Provenance

## Goal
Provide a rollback path for bad deployments, schema mistakes, and memory corruption without rewriting history or exposing the system to unsafe writes.

## Rollback rules
- Rollback must be explicit.
- Rollback must preserve provenance.
- Rollback must not delete the append-only event history.
- Rollback must not promote VPS 2 to canonical owner.
- Rollback should prefer forward fixes when history must remain intact.

## Allowed rollback actions
- revert application deploys
- restore a known-good schema migration
- disable a bad write path
- rehydrate caches from canonical data
- replay pending events after correction

## Forbidden rollback actions
- editing `memory_event_log` in place
- silently dropping records to make data look clean
- accepting public writes as a shortcut to recovery
- replacing canonical state with local execution state

## Recovery sequence
1. freeze new writes
2. verify current failure mode
3. restore the last known-good code or schema
4. replay or reconcile pending events
5. compare restored state to canonical expectations
6. re-enable writes only after verification

## Acceptance criteria
- A failed release can be backed out safely.
- Canonical memory remains auditable.
- Recovery can be repeated without guessing.

# Memory Indexing

## Goal

Make canonical memory fast to read without turning it into a write-heavy system.

## Recommended indexes

- `memory_event_log (occurred_at DESC)` for timeline queries
- `memory_event_log (entity_id)` for entity-centric lookups
- `memory_event_log (event_type)` for filtering by event class
- `memory_event_log USING GIN (payload)` for JSONB search
- `memory_facts (subject_entity_id)` for entity facts
- `memory_facts (fact_key)` for key-based lookup
- `memory_facts USING GIN (fact_value)` for structured fact search
- `memory_decisions (decision_key)` for decision history
- `memory_decisions (status)` for active/superseded filtering
- `memory_episodes (entity_id)` and `memory_episodes (started_at DESC)` for timeline browsing
- `memory_summaries (scope_type, scope_id)` for scoped retrieval
- `memory_summaries USING GIN (source_range)` for provenance expansion

## Read path

1. Start from entity or time window.
2. Fetch relevant facts and decisions.
3. Expand via linked source events.
4. Use summaries only as compression, never as the only source.

## Rule

If a query becomes slow, add an index for the read pattern before adding more derived data.

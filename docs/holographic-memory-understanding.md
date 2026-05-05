# Holographic Memory Understanding

This document describes the productionized Phase 1 "memory understanding"
layer for the local `holographic` memory provider.

## Scope

The upgrade is additive. It does not replace built-in `MEMORY.md` / `USER.md`,
does not change launchd or gateway wiring, and does not require cloud memory.

The understanding layer now adds:

- hybrid retrieval scoring across semantic, keyword, recency, salience, and confidence
- structured enrichment on write / ingest
- bounded deferred understanding ingestion for turn and session extraction
- related-memory links for repeated people / project / topic mentions
- canonical keys / lightweight clustering for people, projects, and topics
- explain/debug retrieval output
- operator commands for status, reindex, inspect, and query debugging

## Architecture

Primary modules:

- `plugins/memory/holographic/store.py`
  Stores facts plus derived metadata, vectors, and links.
- `plugins/memory/holographic/enrichment.py`
  Local heuristics for extracting entities, people, projects, topics,
  dates/times, locations, intent/type, source channel, salience, and confidence.
- `plugins/memory/holographic/embeddings.py`
  Optional embedding-provider abstraction. Current providers: `none`, `openai`.
- `plugins/memory/holographic/ingestion.py`
  Durable deferred-ingest payload shaping, bounded queue draining, and
  heuristic turn/session extraction.
- `plugins/memory/holographic/retrieval.py`
  Hybrid candidate generation, ranking, and explain/debug scoring.
- `plugins/memory/holographic/cli.py`
  Operator commands.

Storage model:

- `facts`
  Source text plus trust, salience, source confidence, intent, source channel,
  metadata JSON, canonical keys, HRR vector, and optional embedding vector.
- `fact_entities`
  Normalized entity links.
- `fact_links`
  Lightweight related-memory edges.
- `memory_banks`
  Existing HRR banks kept intact.
- `understanding_ingest_queue`
  Durable deferred-ingest ledger for turn/session understanding work.
- `understanding_state`
  Last-success, failure, queue-reject, and reindex state for operators.

Write paths:

- synchronous:
  - explicit `fact_store(action="add")`
  - built-in memory mirroring via `memory` tool writes
- deferred:
  - `sync_turn()` queues bounded turn understanding
  - `on_session_end()` queues bounded session extraction when `auto_extract` is enabled
  - deferred work drains opportunistically on `queue_prefetch`, `prefetch`, session end, shutdown, and `hermes holographic reindex`

The deferred path is intentionally small:

- no always-on worker
- durable queue in the existing SQLite DB
- bounded pending queue with reject counting
- retry with backoff on failures
- safe restart recovery for interrupted in-flight items

## Retrieval Model

Search now merges two candidate paths:

1. keyword candidates from SQLite FTS5
2. semantic candidates from HRR vectors and optional embeddings

Each candidate gets a configurable weighted score across:

- semantic relevance
- keyword relevance
- recency
- salience / priority
- source confidence

If semantic signals are unavailable, weights are renormalized and retrieval
continues instead of failing.

## Enrichment Model

Every write or ingest path that stores a fact now enriches it with:

- entities
- people
- projects
- topics
- dates
- times
- locations
- intent/type
- source channel
- salience score
- source confidence
- canonical `entity_keys`, `person_keys`, `project_keys`, `topic_keys`
- lightweight `cluster_keys`

The extraction is intentionally heuristic and local. It is deterministic,
fast, and testable, not LLM-dependent.

## Operator Commands

With `memory.provider: holographic` active:

```bash
hermes holographic status
hermes holographic reindex
hermes holographic inspect <fact_id>
hermes holographic query-debug "Hermes deploy checklist"
```

Command mapping to the Phase 1 operator asks:

- `status` -> index status / coverage
- `reindex` -> drain pending deferred ingest, then rebuild derived state
- `inspect` -> memory inspect
- `query-debug` -> memory query debug
- `hermes doctor` -> concise global health summary when `memory.provider: holographic` is active

`hermes holographic status` now exposes:

- pending / failed / processing deferred-ingest counts
- oldest pending item timestamp
- last successful ingest time
- last ingest error summary
- queue reject count
- reindex state (`idle`, `running`, `completed`, `failed`)

Global doctor behavior:

- `hermes doctor` shows a single holographic summary line only when the
  holographic provider is active.
- Healthy state is `OK` with compact counts.
- Degraded state is `WARN`, not `FAIL`, for:
  - failed deferred-ingest items
  - stale pending/processing backlog
  - reindex running
  - reindex failed
- Use holographic-specific commands for full detail and recovery.

## Config And Env

Config path:

- `$HERMES_HOME/config.yaml`
- section: `plugins.hermes-memory-store`

Key knobs:

- `db_path`
- `auto_extract`
- `deferred_ingest`
- `turn_understanding`
- `ingest_batch_size`
- `ingest_max_pending`
- `ingest_retry_delay_seconds`
- `session_ingest_message_limit`
- `default_trust`
- `hrr_dim`
- `link_threshold`
- `temporal_decay_half_life`
- `semantic_provider`
- `semantic_model`
- `semantic_dimensions`
- `semantic_base_url`
- `rank_semantic_weight`
- `rank_keyword_weight`
- `rank_recency_weight`
- `rank_salience_weight`
- `rank_confidence_weight`

Optional env:

- `HOLOGRAPHIC_OPENAI_API_KEY`
- `OPENAI_API_KEY`
- `HOLOGRAPHIC_OPENAI_BASE_URL`
- `OPENAI_BASE_URL`

## Failure Modes

- Missing embedding credentials:
  Semantic embedding path is skipped. HRR and keyword retrieval remain active.
- Missing NumPy:
  HRR path is skipped. Keyword and metadata ranking remain active.
- Deferred ingest failure:
  The queue item is retained, marked failed, and retried later with backoff.
  Normal agent operation continues.
- Deferred ingest queue full:
  New understanding items are skipped rather than blocking the agent. Status
  shows the reject count and last error summary.
- Interrupted process during ingest:
  `processing` items are recovered to `failed` on next startup and retried.
- Reindex on an existing store:
  Facts are preserved. Derived metadata, vectors, links, and canonical keys
  are rebuilt. Pending deferred-ingest items can be drained first.
- Stale links:
  Run `hermes holographic reindex`.

Recommended operator flow:

1. `hermes doctor`
2. If holographic shows `WARN`, run `hermes holographic status`
3. Use `hermes holographic inspect <fact_id>` or `query-debug` for diagnosis
4. Run `hermes holographic reindex` to recover derived state / drain backlog

## Inspecting What Hermes Knows

For a single fact:

```bash
hermes holographic inspect 42
```

For explainable recall:

```bash
hermes holographic query-debug "Alice Johnson deployment preferences"
```

The debug output includes:

- why a fact matched
- score breakdown
- matched entities/topics/terms
- matched canonical clusters
- recency contribution
- related memory IDs

`hermes holographic inspect <fact_id>` shows:

- raw entities / people / projects / topics
- canonical keys used for alias grouping
- cluster keys
- related-memory links with reasons

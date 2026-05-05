# Holographic Memory Provider

Local SQLite understanding-oriented memory store with:

- hybrid recall: keyword + semantic + recency + salience + confidence
- structured enrichment: entities, people, projects, topics, dates/times, locations, intent, source channel
- bounded deferred turn/session understanding ingestion with retryable queue status
- canonical keys / lightweight clustering for people, projects, and topics
- related-memory linking across repeated mentions
- explain/debug retrieval output
- optional OpenAI-compatible embeddings with graceful fallback

## Requirements

None for the base path — uses SQLite (always available). NumPy is optional for HRR algebra.

Optional semantic embeddings:

- `semantic_provider: openai`
- `HOLOGRAPHIC_OPENAI_API_KEY` or `OPENAI_API_KEY`
- optional `semantic_base_url` for OpenAI-compatible endpoints

## Setup

```bash
hermes memory setup    # select "holographic"
```

Or manually:
```bash
hermes config set memory.provider holographic
```

## Config

Config in `config.yaml` under `plugins.hermes-memory-store`:

| Key | Default | Description |
|-----|---------|-------------|
| `db_path` | `$HERMES_HOME/memory_store.db` | SQLite database path |
| `auto_extract` | `false` | Auto-extract facts at session end |
| `deferred_ingest` | `true` | Enable durable deferred understanding ingestion |
| `turn_understanding` | `true` | Extract understanding from user turns |
| `ingest_batch_size` | `2` | Number of deferred items drained per bounded pass |
| `ingest_max_pending` | `200` | Max deferred-ingest queue depth before new items are rejected |
| `ingest_retry_delay_seconds` | `60` | Base retry delay for failed deferred-ingest items |
| `session_ingest_message_limit` | `80` | Max session messages captured for deferred session ingestion |
| `default_trust` | `0.5` | Default trust score for new facts |
| `hrr_dim` | `1024` | HRR vector dimensions |
| `link_threshold` | `0.36` | Minimum score for related-memory links |
| `temporal_decay_half_life` | `45` | Recency half-life in days |
| `semantic_provider` | `none` | `none` or `openai` |
| `semantic_model` | `text-embedding-3-small` | Embedding model when `semantic_provider=openai` |
| `semantic_dimensions` | `1536` | Optional embedding dimension override |
| `semantic_base_url` | `` | Optional OpenAI-compatible base URL |
| `rank_semantic_weight` | `0.35` | Retrieval weight: semantic relevance |
| `rank_keyword_weight` | `0.25` | Retrieval weight: keyword relevance |
| `rank_recency_weight` | `0.15` | Retrieval weight: recency |
| `rank_salience_weight` | `0.15` | Retrieval weight: salience |
| `rank_confidence_weight` | `0.10` | Retrieval weight: source confidence / trust |

## Tools

| Tool | Description |
|------|-------------|
| `fact_store` | 9 actions: add, search, probe, related, reason, contradict, update, remove, list |
| `fact_feedback` | Rate facts as helpful/unhelpful (trains trust scores) |

`fact_store(action="search", debug=true)` returns explain/debug scoring details.

## Operator Commands

When `holographic` is the active memory provider:

```bash
hermes holographic status
hermes holographic reindex
hermes holographic inspect <fact_id>
hermes holographic query-debug "your query"
```

These cover the Phase 1 operator flows:

- index status / coverage
- full reindex of enrichment, vectors, optional embeddings, and links
- inspection of a single stored memory and its related memories
- explainable recall with score breakdowns

`status` now includes:

- pending / failed / processing deferred-ingest counts
- last successful ingest time
- last ingest error summary
- queue reject count
- reindex status and timestamps

Global visibility:

- `hermes doctor` shows a concise holographic summary only when
  `memory.provider: holographic` is active.
- Healthy holographic state is reported as `OK`.
- Degraded holographic state is reported conservatively as `WARN` for backlog,
  failed ingest items, or reindex issues.
- Use `hermes holographic status` for full operator detail and recovery state.

`inspect` now includes canonical keys / cluster keys so operators can see how
alias grouping is working.

`reindex` drains pending deferred-ingest items by default before rebuilding
derived understanding state.

## Runtime Model

- synchronous writes:
  - explicit `fact_store(action=\"add\")`
  - built-in memory mirroring from `memory` tool writes
- deferred writes:
  - turn understanding queued from `sync_turn()`
  - session extraction queued from `on_session_end()` when `auto_extract=true`

Deferred ingestion is durable but intentionally lightweight:

- queue stored in the same SQLite DB
- no separate always-on worker
- bounded queue with reject counting
- retry with backoff
- interrupted `processing` items are recovered on next startup

## Failure Modes

- If embeddings are not configured or fail, retrieval falls back to keyword + HRR + metadata scoring.
- If NumPy is unavailable, HRR-based semantic features are skipped and retrieval falls back to keyword + metadata scoring.
- If deferred ingest fails, the item stays queued with failure state and retries later; normal agent operation continues.
- If the deferred queue fills, new understanding items are skipped rather than blocking the agent; see `hermes holographic status`.
- Reindexing never deletes facts; it only rebuilds derived enrichment, vectors, and links.

## Operator Workflow

1. Run `hermes doctor` for the concise global summary.
2. If holographic is warned, run `hermes holographic status`.
3. Use `inspect` or `query-debug` to inspect specific memories / matches.
4. Run `hermes holographic reindex` to drain backlog and rebuild derived state.

---
name: memory-tree-pipeline
description: "OpenHuman-inspired memory system: async pipeline, auto-fetch, cross-agent sharing, subconscious loop. Turns 5 knowledge stores into one unified memory."
tags: [memory, knowledge-graph, sync, pipeline]
related_skills: [wiki-obsidian-sync, add-new-knowledge, llm-wiki, obsidian]
---

# Memory Tree Pipeline

An OpenHuman-inspired memory system for Hermes Agent that unifies LLM Wiki, Obsidian Vault, TheBrain, and Memory Graph into a single auto-syncing pipeline.

## Quick Start

```bash
# Initialize the database
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/pipeline.py stats

# Backfill existing content
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/backfill.py

# Start workers (in background)
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/pipeline.py workers &

# Run auto-fetch once
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/auto_fetch.py

# Run subconscious tick
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/subconscious.py tick

# Search memory
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/retrieve.py search "neural networks" --limit=5

# Browse entity topic
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/retrieve.py topic "Hermes Agent"

# Get today's digest
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/retrieve.py digest

# Pipeline health
python3 ~/.hermes/skills/memory-tree-pipeline/scripts/retrieve.py status
```

## Architecture

6-stage async pipeline: Ingest → Queue → Workers → Trees → Scheduler → Lifecycle

### Data Flow
1. **Sources** (Obsidian, Wiki, TheBrain, Apple Notes, Chat) → **Auto-Fetch** (20min cron)
2. **Auto-Fetch** → **Ingest** (canonicalize, chunk, fast-score)
3. **Ingest** → **Job Queue** (SQLite) → **Workers** (3 parallel, LLM-gated)
4. **Workers** → extract entities/relations → build source/topic/global trees
5. **Trees** → **Sync** → push to Obsidian, Wiki, TheBrain, Memory Graph, agentmemory
6. **Subconscious** (5min cron) → evaluate tasks against Memory Tree state

### Components

| Script | Purpose |
|--------|---------|
| `pipeline.py` | Main CLI: ingest, workers, stats, digest, flush |
| `auto_fetch.py` | Periodic sync from all sources |
| `backfill.py` | One-time bulk ingest of existing content |
| `sync.py` | Push entities to Obsidian, Wiki, TheBrain, Memory Graph |
| `agentmemory_bridge.py` | Cross-agent memory via agentmemory daemon |
| `retrieve.py` | Search, drill-down, topic browse, digest, pipeline status |
| `subconscious.py` | Background task evaluation and execution |
| `workers.py` | Async job worker pool |

### Environment Variables
- `ANTHROPIC_API_KEY` — Primary LLM for entity extraction and summaries (config.py auto-loads from ~/.hermes/.env)
- `GROQ_API_KEY` — Fallback LLM (if Anthropic unavailable). Default key hardcoded in config.py but may expire
- `THEBRAIN_API_KEY` — Optional, for TheBrain sync
- `OPENAI_API_KEY` — Optional, for embeddings
- `AGENTMEMORY_URL` — Optional, defaults to http://localhost:3111

### LLM Provider Priority
The extractor and tree summarizer try **Anthropic first** (better extraction quality), then fall back to **Groq** (free/fast). Config.py loads `~/.hermes/.env` automatically so API keys don't need to be manually exported. The Groq free tier key can return 403 if expired — Anthropic is the reliable path.

### Cron Jobs
- Auto-fetch: every 20 minutes
- Subconscious: every 5 minutes
- Daily digest: midnight UTC
- Sync push: every 6 hours

## Parallel Extraction (Speed Trick)

The default worker pool processes ~6 chunks/min (sequential job queue). For bulk processing (backfill, catch-up), use `fast_extract.py` which bypasses the job queue and runs extraction with Python ThreadPoolExecutor:

```bash
# 10 threads, 300 chunk batch — processes ~0.7 chunks/sec with Anthropic
python3 scripts/fast_extract.py 10 300

# Or run MULTIPLE worker pool instances simultaneously — SQLite's atomic
# claim_job() prevents double-processing:
python3 scripts/pipeline.py workers &
python3 scripts/pipeline.py workers &
python3 scripts/pipeline.py workers &
# This gives 15 workers (5 per pool) with 9 LLM slots total
```

The fast_extract approach took 558 pending chunks → 0 in ~3 minutes (vs ~93 min with a single worker pool). Safe to run alongside queue workers — uses atomic status checks to skip chunks already claimed.

After bulk extraction, always run maintenance:
```bash
python3 scripts/maintenance.py all  # dedup entities, recompute hotness, fix buffers
```

## Entity Report with Source Traceability

```bash
# Rich report: entities with source files, relations, sample quotes
python3 scripts/retrieve.py report --limit=50
```

Each entity shows which Obsidian/Wiki/TheBrain files it appears in, so users can investigate further. This is the primary "browse the knowledge graph" interface.

## Maintenance

Run periodically (or after bulk operations):
```bash
python3 scripts/maintenance.py all      # dedup + hotness + buffers
python3 scripts/maintenance.py dedup    # merge case-insensitive duplicates + known aliases
python3 scripts/maintenance.py hotness  # recalculate: mentions × recency × cross-source
```

The dedup function handles: case-insensitive merging ("CSS" + "css"), known aliases ("Vincent W" + "vincent-w" + "Vincent"), and transfers chunk links + mention counts to the canonical entity.

Hotness formula: `mention_count × recency_weight × cross_source_bonus` where recency decays from 1.0 (today) to 0.1 (30+ days) and cross-source gives 1.5x if entity spans 2+ source_ids.

## Pitfalls

### API & Rate Limits
- TheBrain API has ~50 req/min limit; always use 2.0s delay between calls
- Groq free tier keys expire or get 403 — always prefer Anthropic for extraction. The extractor has automatic fallback: Anthropic → Groq → empty (graceful degradation)
- Workers use a threading semaphore (default: 2 concurrent) to avoid rate-limit storms on the LLM provider
- config.py auto-loads `~/.hermes/.env` so child Python processes inherit Hermes API keys without manual export

### Infrastructure
- agentmemory must be running separately (`npx -y @agentmemory/agentmemory`)
- Memory Graph MCP sync writes a JSON file at `~/.hermes/memory_tree/memory_graph_sync.json`; Hermes must execute the MCP calls separately (the pipeline is a standalone Python process, not an MCP server)
- Cron wrapper scripts live at `~/.hermes/scripts/memory_tree_*.py` because Hermes cron `script` paths must be relative to `~/.hermes/scripts/`. These thin wrappers just add the skill's scripts dir to sys.path and call the main function.

### Chat Provider
- The Hermes state.db sessions table uses `started_at` (REAL epoch timestamp), NOT `created_at`. The chat provider was fixed to use this column name. If state.db schema changes in a Hermes update, the chat provider may need re-patching.
- Session messages are in a separate `messages` table joined by `session_id`. The provider pulls the first 3 assistant messages as preview content.

### Backfill & Auto-Fetch
- Initial backfill of ~285 docs (Obsidian + Wiki) produces ~1,024 chunks — all start as `pending_extraction`. These won't be processed until workers run with a valid GROQ_API_KEY.
- Auto-fetch deduplicates by content hash — re-running on unchanged files produces 0 new chunks (safe to run repeatedly)
- TheBrain and Apple Notes providers return "unavailable" if API key / memo CLI not configured — this is expected, not an error

### Hermes Cron Script Wrapper Pattern
Hermes cron `script` paths must be relative to `~/.hermes/scripts/`. The pipeline scripts live in the skill directory, so thin wrapper scripts at `~/.hermes/scripts/memory_tree_*.py` add the skill's scripts dir to sys.path and call the main function. If you need to add a new cron job for a skill script, follow this pattern — don't try to use absolute paths in the `script` field.

## References

- `references/architecture.md` — full system architecture diagram and design decisions
- `references/parallel-llm-extraction.md` — reusable pattern for 30x faster bulk LLM processing with ThreadPoolExecutor

### Known Cron Job IDs
- `ab4f36a8731b` — auto-fetch (every 20m)
- `4e7f02547dca` — subconscious (every 30m)
- `bb3753f49c90` — daily digest (midnight)
- `522c20a24885` — sync push (every 6h)

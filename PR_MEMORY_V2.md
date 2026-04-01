## What does this PR do?

Replaces the flat-file memory system (MEMORY.md / USER.md) with a SQLite-backed engine featuring full-text search, tiered lifecycle, and budget enforcement.

### Why

The current memory system stores entries as raw text lines delimited by `§` in two markdown files. It has no search (everything is injected verbatim into the system prompt), no deduplication, no lifecycle management, and a hard capacity of ~3.5KB across both files (~25-30 short entries). When the files fill up, the agent must manually delete entries to make room.

### What changes

The new engine stores memories as typed records in SQLite with FTS5 indexing. Search is ranked by BM25 relevance, recency, and access frequency — not just "show everything." Memories have a lifecycle: active entries live in the prompt, stale or low-value entries are automatically archived, and near-duplicates are superseded on write. A configurable budget (default: 50 memory / 25 user active entries) keeps the prompt lean without manual curation.

Optional features (disabled by default, zero cost if unused):
- **Embedding-based semantic search** — cosine similarity blended with BM25, with a 4-level provider cascade (local fastembed → configured model → auto-detect from env → BM25-only fallback)
- **Auto-extraction** — background extraction of durable memories from conversations via auxiliary LLM
- **Consolidation** — periodic LLM-driven merge/update/archive of memory entries
- **Session memory** — structured 9-section session notes for context restoration in long sessions

Migration from existing flat files is automatic on first load. Setting `memory.engine: flat` in config.yaml preserves the old behavior entirely.

## Related Issue

No existing issue — this is a new feature.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

### Core (the engine)

| File | Lines | Purpose |
|------|------:|---------|
| `tools/memory_engine.py` | 1,429 | SQLite engine: schema, FTS5 search with BM25, optional embedding index, knowledge graph (auto-edges via keyword overlap, BFS traversal), tiered lifecycle (active → archived → superseded → purged), budget enforcement, near-duplicate detection, flat-file migration |
| `tools/memory_tool.py` | modified | Rewired to `MemoryEngine` backend. Added `search` action with hybrid retrieval. Existing actions (add/remove/replace) preserved |
| `agent/yake.py` | 215 | YAKE keyword extraction — pure Python, zero dependencies. Used for auto-tagging and graph edge creation |
| `hermes_state.py` | modified | Engine initialization, lifecycle hooks |
| `run_agent.py` | modified | Engine wired into agent init and session end (archive stale, enforce budget, purge dead) |

### Optional subsystems

| File | Lines | Purpose |
|------|------:|---------|
| `agent/memory_extractor.py` | 428 | Auto-extraction via auxiliary LLM (opt-in) |
| `agent/memory_consolidator.py` | 266 | 5-gate consolidation scheduler (opt-in) |
| `agent/session_memory.py` | 307 | Structured session notes (opt-in) |

### Documentation and tests

| File | Lines | Purpose |
|------|------:|---------|
| `docs/MEMORY_V2.md` | 742 | Full architecture documentation |
| `tests/tools/test_memory_engine.py` | 448 | Engine tests: CRUD, search, lifecycle, budget, dedup, migration, graph |
| `tests/agent/test_memory_extractor.py` | 347 | Extraction pipeline tests |
| `tests/agent/test_memory_consolidator.py` | 179 | Consolidation gate tests |
| `tests/agent/test_session_memory.py` | 153 | Session memory tests |

### Architecture highlights

**Search**: `score = BM25 × recency_decay × strength × tier_weight × type_boost`, where recency follows power-law decay `(1 + hours)^-0.3` and strength uses logarithmic reinforcement `1.0 + 0.1 × ln(1 + access_count)`.

**Lifecycle**: Memories start active. Accessed memories get stronger. Untouched memories weaken and archive after 90 days. Near-duplicates are superseded (BM25 > 8.0 or cosine > 0.92). Budget enforcement archives the weakest entries first, protecting corrections and preferences.

**Memory types**: `general`, `preference`, `correction`, `project`, `reference` — classified on write, enabling type-aware scoring (corrections get 1.3× boost) and lifecycle policies (corrections/preferences resist archival).

**Security**: Prompt injection detection, exfiltration pattern matching, invisible unicode detection — carried forward from the existing system.

## How to Test

1. **Run the test suite**:
   ```bash
   source venv/bin/activate
   python -m pytest tests/tools/test_memory_engine.py tests/tools/test_memory_tool.py tests/agent/test_memory_consolidator.py tests/agent/test_memory_extractor.py tests/agent/test_session_memory.py -q
   ```

2. **Automatic migration**: Start a session with existing MEMORY.md/USER.md files:
   ```bash
   hermes -q "Use the memory tool to search for anything"
   ls ~/.hermes/memories/  # memory.db + .md.bak files
   ```

3. **Memory CRUD**:
   ```bash
   hermes -q "Save a memory that my favorite color is blue, then search for 'color'"
   ```

4. **Backward compat**: Set `memory.engine: flat` in config.yaml, confirm original behavior.

5. **Full suite**: `pytest tests/ -q` — 7,424 tests pass.

## Configuration

All settings under `memory:` in config.yaml. Sensible defaults — no configuration required.

```yaml
memory:
  engine: sqlite              # "sqlite" or "flat" (legacy)
  max_active_memory: 50       # Budget cap: memory target
  max_active_user: 25         # Budget cap: user target
  # Optional subsystems (off by default, no cost if unused):
  auto_extract: false         # Auto-extraction via auxiliary LLM
  consolidation: false        # Periodic consolidation at session end
  session_memory: false       # Structured session notes
  embeddings: false           # Vector embeddings (falls back to BM25-only)
  importance_threshold: 5     # Min score (1-10) for auto-extracted memories
```

## Checklist

### Code

- [x] I've read the [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md)
- [x] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
- [x] I searched for [existing PRs](https://github.com/NousResearch/hermes-agent/pulls) to make sure this isn't a duplicate
- [x] My PR contains **only** changes related to this fix/feature
- [x] I've run `pytest tests/ -q` and all tests pass
- [x] I've added tests for my changes
- [x] I've tested on my platform: Ubuntu 24.04 (WSL2)

### Documentation & Housekeeping

- [x] I've updated relevant documentation — `docs/MEMORY_V2.md` (742 lines)
- [ ] I've updated `cli-config.yaml.example` — TODO: add `memory:` section
- [x] I've considered cross-platform impact — SQLite is stdlib, fastembed is optional, all paths use `get_hermes_home()`
- [x] I've updated tool descriptions/schemas — `search` action added to memory tool

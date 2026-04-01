## What does this PR do?

Upgrades the curated memory store (MEMORY.md / USER.md) from flat text files to a SQLite-backed engine with full-text search, tiered lifecycle, and budget enforcement.

### Context: where this fits in the memory stack

Hermes already has strong episodic memory (session_search over the full conversation SQLite DB) and procedural memory (skills). What it lacks is a capable **declarative memory** layer — the curated facts, preferences, and corrections that get injected into the system prompt every turn.

The current declarative store is two markdown files with a `§` delimiter, a 3.5KB combined cap, no search within the store, no deduplication, and no lifecycle management. When the files fill up, the agent must manually delete entries to make room. Every entry is injected verbatim regardless of relevance.

### What this changes

The new engine stores curated memories as typed records in SQLite with FTS5 indexing. Key improvements:

- **Search within curated memory** — BM25-ranked retrieval instead of injecting everything. The agent can search its own notes by topic without falling back to session_search (which searches raw transcripts and requires LLM summarization per query).
- **Memory types** — `general`, `preference`, `correction`, `project`, `reference`. Corrections get 1.3× scoring boost and resist archival because they're the most expensive to relearn.
- **Tiered lifecycle** — active → archived → superseded → purged. Memories that get accessed grow stronger (logarithmic reinforcement). Unused memories fade and archive after 90 days. Near-duplicates are auto-superseded on write.
- **Budget enforcement** — configurable caps (default 50 memory / 25 user active entries). Weakest entries archived first. No more manual curation.
- **Flat-file migration** — existing MEMORY.md/USER.md entries are automatically imported on first load. `memory.engine: flat` preserves old behavior.

Optional subsystems (off by default, zero cost if unused):
- Embedding-based semantic search (cosine similarity blended with BM25)
- Auto-extraction of memories from conversations via auxiliary LLM
- Periodic LLM-driven consolidation
- Structured session notes

This complements session_search and skills — it doesn't replace them. Session search is episodic recall ("what happened"). Skills are procedural ("how to do X"). This is declarative ("what I know"), now with proper storage.

## Related Issue

No existing issue — this is a new feature.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

### Core engine

| File | Lines | Purpose |
|------|------:|---------|
| `tools/memory_engine.py` | 1,429 | SQLite engine: FTS5 search with BM25, tiered lifecycle, budget enforcement, near-duplicate detection, auto-tagging via YAKE keywords, knowledge graph edges for search expansion, flat-file migration |
| `tools/memory_tool.py` | modified | Rewired to `MemoryEngine` backend. Added `search` action. Existing actions (add/remove/replace) preserved |
| `agent/yake.py` | 215 | YAKE keyword extraction — pure Python, zero dependencies. Auto-tags memories for search and graph edges |
| `hermes_state.py` | modified | Engine initialization, lifecycle hooks |
| `run_agent.py` | modified | Engine wired into agent init and session end (archive stale, enforce budget, purge dead) |

### Optional subsystems

| File | Lines | Purpose |
|------|------:|---------|
| `agent/memory_extractor.py` | 428 | Auto-extraction via auxiliary LLM (opt-in) |
| `agent/memory_consolidator.py` | 266 | 5-gate consolidation scheduler (opt-in) |
| `agent/session_memory.py` | 307 | Structured session notes (opt-in) |

### Documentation and tests

| File | Lines |
|------|------:|
| `docs/MEMORY_V2.md` | 742 |
| `tests/tools/test_memory_engine.py` | 448 |
| `tests/agent/test_memory_extractor.py` | 347 |
| `tests/agent/test_memory_consolidator.py` | 179 |
| `tests/agent/test_session_memory.py` | 153 |

## How to Test

1. **Test suite**: `python -m pytest tests/tools/test_memory_engine.py tests/tools/test_memory_tool.py tests/agent/ -q`
2. **Migration**: Start a session with existing flat files → auto-imported, originals renamed to `.bak`
3. **Backward compat**: Set `memory.engine: flat` → original behavior preserved
4. **Full suite**: `pytest tests/ -q` — 7,424 tests pass

## Configuration

```yaml
memory:
  engine: sqlite              # "sqlite" or "flat" (legacy)
  max_active_memory: 50       # Budget cap: memory target
  max_active_user: 25         # Budget cap: user target
  # Optional (off by default):
  auto_extract: false
  consolidation: false
  session_memory: false
  embeddings: false
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
- [x] I've updated `cli-config.yaml.example` — added `memory:` section with all V2 keys
- [x] I've considered cross-platform impact — SQLite is stdlib, fastembed is optional, all paths use `get_hermes_home()`
- [x] I've updated tool descriptions/schemas — `search` action added to memory tool

# feat: Memory V2 — SQLite-backed knowledge system with hybrid search, graph, and auto-extraction

## Summary

Replaces the flat-file memory store with a full SQLite-backed knowledge system featuring FTS5 full-text search, optional embedding-based semantic search, a relationship graph, automatic knowledge extraction from conversations, session memory injection, and a 5-gate consolidation scheduler with tiered lifecycle management. The migration from flat files is automatic and backward-compatible — existing memories are imported on first load with no user action required.

---

## What Changed

### New Files

| File | Lines | Purpose |
|------|------:|---------|
| `tools/memory_engine.py` | 2,010 | Core SQLite engine: FTS5 search, embedding index, relationship graph, tiered lifecycle (active → archive → tombstone), importance scoring, budget enforcement, cursor-based pagination |
| `agent/memory_extractor.py` | 428 | Automatic knowledge extraction from conversation turns via auxiliary LLM — identifies facts, preferences, procedures, events; classifies and deduplicates before storage |
| `agent/session_memory.py` | 301 | Session-scoped memory: injects relevant memories into system prompt at session start, tracks what was surfaced to avoid repetition |
| `agent/memory_consolidator.py` | 266 | 5-gate consolidation scheduler: staleness check, duplicate merge, importance decay, archive promotion, and purge — runs on configurable intervals |
| `agent/yake.py` | 215 | Pure-Python YAKE keyword extraction (no external dependencies) for memory tagging and search enhancement |
| `MEMORY_V2_PLAN.md` | 422 | Implementation plan and architecture documentation |
| `tests/tools/test_memory_engine.py` | 448 | MemoryEngine unit tests: CRUD, FTS5 search, graph operations, lifecycle transitions, budget enforcement |
| `tests/agent/test_memory_extractor.py` | 347 | Extraction pipeline tests: LLM output parsing, deduplication, classification |
| `tests/agent/test_memory_consolidator.py` | 179 | Consolidation gate tests: scheduling, staleness, merge behavior |
| `tests/agent/test_session_memory.py` | 136 | Session memory injection and retrieval tests |
| `tests/agent/test_yake.py` | 98 | YAKE keyword extraction accuracy tests |

### Modified Files

| File | Change |
|------|--------|
| `tools/memory_tool.py` | Rewired to use `MemoryEngine` backend; added `search` action with hybrid (FTS5 + embedding) retrieval; added `graph` action for relationship queries; preserved all existing tool signatures for backward compat |
| `hermes_state.py` | Added memory engine initialization, session memory hooks, consolidator lifecycle management; state object now carries `memory_engine` and `session_memory` instances |
| `run_agent.py` | Wired extraction into post-turn hook, session memory into prompt assembly, consolidator into idle/shutdown; added embedding provider resolution for Hermes provider stack |
| `tests/tools/test_memory_tool.py` | Minor fixture updates for new engine backend |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  run_agent.py                     │
│  (post-turn extraction, session inject, idle      │
│   consolidation)                                  │
├──────────┬──────────────┬───────────────┬────────┤
│ Extractor│ SessionMemory│ Consolidator  │  YAKE  │
├──────────┴──────────────┴───────────────┴────────┤
│              tools/memory_engine.py                │
│  ┌──────────┬────────────┬──────────┬──────────┐ │
│  │ SQLite   │ FTS5 Index │Embeddings│  Graph   │ │
│  │(memories)│(full-text) │(semantic)│(relations)│ │
│  └──────────┴────────────┴──────────┴──────────┘ │
│              Tiered Lifecycle                      │
│         active → archive → tombstone               │
└─────────────────────────────────────────────────┘
```

For full architecture details, see `MEMORY_V2_PLAN.md`.

---

## Key Features

- **SQLite + FTS5 full-text search** — sub-millisecond keyword search across all memories, no external services
- **Optional embedding-based semantic search** — hybrid retrieval combining FTS5 BM25 scores with cosine similarity; adapts to Hermes provider stack (local Ollama, OpenAI, Anthropic)
- **Relationship graph** — memories can link to each other with typed edges (related_to, contradicts, supersedes, part_of); queryable via `memory graph` tool action
- **Automatic knowledge extraction** — auxiliary LLM extracts facts, preferences, procedures, and events from conversation turns; deduplicates against existing knowledge
- **Session memory injection** — relevant memories auto-injected into system prompt at session start based on context similarity
- **5-gate consolidation** — background scheduler handles staleness detection, duplicate merging, importance decay, archive promotion, and tombstone purge
- **Tiered lifecycle** — memories progress through active → archive → tombstone states with configurable retention budgets
- **Importance scoring** — memories scored by access frequency, recency, and explicit user signals; budget enforcement evicts lowest-importance entries first
- **Pure-Python YAKE keywords** — zero-dependency keyword extraction for automatic tagging
- **Cursor-based pagination** — efficient traversal of large memory sets
- **Flat-file migration** — existing V1 memories automatically imported on first engine initialization

---

## Breaking Changes

**None.** The flat-file to SQLite migration is automatic and backward-compatible:
- On first load, `MemoryEngine` detects existing flat-file memories and imports them into SQLite
- All existing `memory_tool.py` actions (`store`, `recall`, `list`, `delete`) continue to work with the same signatures
- New actions (`search`, `graph`) are additive
- If the SQLite DB is deleted, flat files still serve as a fallback source for re-import

---

## Testing

| Test File | Tests | Lines |
|-----------|------:|------:|
| `tests/tools/test_memory_engine.py` | Core engine CRUD, FTS5, graph, lifecycle | 448 |
| `tests/agent/test_memory_extractor.py` | Extraction pipeline, parsing, dedup | 347 |
| `tests/agent/test_memory_consolidator.py` | 5-gate scheduling, merge, decay | 179 |
| `tests/agent/test_session_memory.py` | Session injection, retrieval | 136 |
| `tests/agent/test_yake.py` | Keyword extraction accuracy | 98 |
| `tests/tools/test_memory_tool.py` | Tool interface compat (updated) | 10± |
| **Total** | | **~1,218** |

---

## Provenance

This implementation draws from multiple sources:

- **HiveMind / MAGMA** — The tiered lifecycle model (active → archive → tombstone), importance scoring with decay, and relationship graph patterns are inspired by `memory.rs` in the MAGMA framework
- **Claude Code** — The autoDream consolidation pattern, automatic extraction from conversation turns, and session memory injection patterns originate from Claude Code's memory system
- **Original work** — SQLite FTS5 hybrid search engine, YAKE keyword extraction integration, Hermes provider stack adaptation for embeddings, budget enforcement with cursor pagination, and the 5-gate consolidation scheduler are original to this implementation

---

## Commit Log

```
3406abcf wire Ollama cloud: nemotron-3-super fallback, ministral-3:3b auxiliary, OLLAMA_API_KEY resolution
57085719 memory v2: close all gaps — local embeddings, LLM reranker, procedures, events
d9313997 memory v2: lifecycle hardening — importance scoring, budget enforcement, purge, cursor persistence
6d1f78fe fix(memory): activate by default + adapt embeddings to Hermes provider stack
27b53b25 feat(memory): embeddings pipeline, hybrid search, graph tools, full wiring
1bf81da0 feat(memory): complete memory system — YAKE, graph, chunking, classification, session memory, extraction hardening
3752e1dd feat(memory): add memory consolidation with 5-gate scheduling
a443d1d4 feat(memory): add automatic memory extraction via auxiliary LLM
1da2b76f feat(memory): wire MemoryEngine into MemoryStore + add search action + type taxonomy
0d8c7637 feat(memory): add MemoryEngine — SQLite-backed memory with FTS5 search and tiered lifecycle
d66132e2 docs: memory system v2 implementation plan
83b107df feat(prompt): extensible system prompt + credential redaction (local governance)
```

---

## Stats

```
 MEMORY_V2_PLAN.md                       |  422 +++++++
 agent/memory_consolidator.py            |  266 ++++
 agent/memory_extractor.py               |  428 +++++++
 agent/session_memory.py                 |  301 +++++
 agent/yake.py                           |  215 ++++
 hermes_state.py                         |  404 +++++--
 run_agent.py                            | 1352 ++++++++++++++++++---
 tests/agent/test_memory_consolidator.py |  179 +++
 tests/agent/test_memory_extractor.py    |  347 ++++++
 tests/agent/test_session_memory.py      |  136 +++
 tests/agent/test_yake.py               |   98 ++
 tests/tools/test_memory_engine.py       |  448 +++++++
 tests/tools/test_memory_tool.py         |   10 +-
 tools/memory_engine.py                  | 2010 +++++++++++++++++++++++++++++++
 tools/memory_tool.py                    |  461 ++++---
 15 files changed, 6685 insertions(+), 392 deletions(-)
```

**Net delta: +6,293 lines**

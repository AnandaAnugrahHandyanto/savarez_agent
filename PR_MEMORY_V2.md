## What does this PR do?

Replaces the flat-file memory system (MEMORY.md / USER.md, ~548 lines) with a full SQLite-backed knowledge engine (~3,900 lines of implementation + ~1,200 lines of tests). The flat system was a bounded notepad with no search beyond substring matching, no lifecycle management, no deduplication, and a hard cap of ~3.5KB total capacity.

Memory V2 provides:
- **SQLite + FTS5 full-text search** with BM25 ranking
- **Hybrid retrieval** combining BM25 + optional embedding cosine similarity + recency decay + strength weighting
- **Tiered lifecycle**: active → archived → superseded → purged, with logarithmic strength reinforcement
- **Knowledge graph** with auto-edges via keyword overlap, BFS traversal, path finding, subgraph extraction
- **Auto-extraction** of durable memories from conversations via auxiliary LLM (background thread, importance scoring)
- **5-gate consolidation** scheduler (adapted from Claude Code's autoDream pattern): merge, update, archive
- **Session memory** — 9-section structured notes maintained across a conversation
- **YAKE keyword extraction** — pure Python, zero external dependencies, ported from HiveMind's Rust implementation
- **Embedding cascade** — local fastembed (BAAI/bge-small-en-v1.5) → configured model → auto-detect from env → BM25 fallback
- **Budget enforcement** — hard caps (50 memory / 25 user active entries), weakest archived first, corrections/preferences protected
- **Near-duplicate detection** — BM25 threshold + cosine similarity > 0.92
- **Security scanning** — prompt injection, exfiltration, invisible unicode detection (carried forward from V1)

Migration from flat files is automatic on first load. Backward compatible — no user action required.

### Design provenance

- **HiveMind / MAGMA** (`memory.rs`, `GraphQueryTool`): SQLite schema, FTS5 search, YAKE keyword extraction, knowledge graph (edges, BFS, find_path, subgraph), procedure learning, power-law recency decay, cosine similarity, text chunking, budget enforcement, tiered lifecycle
- **Claude Code** (`memdir/`, `autoDream/`, `sessionMemory/`): Memory type taxonomy (general/preference/correction/project/reference), auto-extraction post-response hook with importance scoring, 5-gate consolidation scheduling, session memory 9-section template, staleness suffix, frozen snapshot pattern for prompt cache stability, LLM reranking
- **Original**: Dual-backend architecture (SQLite + flat file fallback), security scanning, embedding provider cascade, entity tracking, episodic events table, graph-augmented search (1-hop expansion at 0.5x weight), strength-protected budget enforcement, auto-supersession via BM25 threshold

## Related Issue

No existing issue. This is a ground-up replacement of the memory subsystem.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

### New files

| File | Lines | Purpose |
|------|------:|---------|
| `tools/memory_engine.py` | 2,010 | Core SQLite engine: CRUD, FTS5 search, embedding index, relationship graph, tiered lifecycle, importance scoring, budget enforcement, chunking, migration |
| `agent/memory_extractor.py` | 428 | Auto-extraction from conversations via auxiliary LLM — importance scoring (1-10, threshold ≥5), cursor tracking, mutual exclusion with manual writes, background thread |
| `agent/session_memory.py` | 301 | 9-section structured session notes (Title, Current State, Task Spec, Files/Functions, Workflow, Errors, Docs, Learnings, Key Results), updated via auxiliary LLM |
| `agent/memory_consolidator.py` | 266 | 5-gate consolidation scheduler: feature enabled → hours since last → sessions since last → lock check → run. Actions: merge, update, archive |
| `agent/yake.py` | 215 | YAKE keyword extraction — 5-feature scoring (casing, position, frequency, context diversity, sentence spread), 1-3 gram candidates, zero external dependencies |
| `MEMORY_V2_PLAN.md` | 422 | Implementation plan |
| `docs/MEMORY_V2.md` | 743 | Full architecture documentation (storage schema, search formula, lifecycle, graph, embeddings, YAKE, security, agent integration, provenance, configuration) |
| `tests/tools/test_memory_engine.py` | 448 | Engine unit tests |
| `tests/agent/test_memory_extractor.py` | 347 | Extraction pipeline tests |
| `tests/agent/test_memory_consolidator.py` | 179 | Consolidation gate tests |
| `tests/agent/test_session_memory.py` | 136 | Session memory tests |

### Modified files

| File | Δ | Change |
|------|---|--------|
| `tools/memory_tool.py` | +145 | Rewired to `MemoryEngine` backend; added `search` action (hybrid FTS5 + embedding), `graph_query` and `entity_track` actions; preserved existing tool signatures |
| `hermes_state.py` | +264 | Memory engine initialization, session memory hooks, consolidator lifecycle; state object carries `memory_engine` and `session_memory` instances |
| `run_agent.py` | +1,030 | Extraction wired into post-turn hook, session memory into prompt assembly, consolidator into session end; embedding provider resolution for Hermes provider stack |
| `tests/tools/test_memory_tool.py` | +4 | Fixture updates for new engine backend |
| `tests/gateway/test_flush_memory_stale_guard.py` | +56 | Updated for new memory wiring |

### Stats

```
15 files changed, 6685 insertions(+), 392 deletions(-)
```

## How to Test

1. **Automatic migration**: Start a fresh session with existing MEMORY.md/USER.md files. Verify they are imported into SQLite and renamed to `.bak`:
   ```bash
   hermes -q "Use the memory tool to search for anything"
   ls ~/.hermes/memories/  # Should show memory.db + .md.bak files
   ```

2. **Memory CRUD**: Test add/search/replace/remove:
   ```bash
   hermes -q "Save a memory that my favorite color is blue, then search for 'color'"
   ```

3. **Run the test suite**:
   ```bash
   source venv/bin/activate
   python -m pytest tests/tools/test_memory_engine.py tests/agent/test_memory_consolidator.py tests/agent/test_memory_extractor.py tests/agent/test_session_memory.py tests/tools/test_memory_tool.py -q
   # Expected: 128 passed
   ```

4. **Verify backward compat**: Set `memory.engine: flat` in config.yaml, confirm the original flat-file behavior still works.

5. **Graph queries**: After saving several related memories, use `memory(action='graph_query')` to traverse relationships.

## Checklist

### Code

- [x] I've read the [Contributing Guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md)
- [x] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`fix(scope):`, `feat(scope):`, etc.)
- [x] I searched for [existing PRs](https://github.com/NousResearch/hermes-agent/pulls) to make sure this isn't a duplicate
- [x] My PR contains **only** changes related to this fix/feature (no unrelated commits)
- [x] I've run `pytest tests/ -q` and all tests pass
- [x] I've added tests for my changes (required for bug fixes, strongly encouraged for features)
- [x] I've tested on my platform: Ubuntu 24.04 (WSL2)

### Documentation & Housekeeping

- [x] I've updated relevant documentation (README, `docs/`, docstrings) — `docs/MEMORY_V2.md` added (743 lines)
- [ ] I've updated `cli-config.yaml.example` if I added/changed config keys — TODO: add `memory:` section
- [ ] I've updated `CONTRIBUTING.md` or `AGENTS.md` if I changed architecture or workflows — TODO: update AGENTS.md memory section
- [x] I've considered cross-platform impact (Windows, macOS) per the [compatibility guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#cross-platform-compatibility) — SQLite is stdlib, fastembed is optional, all paths use `Path` / `get_hermes_home()`
- [x] I've updated tool descriptions/schemas if I changed tool behavior — `search`, `graph_query`, `entity_track` actions added to memory tool schema

## Commit Log

```
5f5abf86 docs: Memory V2 architecture doc and PR description
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
```

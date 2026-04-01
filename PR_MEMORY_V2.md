## What does this PR do?

Adds a structured memory system backed by SQLite + FTS5, replacing the flat-file approach (MEMORY.md / USER.md). The current system appends raw text lines to markdown files with no search capability beyond string matching, no deduplication, no lifecycle management, and no way to surface relevant memories without loading the entire file into context.

Memory V2 stores memories as typed, searchable records with full-text search, optional vector embeddings, a knowledge graph, automatic extraction from conversations, periodic consolidation, and a tiered lifecycle that keeps the memory store lean over time. Migration from existing flat files is automatic on first load.

## Related Issue

No existing issue — this is a new feature.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

### New files

| File | Lines | Purpose |
|------|------:|---------|
| `tools/memory_engine.py` | 1,429 | Core engine: SQLite schema, FTS5 full-text search with BM25 ranking, optional embedding index with cosine similarity, knowledge graph (auto-edges via keyword overlap, BFS traversal), tiered lifecycle (active → archived → superseded → purged), budget enforcement, near-duplicate detection, flat-file migration |
| `agent/memory_extractor.py` | 428 | Automatic extraction of durable memories from conversations via auxiliary LLM. Runs in a background thread after each agent turn. Scores importance 1–10, only persists memories scoring ≥5. Tracks a cursor so it never re-processes the same messages. Mutual exclusion with manual memory writes |
| `agent/session_memory.py` | 307 | Maintains 9-section structured session notes (Title, Current State, Task Spec, Key Files/Functions, Workflow, Errors, Docs Referenced, Learnings, Key Results) updated via auxiliary LLM. Provides a compact summary for context restoration across long sessions |
| `agent/memory_consolidator.py` | 266 | 5-gate consolidation scheduler: feature enabled → hours since last run → sessions since last run → lock check → execute. Actions: merge near-duplicates, update stale entries, archive low-value memories. Runs at session end |
| `agent/yake.py` | 215 | YAKE keyword extraction — 5-feature scoring (casing, position, frequency, context diversity, sentence spread), 1–3 gram candidates. Pure Python, zero external dependencies |
| `docs/MEMORY_V2.md` | 742 | Full architecture documentation: storage schema, search formula, lifecycle, graph, embeddings, YAKE, security, agent integration, configuration |
| `tests/tools/test_memory_engine.py` | 448 | Engine unit tests: CRUD, search, lifecycle transitions, budget enforcement, dedup, migration, graph operations |
| `tests/agent/test_memory_extractor.py` | 347 | Extraction pipeline tests: importance filtering, cursor tracking, mutual exclusion, error handling |
| `tests/agent/test_memory_consolidator.py` | 179 | Consolidation gate tests: all 5 gates, merge/update/archive actions |
| `tests/agent/test_session_memory.py` | 153 | Session memory tests: section parsing, LLM update flow, serialization |

### Modified files

| File | Change |
|------|--------|
| `tools/memory_tool.py` | Rewired to use `MemoryEngine` as backend. Added `search` action with hybrid FTS5 + embedding retrieval. Existing tool signatures (add/remove/replace) preserved for backward compatibility |
| `hermes_state.py` | Memory engine initialization, session memory hooks, consolidator lifecycle. State object carries `memory_engine` and `session_memory` instances |
| `run_agent.py` | Extraction wired into post-turn hook, session memory into prompt assembly, consolidator into session end. Embedding provider resolution for the Hermes provider stack |

### Architecture overview

**Search formula**: `score = w1·BM25 + w2·cosine_sim + w3·recency_decay + w4·strength` where recency follows power-law decay and strength uses logarithmic reinforcement on repeated access.

**Embedding cascade**: local fastembed (BAAI/bge-small-en-v1.5) → configured model provider → auto-detect from environment → graceful BM25-only fallback. Embeddings are optional — the system works without them.

**Knowledge graph**: Memories are connected via keyword overlap edges. Search expands results by traversing 1-hop neighbors at 0.5× weight, surfacing related context the user didn't explicitly query.

**Budget enforcement**: Hard caps (configurable, default 50 memory / 25 user active entries). When exceeded, lowest-strength entries are archived first. Corrections and preferences are protected from archival.

**Security scanning**: Prompt injection detection, exfiltration pattern matching, invisible unicode detection — carried forward from the existing memory system.

**Memory types**: `general`, `preference`, `correction`, `project`, `reference` — classified automatically on write, enabling type-aware retrieval and lifecycle policies.

### Stats

```
13 files changed, 6,344 insertions(+), 389 deletions(-)
```

(Memory system files only. Full branch includes unrelated upstream changes.)

## How to Test

1. **Run the dedicated test suite**:
   ```bash
   source venv/bin/activate
   python -m pytest tests/tools/test_memory_engine.py tests/agent/test_memory_consolidator.py tests/agent/test_memory_extractor.py tests/agent/test_session_memory.py tests/tools/test_memory_tool.py -q
   ```

2. **Automatic migration**: Start a session with existing MEMORY.md/USER.md files. They are imported into SQLite and renamed to `.bak`:
   ```bash
   hermes -q "Use the memory tool to search for anything"
   ls ~/.hermes/memories/  # Should show memory.db + .md.bak files
   ```

3. **Memory CRUD**:
   ```bash
   hermes -q "Save a memory that my favorite color is blue, then search for 'color'"
   ```

4. **Full test suite**: `pytest tests/ -q` — 7,424 tests pass.

## Configuration

All settings live under `memory:` in `config.yaml`. Everything has sensible defaults — no configuration required to use the feature.

```yaml
memory:
  engine: sqlite          # "sqlite" (default) or "flat" to keep old behavior
  auto_extract: true      # Enable automatic memory extraction from conversations
  consolidation: true     # Enable periodic consolidation at session end
  session_memory: true    # Enable structured session notes
  embeddings: true        # Enable vector embeddings (falls back to BM25-only if unavailable)
  max_active_memory: 50   # Budget cap for memory-type active entries
  max_active_user: 25     # Budget cap for user-type active entries
  importance_threshold: 5 # Minimum importance score (1-10) for auto-extracted memories
```

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

- [x] I've updated relevant documentation (README, `docs/`, docstrings) — `docs/MEMORY_V2.md`
- [ ] I've updated `cli-config.yaml.example` if I added/changed config keys — TODO: add `memory:` section
- [ ] I've updated `CONTRIBUTING.md` or `AGENTS.md` if I changed architecture or workflows — TODO: update AGENTS.md memory section
- [x] I've considered cross-platform impact (Windows, macOS) per the [compatibility guide](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#cross-platform-compatibility) — SQLite is stdlib, fastembed is optional, all paths use `Path` / `get_hermes_home()`
- [x] I've updated tool descriptions/schemas if I changed tool behavior — `search` action added to memory tool schema

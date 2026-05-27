---
name: enhanced-memory
description: "Enhanced Memory — two-tier fact store with condensation, FTS5, and Gemini-powered semantic search."
version: 1.0.0
author: Dmitriy Labaznov
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Memory, Semantic-Search, FTS5, SQLite, Gemini, Condensation]
    related_skills: [memory-condenser, honcho-holographic-sync]
---

# Enhanced Memory Plugin

Two-tier persistent memory with automatic condensation and semantic vector search.

## Architecture

```
User message → auto_extract → raw_facts (SQLite + FTS5)
                                    ↓
                              condenser.py (group, dedup, prioritize)
                                    ↓
                              condensed (SQLite + FTS5)
                                    ↓
                              embeddings.py (Gemini + sqlite-vec)
                                    ↓
                              vec_memory (KNN search)
```

## When to Use

- **add**: Store user preferences, decisions, env details, tool quirks
- **search**: FTS5 keyword search across both tiers (raw + condensed)
- **semantic_search**: Find by meaning, cross-language, synonym-aware (needs GOOGLE_API_KEY)
- **condense**: Group raw facts → deduplicate → prioritize → merge into condensed entries
- **list_condensed**: View memory sorted by priority
- **stats**: Check counts, index status

## Categories

| Category | Priority Range | Description |
|----------|---------------|-------------|
| security | 9-10 | SSH, keys, passwords, firewall |
| user_pref | 8-9 | User preferences and corrections |
| decision | 7-9 | Architectural and workflow decisions |
| project | 7 | Project details, requirements |
| tool | 6-8 | Tools, configs, versions |
| env | 5 | Environment, infrastructure |
| general | 4 | Everything else |

## Configuration

```yaml
# config.yaml
memory:
  provider: enhanced-memory

plugins:
  enhanced-memory:
    db_path: $HERMES_HOME/memory_store.db
    auto_extract: true
    auto_condense: true
    semantic_search: true  # requires GOOGLE_API_KEY + pip install sqlite-vec
```

## Requirements

- Core: Python 3.10+, SQLite 3.35+ (FTS5 support)
- Semantic search (optional): `pip install sqlite-vec`, `GOOGLE_API_KEY` env var

## Hooks

- `on_session_end` — auto-extract facts from conversation
- `on_memory_write` — mirror built-in memory writes as raw facts
- `on_pre_compress` — save facts before context window compression

## Pitfalls

1. **FTS5 syntax**: Use `AND` between terms, `"quoted"` for exact phrases, `*` for prefix
2. **Semantic search returns 0 results**: Check `GOOGLE_API_KEY` is set and `sqlite-vec` is installed
3. **Condense merges categories**: Each category gets one condensed entry with merged summaries
4. **sqlite-vec not found**: `pip install sqlite-vec` — it's not in default Hermes deps

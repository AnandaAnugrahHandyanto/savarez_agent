# Enhanced Memory Plugin

**Two-tier fact store with condensation, FTS5 full-text search, and pluggable semantic vector search.**

> Version 1.0.0 · Hermes Agent Memory Provider Plugin

---

## Overview

The Enhanced Memory plugin replaces the default flat memory system with a
structured, two-tier architecture. Every fact captured during a session is
stored as a **raw fact** with category metadata. A **condenser** periodically
groups, deduplicates, and summarises those raw facts into compact **condensed
entries** ranked by priority. The condensed layer is what gets injected into
the system prompt — keeping context windows small while retaining the most
important information.

Optionally, all facts are embedded via a **configurable embedding provider**
and stored as vectors in **sqlite-vec**, enabling true semantic similarity
search across the entire memory corpus.

---

## Architecture

```
 Session N               Session N+1             System Prompt
 ─────────               ───────────             ─────────────
 ┌──────────┐            ┌──────────┐
 │  User    │            │  User    │
 │  message │            │  message │
 └────┬─────┘            └────┬─────┘
      │                       │
      ▼                       ▼
 ┌──────────────────────────────────────────────┐
 │              enhanced_memory tool            │
 │  actions: add / search / semantic_search /   │
 │           condense / list_condensed / stats  │
 └──────────┬──────────────────────┬────────────┘
            │                      │
            ▼                      ▼
 ┌─────────────────┐    ┌─────────────────────┐
 │   raw_facts     │    │   condensed         │
 │   (SQLite+FTS5) │───▶│   (SQLite+FTS5)     │
 │                 │    │                     │
 │  id, content    │    │  topic, category    │
 │  category       │    │  summary, priority  │
 │  source         │    │  source_ids [JSON]  │
 │  condensed flag │    │  version            │
 └─────────────────┘    └─────────┬───────────┘
                                  │
                        ┌─────────▼───────────┐
                        │  get_top_for_memory  │
                        │  (char_limit=2200)   │
                        └─────────┬───────────┘
                                  │  §-separated
                                  ▼
                        ┌─────────────────────┐
                        │  System Prompt       │
                        │  Memory Section      │
                        └─────────────────────┘

 Optional semantic layer:
 ┌────────────────────────────────────────────┐
 │  embedding_providers.py                    │
 │  ┌──────────┐ ┌──────────┐ ┌────────────┐ │
 │  │ Gemini   │ │ OpenAI   │ │  Local     │ │
 │  │ API      │ │ API      │ │  (ST/e5)   │ │
 │  └────┬─────┘ └────┬─────┘ └─────┬──────┘ │
 │       └─────┬──────┘             │         │
 │             ▼                    ▼         │
 │        sqlite-vec (KNN search)             │
 └────────────────────────────────────────────┘
```

---

## Tool: `enhanced_memory`

The plugin exposes a single tool with multiple actions:

### `add`
Store a new raw fact.

| Parameter  | Type   | Required | Description                          |
|------------|--------|----------|--------------------------------------|
| `content`  | string | ✅       | The fact text to store               |
| `category` | string | —        | One of: `user_pref`, `project`, `tool`, `env`, `decision`, `security`, `general` |
| `source`   | string | —        | Origin: `dialog`, `manual`, `auto_extract` |

### `search`
Full-text search across both tiers using SQLite FTS5.

| Parameter | Type   | Required | Description          |
|-----------|--------|----------|----------------------|
| `query`   | string | ✅       | FTS5 search query    |
| `limit`   | int    | —        | Max results (default: 10) |

### `semantic_search`
Vector similarity search using configurable embedding providers + sqlite-vec.

| Parameter | Type   | Required | Description               |
|-----------|--------|----------|---------------------------|
| `query`   | string | ✅       | Natural-language query     |
| `limit`   | int    | —        | Max results (default: 5)   |

### `condense`
Run the condensation pipeline: group → deduplicate → prioritise → upsert.

| Parameter  | Type | Required | Description                     |
|------------|------|----------|---------------------------------|
| `dry_run`  | bool | —        | Preview only, don't write (default: false) |

### `list_condensed`
Return all condensed entries sorted by priority.

### `stats`
Return counts and metadata: total raw facts, uncondensed count, condensed entries, category breakdown, embedding provider status.

---

## Embedding Providers

The plugin supports **three embedding backends** — configurable per-user:

| Provider | Key | Model | Dims | Requirements |
|----------|-----|-------|------|-------------|
| **Gemini** (default) | `gemini` | `gemini-embedding-001` | 3072 | `GOOGLE_API_KEY` |
| **OpenAI** | `openai` | `text-embedding-3-small` | 1536 | `OPENAI_API_KEY` |
| **OpenAI Large** | `openai-large` | `text-embedding-3-large` | 3072 | `OPENAI_API_KEY` |
| **Local** | `local` | `all-MiniLM-L6-v2` | 384 | `pip install sentence-transformers` |
| **Local Multilingual** | `local-multilingual` | `intfloat/multilingual-e5-large` | 1024 | `pip install sentence-transformers` |
| **Disabled** | `none` | — | — | — |

All providers share the same interface (`EmbeddingProvider` ABC). Custom models can be specified via `embedding_model`.

OpenAI provider supports custom `embedding_base_url` for OpenAI-compatible APIs (Azure, local servers, etc.).

---

## Hooks

| Hook               | Trigger                              | Behaviour                                      |
|--------------------|--------------------------------------|-------------------------------------------------|
| `on_session_end`   | Session closes                       | Auto-extract facts + condense if needed         |
| `on_memory_write`  | Built-in memory tool writes          | Mirrors writes as raw facts                     |
| `on_pre_compress`  | Before context-window compression    | Extracts facts before messages are discarded    |

---

## Configuration

Add to your profile's `config.yaml`:

```yaml
memory:
  provider: enhanced-memory

plugins:
  enhanced-memory:
    db_path: $HERMES_HOME/memory_store.db
    auto_extract: true          # Extract facts from conversations
    auto_condense: true         # Auto-condense periodically
    semantic_search: true       # Enable vector search

    # Embedding provider (choose one)
    embedding_provider: gemini  # gemini | openai | openai-large | local | local-multilingual | none
    # embedding_model: gemini-embedding-001    # Override default model
    # embedding_dims: 3072                     # Override dimensions
    # embedding_device: cpu                    # For local: cpu | cuda | mps
    # embedding_base_url: https://...          # For OpenAI-compatible APIs
    # embedding_api_key: ...                   # Explicit key (or use env var)
```

### Environment Variables

| Variable | Provider | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Gemini | Google API key |
| `OPENAI_API_KEY` | OpenAI | OpenAI API key |
| `OPENAI_BASE_URL` | OpenAI | Custom API base URL |

---

## Requirements

### Core (always required)
- Python ≥ 3.10
- SQLite with FTS5 support (included in standard Python builds)

### Semantic Search (optional)
- **`sqlite-vec`** — SQLite extension for vector similarity search
  ```bash
  pip install sqlite-vec
  ```
- **One of the embedding providers:**
  - Gemini: `GOOGLE_API_KEY` environment variable
  - OpenAI: `OPENAI_API_KEY` environment variable
  - Local: `pip install sentence-transformers`

---

## Categories & Priority

| Category    | Base Priority | Topic Label                     |
|-------------|--------------|----------------------------------|
| `security`  | 9 – 10       | Безопасность                     |
| `user_pref` | 8 – 9        | Пользователь: предпочтения      |
| `decision`  | 7 – 9        | Решения и выборы                 |
| `project`   | 7            | Проекты и работа                 |
| `tool`      | 6 – 8        | Инструменты и настройки          |
| `env`       | 5            | Среда и инфраструктура           |
| `general`   | 4            | Общее                            |

**Keyword boosts** (applied on top of base):
- **+1**: `prefers`, `always`, `never`, `предпочитает`, `всегда`, `никогда`
- **+2**: `password`, `key`, `secret`, `пароль`, `ключ`, `секрет`

Priority is capped at 10.

---

## How It Differs from the Holographic Plugin

| Aspect              | Holographic Memory              | Enhanced Memory                    |
|---------------------|---------------------------------|------------------------------------|
| **Storage model**   | Single-tier facts               | Two-tier: raw_facts → condensed    |
| **Search**          | FTS5 keyword                    | FTS5 + semantic vectors            |
| **Embeddings**      | None                            | Gemini / OpenAI / Local            |
| **Deduplication**   | Manual                          | Automatic (80% word overlap)       |
| **Prioritisation**  | Trust scores                    | Category-based scoring (1–10)      |
| **Summarisation**   | None                            | Auto-condensation pipeline         |
| **Prompt injection**| Full entries                    | Priority-ranked, char-limited      |
| **Multilingual**    | English patterns                | EN + RU keyword support            |

---

## File Structure

```
plugins/memory/enhanced_memory/
├── plugin.yaml              # Plugin metadata and hook declarations
├── __init__.py              # MemoryProvider implementation + tool handler
├── store.py                 # EnhancedMemoryStore — SQLite/FTS5 backend
├── condenser.py             # FactCondenser — grouping, dedup, prioritisation
├── embedding_providers.py   # EmbeddingProvider ABC + Gemini/OpenAI/Local
├── embeddings.py            # SemanticSearch — provider-agnostic vec search
├── README.md                # This file
└── SKILL.md                 # Agent-facing skill documentation
```

---

## License

Part of the Hermes Agent ecosystem. See the main project license.

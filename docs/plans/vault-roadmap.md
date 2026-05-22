# Vault Tools — Implementation Roadmap

## Overview

The **vault** toolset provides Hermes with native access to a local
"development ideas" vault: a directory of Markdown files, JSONL entries, and
reference sources stored under `HERMES_HOME/data/development_ideas/`.

This document tracks what is implemented, what is pending, and the intended
design direction.

---

## Phase 1 — Extractive Search (Implemented ✅)

### Files
| File | Purpose |
|------|---------|
| `tools/vault_tool.py` | Core search + ask logic, JSON schemas, registry calls |
| `tests/tools/test_vault_tool.py` | pytest test suite |

### Tools registered
| Tool | Toolset | Description |
|------|---------|-------------|
| `vault_search` | `vault` | Case-insensitive substring search over README.md, ideas.jsonl, sources/*.md |
| `ask_vault` | `vault` | Extractive Q&A — returns top snippets + answer_summary, no LLM call |

### Vault layout expected
```
HERMES_HOME/
  data/
    development_ideas/
      README.md         ← top-level index / overview
      ideas.jsonl       ← one JSON object per line (title, body, tags, …)
      sources/
        *.md            ← reference material (optional)
```

### Scoring algorithm
- Split query into whitespace-delimited terms
- Per-line (Markdown) or per-entry (JSONL): score = `5 * exact_query_hits + sum(term_freq)`
- Sort descending; truncate to `limit`

### Safety / path handling
- Default root: `get_hermes_home() / "data" / "development_ideas"`
- Absolute `path` override: must exist and be a directory.  **Note:** there is
  no restriction on *which* absolute path the caller may supply — users with
  tool access can point it at any readable directory on the filesystem.  A
  future hardening pass could add an allowlist or require the path to live
  inside `HERMES_HOME`.
- Relative `path` override: resolved under default root, `..` components
  are rejected to prevent path traversal
- `check_fn`: returns `True` only when default vault root exists
- **File size guard (future):** very large Markdown or JSONL files are read
  entirely into memory.  A per-file size limit (e.g. 10 MB) should be added
  before the vault is exposed to arbitrary user-supplied paths.

### Toolset registration in `toolsets.py`
- `vault_search` and `ask_vault` added to `_HERMES_CORE_TOOLS`
- `"vault"` entry added to `TOOLSETS` dict

---

## Phase 2 — Structured Indexing (Planned)

- Build an on-disk index (e.g. SQLite FTS5) for faster large-vault search
- Incremental re-index on file change (inotify / polling)
- Tag-based filtering (`tags: [python, ml]` in JSONL entries)
- Date-range filtering on `created_at` / `updated_at` fields

---

## Phase 3 — Semantic Search (Planned)

- Embed vault entries with a local embedding model (e.g. `nomic-embed-text`
  via Ollama) or a lightweight SentenceTransformers model
- Store vectors alongside the SQLite index
- `vault_search` gains `mode` parameter: `"keyword"` (default) | `"semantic"` | `"hybrid"`
- `ask_vault` can optionally call the configured LLM for a synthesised answer
  when `use_llm=True` is passed (gated on model availability)

---

## Phase 4 — Vault Management (Planned)

- `vault_add_idea` — append a new entry to `ideas.jsonl`
- `vault_edit_idea` — update an existing entry by ID or fuzzy title match
- `vault_delete_idea` — soft-delete (move to `ideas.jsonl.archive`)
- `vault_stats` — count entries, list tags, show recent additions

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| No LLM in Phase 1 | Fast, offline, no token cost; sufficient for most lookups |
| JSONL over SQLite | Human-editable, diff-friendly, zero schema migration |
| `check_fn` gates on dir existence | Avoids polluting tool schemas for users without a vault |
| Path traversal guard for relative paths | Principle of least surprise; absolute override is explicit user intent |
| `ask_vault` mode="extractive" | Honest about capabilities; avoids hallucinated "answers" |

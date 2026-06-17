# Context Pager — Lossless Context Compression Engine

A Hermes **ContextEngine** plugin that operates in two stages to maximise context window budget while minimising information loss.

## Architecture

```
compress(messages)
  │
  ├─ Stage 1: Hash dedup + turn merge
  │   • SHA-256 hash of every tool output
  │   • SQLite lookup for identical hashes in same session
  │   • Replaces duplicates with [repeated — same as turn N] stub
  │   • Merges adjacent turns with identical tool signatures
  │   • Lossless — zero information destroyed
  │   • Cost: $0, ~1-7ms
  │
  ├─ Still over threshold and fallback enabled? ──yes──→ Stage 2
  │                                                         │
  │                                              ContextCompressor
  │                                              (LLM summarization)
  │                                              • Summarises middle turns
  │                                              • Preserves head + tail
  │                                              • Lossy — tool outputs gone
  │                                              • Cost: ~$0.002 per fire
  │                                              • Only fires when needed
  │
  └─ No → Return Stage 1 result
```

The two stages are complementary:
- **Stage 1 handles the easy wins** — repeated tool outputs (web search, read_file, terminal) get stubbed away at zero cost.
- **Stage 2 handles the overflow** — unique content that still doesn't fit gets summarised by the built-in compressor.

## Configuration

```yaml
context:
  engine: context_pager
  context_pager:
    protect_first_n: 3          # Turns always kept verbatim (head)
    protect_last_n: 6           # Turns always kept verbatim (tail)
    threshold_percent: 0.75     # % of context length that triggers compression
    fallback_compressor: false  # Enable Stage 2 LLM summarization
    openviking:
      enabled: true             # Archive originals to OpenViking on compression
    sqlite_path: ""             # Default: ~/.hermes/data/context_pager.db
```

## How It Works

### Stage 1 — Semantic Dedup

Every tool output is SHA-256 hashed. Hashes are stored in a local SQLite DB (`tool_outputs` table, keyed by `(session_id, turn_index, msg_index)`).

When `compress()` is called:
1. Messages are annotated with turn indices (system = -1, user = 0, etc.)
2. Protected head and tail are computed (in turns, not messages)
3. Middle-window tool outputs are checked against the DB for more-recent duplicates
4. Duplicates → `[repeated output — same as turn N]` stub
5. Adjacent turns with identical tool signatures → merged
6. Role alternation validated (no two same-role messages in a row)
7. New hashes stored, originals optionally archived to OpenViking

### Stage 2 — Fallback Compressor

If `fallback_compressor: true` and the deduped result is still over the token threshold, Hermes' built-in `ContextCompressor` fires on the already-deduped messages. This means:
- The LLM summarizer sees smaller input (dupes already stripped)
- Summary quality is higher (less noise from repeats)
- Cost is lower per fire (~600 tok in vs ~3,100 without pre-dedup)

## When to Use Fallback Compressor

| Pattern | Stage 1 | Stage 2 | Recommendation |
|---|---|---|---|
| Heavy repeats (same research twice) | 80%+ savings | Rarely needed | Keep default `false` |
| Mixed (some repeats, some unique long content) | 20-60% savings | Fires on overflow | Enable `true` |
| All unique (every turn novel) | 0% savings | Always fires | Use default compressor instead |

## File Layout

```
plugins/context_engine/context_pager/
├── __init__.py    # Plugin registration
├── engine.py      # ContextPagerEngine (two-stage compress)
├── dedup.py       # Hash dedup, turn merging, role validation
├── store.py       # SQLite store + OpenViking archiver
├── plugin.yaml    # Config schema
└── tests/
    ├── test_context_pager.py        # 62 unit tests (E1-X3)
    ├── benchmark_comparison.py      # Side-by-side benchmark
    └── benchmark_large_projects.py  # Large research project benchmark
```

## Running Tests

```bash
pytest plugins/context_engine/context_pager/tests/ -v
```

## Storage

- **SQLite** (`~/.hermes/data/context_pager.db`): Primary hash store. WAL mode. Thread-safe.
- **OpenViking** (optional, `http://127.0.0.1:1933`): Best-effort archival of original (pre-compression) tool outputs for future retrieval.

## Benchmarks (10 identical research projects, 468KB)

| Metric | Stage 1 only | Stage 1 + 2 |
|---|---|---|
| Tokens saved | 97,968 (82%) | + more after summarization |
| LLM calls | 0 | 1 (if triggered) |
| Time | 6.7ms | ~9-11s |
| Lossless? | ✅ Yes | ❌ No |
| Message count | 241→241 (stubs) | 241→~8 |

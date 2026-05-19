# Hermes Brain Memory Provider

`brain` is a local-first MemoryProvider for source-isolated durable memory.

## Enable

```bash
hermes config set memory.provider brain
# Restart the CLI/gateway or start a new session after changing providers.
```

Optional custom database path:

```yaml
plugins:
  brain:
    db_path: $HERMES_HOME/brain/brain.db
```

Default path: `$HERMES_HOME/brain/brain.db`.

## Sources

Default sources are seeded automatically:

- `personal` — Christian-specific private preferences and Friday operating memory.
- `altcoinist` — Altcoinist company/product/team/support/metrics/strategy knowledge.
- `marktr` — Marktr company knowledge. Kept separate from Altcoinist.
- `hermes` — Hermes Agent implementation and architecture knowledge.
- `openclaw` — OpenClaw legacy/migration knowledge.

Source is a hard boundary. Do not write Altcoinist facts into Marktr or personal facts into company sources.

## Tool examples

```json
{"action":"sources"}
```

```json
{"action":"write","source":"altcoinist","content":"Altcoinist company brain imports must preserve file provenance.","kind":"company_fact","confidence":0.9}
```

```json
{"action":"recall","source":"altcoinist","query":"company brain imports provenance","mode":"balanced","limit":5}
```

Document chunk write with provenance:

```json
{"action":"write_document","source":"altcoinist","path":"context/PRODUCT.md","section":"What Altcoinist Builds","line_start":1,"line_end":20,"repo":"altcoinist-company-brain","repo_commit":"28328b8","content":"Altcoinist product context...","kind":"product_context","confidence":0.9}
```

Document chunk recall:

```json
{"action":"recall_documents","source":"altcoinist","query":"creator analytics product surface","mode":"balanced","limit":5}
```

```json
{"action":"maintain"}
```

## Documents and chunks

The provider stores both compact facts and richer document chunks:

- `documents`: source, path, title, kind, repo, repo commit, content hash, metadata, active/superseded state.
- `document_chunks`: source, path, section, line range, content, kind, confidence, provenance, active/superseded state.
- `chunks_fts`: SQLite FTS5 index for source-filtered document recall.

Exact chunk duplicates are keyed by source + repo commit + path + section + line range + normalized content. A new active chunk for the same source/path/section/line range supersedes older active chunks, keeping default recall current while preserving inactive history for audit queries.

## MVP limits

- SQLite FTS5 lexical recall only; vector retrieval and graph traversal come later.
- No raw chat auto-ingestion. Curated `memory` writes are mirrored, and compaction hooks produce preservation candidates.
- Maintenance reports stats; dream-cycle dedupe/contradiction detection is the next increment.

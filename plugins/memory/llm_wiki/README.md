# LLM Wiki Memory Provider

`llm_wiki` is a local-first, source-backed durable memory provider for Hermes Agent.

It stores long-term knowledge as Markdown wiki pages, indexes chunks with Qdrant, and exposes read-first tools to Hermes. It is intended for agent-owned, source-backed, inspectable knowledge rather than automatic transcript summarization, human-review proposal queues, or hidden hosted memory.

## What this provider is for

Use LLM Wiki when memory should be:

- inspectable as normal files
- reviewable with Git diffs
- source-backed and citeable
- editable by humans
- backed up as a folder
- kept local by default

Use Honcho/Mem0/Supermemory-style providers when you want automatic user modeling or hosted semantic memory. Use Hermes built-in `MEMORY.md`/`USER.md` for tiny boot-critical facts.

## Safety defaults

- `sync_turn()` is a no-op. Normal conversation turns are not automatically written.
- `system_prompt_block()` is tiny and does not dump wiki content into the prompt.
- `prefetch()` is bounded and cited.
- `wiki_query` defaults to `file_result=false` and `log_query=false`.
- `wiki_lint` defaults to `write_log=false`.
- `wiki_ingest` defaults to `dry_run=true`, but all file ingest is limited to the primary agent context because dry-runs still read local files for analysis.
- Search/status auto-sync the vector index in trusted writable contexts; no manual `wiki_reindex` tool is exposed.
- `wiki_search.limit` is clamped.
- `wiki_read` validates paths stay under the configured wiki root and caps oversized output.
- Engine-generated slugs and ingest source categories are validated before path construction.
- Automatic index sync upserts replacement vectors before deleting stale chunks, avoiding destructive rebuild-first behavior.

## Config

```yaml
memory:
  provider: llm_wiki

wiki:
  path: ~/.hermes/wiki/personal
  name: personal
  embedding:
    url: http://localhost:8000
    model: text-embedding-3-small
    dim: 1536
  vector_store:
    url: http://localhost:6333
    collection_prefix: hermes_wiki
  llm:
    url: https://openrouter.ai/api/v1
    model: openai/gpt-5.5
```

## Dependencies

The provider package is bundled with Hermes. Heavy search dependencies are optional:

```bash
pip install 'hermes-agent[llm-wiki]'
```

Provider discovery does not require `qdrant-client`; the engine lazily ensures the `memory.llm_wiki` dependency when a real wiki operation needs it.

Runtime services:

- Qdrant HTTP endpoint, default `http://localhost:6333`
- OpenAI-compatible embedding endpoint, default `http://localhost:8000`
- OpenAI-compatible chat endpoint for `wiki_query`, default `https://openrouter.ai/api/v1`

## Retrieval evals

Use the read-only retrieval eval runner to catch regressions in page recall:

```bash
hermes-wiki-eval ~/.hermes/wiki/personal/evals/retrieval.yaml --config ~/.hermes/config.yaml --pretty
# or: python -m hermes_wiki.eval ...
```

`--config` is authoritative when supplied: the file must exist and contain the intended `wiki:` settings; the runner will not silently fall back to another profile/config.

Case file shape:

```yaml
cases:
  - query: How autonomous should Hermes be?
    expected_pages:
      - concepts/user-autonomy-operating-policy.md
      - entities/hermes.md
    top_k: 5
```

The eval runner validates page-path presence only. It does not generate text, write wiki files, ingest sources, or reindex vectors. It still embeds eval query text and reads from the configured vector store, so use local/private endpoints for sensitive eval cases.

## Canonical updates

Trusted primary Hermes contexts can maintain existing canonical pages directly with `wiki_update` when the change is source-backed and auditable. Read-only contexts such as MCP, cron, batch jobs, and subagents can search/query/introspect/lint but do not create proposal queues or mutate canonical pages.

## Maintenance reports

Use `hermes-wiki-maintenance` for a read-only health report over local wiki markdown:

```bash
hermes-wiki-maintenance --config ~/.hermes/config.yaml
hermes-wiki-maintenance --config ~/.hermes/config.yaml --json
```

It checks broken wikilinks, orphan pages, and pages without source coverage. By default it only prints a report. `--write-report reports/maintenance.md` requires explicit `--config` and writes only under the dedicated `reports/` namespace; it does not ingest sources, reindex vectors, or mutate canonical entity/concept pages.

## Privacy note

Indexing sends wiki/source text to the configured embedding endpoint. `wiki_query` sends retrieved snippets plus the question to the configured chat endpoint. For sensitive memory, use local OpenAI-compatible endpoints and do not put secrets in wiki pages.

See `website/docs/user-guide/features/llm-wiki-memory.md` for user-facing docs.

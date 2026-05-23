---
sidebar_position: 5
title: "LLM Wiki Memory"
description: "Local-first, source-backed durable memory for Hermes Agent"
---

# LLM Wiki Memory

LLM Wiki is a local-first memory provider that stores durable knowledge as an inspectable Markdown wiki and indexes it for semantic retrieval. The core package is agent-agnostic: Hermes uses it as a native memory provider, and other agents can use the same substrate through the `llm-wiki-mcp` server or a thin adapter.

It is intentionally **not** an automatic transcript summarizer. Normal conversation turns are not written into the wiki. Hermes can search and read the wiki during chat, but durable writes require explicit tool calls and are blocked in unsafe contexts. Use it when you want source-backed memory that stays under your control instead of a hidden hosted memory database.

## When to use it

Use LLM Wiki for:

- project architecture and operating manuals
- durable policy and conventions
- research notes and source-backed conclusions
- memory that should remain inspectable in Git or a folder backup
- local/offline-first deployments

Use other memory paths for other jobs:

- **Built-in `MEMORY.md` / `USER.md`**: tiny boot-critical facts and preferences.
- **Session search**: chronological recall of past conversations.
- **Honcho/Mem0/Supermemory/etc.**: automatic user modeling or hosted semantic memory.

## Install

LLM Wiki's provider package is bundled with Hermes. Heavy vector-store dependencies are optional and lazy-loaded so normal Hermes installs stay small. The `llm-wiki` extra installs Qdrant plus Hermes's shared vector infrastructure dependency, `vector-core`, from a commit-pinned public GitHub ref until `vector-core` is published on PyPI.

For an explicit install, use the optional dependency group:

```bash
pip install 'hermes-agent[llm-wiki]'
```

For MCP access from Claude Code, OpenClaw, or another MCP-capable host, also install Hermes' existing MCP extra:

```bash
pip install 'hermes-agent[llm-wiki,mcp]'
llm-wiki-mcp --config ~/.hermes/config.yaml
```

If you only configure the provider, Hermes can still discover it without `qdrant-client` or `vector-core` installed. The first real engine/tool use will ask the lazy-dependency system to install the pinned optional dependencies, unless lazy installs are disabled in your security config.

LLM Wiki also expects:

- a Qdrant HTTP endpoint, default `http://localhost:6333`
- an OpenAI-compatible embedding endpoint, default `http://localhost:8000`
- an OpenAI-compatible chat endpoint for `wiki_query`, default `https://openrouter.ai/api/v1`

For a local Qdrant server:

```bash
docker run -p 6333:6333 -v "$PWD/qdrant_storage:/qdrant/storage" qdrant/qdrant
```

## Configure

Run the memory setup wizard and select `llm_wiki`:

```bash
hermes memory setup
```

Manual `~/.hermes/config.yaml` example:

```yaml
memory:
  provider: llm_wiki

wiki:
  path: ~/.hermes/wiki/personal
  name: personal
  embedding:
    url: http://localhost:8000
    model: ExactModelName
    dim: 1536
    # Optional; defaults to <wiki path>/.cache/embeddings.sqlite3
    cache_path: ~/.hermes/wiki/personal/.cache/embeddings.sqlite3
    cache_max_entries: 100000
  vector_store:
    url: http://localhost:6333
    collection_prefix: hermes_wiki
  llm:
    url: https://openrouter.ai/api/v1
    model: openai/gpt-5.5
```

Do not put secrets in wiki pages. If an endpoint needs an API key, keep it in `.env` or your provider-specific config; do not commit it with the wiki.

:::tip Local privacy profile
For sensitive personal or company memory, point both embedding and chat URLs at local OpenAI-compatible services. Search indexing sends wiki/source text to the embedding endpoint, and `wiki_query` sends retrieved snippets plus your question to the configured chat endpoint. Local endpoints keep that loop on your machine.
:::

## Wiki layout

A wiki is a folder with Markdown files:

```text
~/.hermes/wiki/personal/
├── SCHEMA.md
├── index.md
├── log.md
├── entities/
├── concepts/
├── comparisons/
├── queries/
└── raw/
    ├── articles/
    ├── papers/
    └── transcripts/
```

Raw sources live under `raw/`. Generated or curated pages cite those sources with provenance markers such as:

```markdown
This fact came from a source. ^[raw/articles/example.md]
```

## Tools

When enabled, the provider exposes these tools:

| Tool | Purpose | Mutates durable memory? |
| --- | --- | --- |
| `wiki_status` | Show wiki path, page counts, collection stats, recent activity | No |
| `wiki_orient` | Read orientation/index information | No |
| `wiki_search` | Semantic search over indexed wiki chunks | No |
| `wiki_read` | Read a wiki page by slug or relative path | No |
| `wiki_query` | Ask an LLM-backed question against wiki context | No by default |
| `wiki_lint` | Validate links, provenance, source hashes, vector health | No by default |
| `wiki_ingest` | Ingest a curated source file | Dry-run by default; primary context only |

Safe defaults:

- `wiki_query`: `file_result=false`, `log_query=false`
- `wiki_lint`: `write_log=false`
- `wiki_ingest`: `dry_run=true`; blocked outside the primary agent context because even dry-runs read local files and submit their content for analysis
- `wiki_search.limit` is clamped to a small bounded range
- `wiki_read` rejects path traversal and truncates oversized pages
- `sync_turn()` is a no-op; chat turns are not automatically canonized
- prefetch is bounded, cited, and retrieval-only
- writes are blocked outside the primary agent context
- host integrations map their execution context to a generic `WikiCapabilities` policy; unknown/MCP/subagent/cron contexts default to read/query/introspection only, not durable writes

## Package boundary during split-out

The LLM Wiki core package lives in the standalone `hermes-llm-wiki` repository.
Hermes Agent no longer carries a duplicate top-level `hermes_wiki/` mirror;
it keeps only the native provider adapter under `plugins/memory/llm_wiki/`.
Install the `llm-wiki` extra or let the `memory.llm_wiki` lazy dependency install
the standalone package when the provider is first used.

For local development against a checkout of the standalone package, install it
into the active Hermes environment before running LLM Wiki tests:

```bash
uv pip install -e /path/to/hermes-llm-wiki
pytest -o addopts='' tests/plugins/memory/test_llm_wiki_provider.py -q
```

## MCP and generic CLI aliases

Hermes keeps the native memory provider for prompt prefetch and execution-context gating, but the same LLM Wiki core can be exposed to other agents with MCP:

```bash
llm-wiki-mcp --config ~/.hermes/config.yaml          # safe read-first MCP context
llm-wiki-mcp --config ~/.hermes/config.yaml --context primary  # trusted local interactive only
```

Use the default MCP context for Claude Code, OpenClaw workers, subagents, cron jobs, and background automations. `--context primary` enables canonical ingest/update-style capabilities and should only be used in a local, user-controlled, interactive session. Index freshness is automatic in trusted writable contexts rather than a separate reindex tool.

The MCP surface is capability-filtered. Default `mcp` context advertises only tools the external agent may actually use:

| Context | Exposed tool classes |
| --- | --- |
| `mcp`, unknown, Claude Code, OpenClaw, subagent, cron, batch | `wiki_capabilities`, status/orientation, read/search/query/introspection/lint |
| `primary`, `trusted`, `owner`, `interactive` | all read/query tools plus `wiki_ingest` and trusted `wiki_update` where available |
| `disabled`, `none`, `off` | `wiki_capabilities` only |

External agents should call `wiki_capabilities` first. It returns the generic `WikiCapabilities` booleans plus `exposed_tools`, so hosts do not need Hermes-specific assumptions. Denied mutating tools are not advertised in default MCP schemas, and direct calls still enforce the same capability checks.

Generic `llm-wiki-*` CLI aliases are available alongside the older `hermes-wiki-*` names while the core package is being split out. Examples:

```bash
llm-wiki-maintenance --config ~/.hermes/config.yaml
llm-wiki-source-integrity --config ~/.hermes/config.yaml --json
llm-wiki-caretaker --config ~/.hermes/config.yaml --quiet
```

## Operational workflow

1. Put a source document somewhere on disk.
2. Ask Hermes to dry-run ingestion first:

   ```text
   Use wiki_ingest on /path/to/source.md with dry_run=true.
   ```

3. Review the dry-run ingest plan.
4. If it is safe and intentional, run the actual ingest from a primary Hermes session:

   ```text
   Ingest /path/to/source.md into LLM Wiki with dry_run=false.
   ```

5. Run lint when needed; search/status keep the vector index fresh automatically in trusted writable contexts.

   ```text
   Run wiki_lint with write_log=false.
   ```

6. Keep a small retrieval eval file for important recall expectations and run it after changes:

   ```yaml
   # ~/.hermes/wiki/personal/evals/retrieval.yaml
   cases:
     - query: How autonomous should Hermes be?
       expected_pages:
         - concepts/user-autonomy-operating-policy.md
         - entities/hermes.md
       top_k: 5
   ```

   ```bash
   hermes-wiki-eval ~/.hermes/wiki/personal/evals/retrieval.yaml --config ~/.hermes/config.yaml --pretty
   # or: python -m hermes_wiki.eval ...
   ```

   `--config` is authoritative when supplied: the file must exist and contain the intended `wiki:` settings; the runner will not silently fall back to another profile/config.

   Retrieval evals are read-only. They validate that expected page paths appear in search results; they do not generate answers, write wiki pages, ingest sources, or reindex vectors. They still embed eval query text and read from the configured vector store, so use local/private endpoints for sensitive eval cases.

7. Inspect retrieval hits for one query when evals fail or recall looks suspicious:

   ```bash
   hermes-wiki-introspect "How autonomous should Hermes be?" \
     --config ~/.hermes/config.yaml \
     --expected-page concepts/user-autonomy-operating-policy.md
   hermes-wiki-introspect "What should Hermes call the user?" --config ~/.hermes/config.yaml --json
   hermes-wiki-introspect "ExactModelName" --config ~/.hermes/config.yaml --search-mode hybrid --json
   ```

   Retrieval introspection is read-only. It reports the original query, search mode, top-k, ranked chunk hits, scores, page/source paths, deduplicated page coverage, and missing expected pages. `--search-mode` can be `dense` (default/backward compatible), `sparse` (lexical payload matching for literal names, commands, config keys, and paths), or `hybrid` (dense+sparse Reciprocal Rank Fusion). It does not generate answers, write wiki pages, ingest sources, reindex vectors, or log queries. Like evals, dense/hybrid modes may embed the inspected query and read from the configured vector store; sparse mode scans indexed payload text.

8. Generate a read-only maintenance report:

   ```bash
   hermes-wiki-maintenance --config ~/.hermes/config.yaml
   hermes-wiki-maintenance --config ~/.hermes/config.yaml --json
   ```

   This checks broken wikilinks, orphan pages, and pages without source coverage. By default it only prints a report. `--write-report reports/maintenance.md` requires explicit `--config` and writes only under the dedicated `reports/` namespace; it does not ingest sources, reindex vectors, or mutate canonical entity/concept pages.

9. Audit or explicitly repair raw-source hash frontmatter:

   ```bash
   llm-wiki-source-integrity --config ~/.hermes/config.yaml --json
   llm-wiki-source-integrity --config ~/.hermes/config.yaml --repair --json
   ```

   Source integrity audit is read-only by default. `--repair` requires explicit `--config` and only updates `sha256` frontmatter on existing `raw/**/*.md` source files to match the parsed Markdown body. It does not edit canonical pages, ingest sources, reindex vectors, or write logs.

10. Run the agent-native caretaker loop for cron/watchdog-style memory health:

   ```bash
   hermes-wiki-caretaker --config ~/.hermes/config.yaml
   hermes-wiki-caretaker --config ~/.hermes/config.yaml --quiet
   hermes-wiki-caretaker --config ~/.hermes/config.yaml --json
   ```

   The caretaker combines maintenance checks with retrieval evals from `<wiki>/evals/retrieval.yaml` when present, then classifies next actions for Hermes (`repair_broken_link`, `fix_retrieval_regression`, etc.). It is read-first and agent-native: no ingest, no reindex, no canonical page mutation, no query logging, no proposal queue, and no chat-model calls. `--quiet` prints nothing when there are no blockers, making it suitable for watchdog scripts that only alert on retrieval regressions or hard maintenance errors. `--write-report reports/caretaker.md` requires explicit `--config` and writes only under `reports/`.

## Safety model

LLM Wiki treats durable memory as the agent-owned, source-backed canonical memory substrate, not a scratchpad or human-review proposal queue.

- No automatic writes from normal conversation flow.
- No whole-wiki prompt dumps.
- No path traversal in `wiki_read`.
- Durable write tools are blocked in cron/subagent/batch/compression/retrieval contexts.
- Ingest source categories are allowlisted before they become paths.
- Automatic index sync upserts replacement vectors before deleting stale chunks, so embedding failures do not wipe existing search results.
- Dense embedding calls use vector-core's persistent SQLite embedding cache and OpenAI-compatible embedding client. Hermes namespaces cache keys by model, embedding dimension, and text content hash; cache values are JSON-serialized and LRU-evicted by `wiki.embedding.cache_max_entries`.
- Raw sources are hash-checked by lint so accidental drift is visible.
- Markdown pages are human-readable and can be reviewed with normal Git tools.

## Troubleshooting

**Provider not available**

Install the extra and restart Hermes:

```bash
pip install 'hermes-agent[llm-wiki]'
```

**Search fails**

Check Qdrant and embedding endpoint health. The embedding URL should be OpenAI-compatible; Hermes normalizes a URL like `http://localhost:8000` to `https://openrouter.ai/api/v1` internally.

**Lint reports empty vector index**

Confirm Qdrant and the embedding endpoint are available, then run a trusted primary-context search/status operation. LLM Wiki auto-syncs the vector index in writable trusted contexts; there is no manual `wiki_reindex` tool to remember.

**Writes are blocked**

This is expected in cron, subagents, batch jobs, and retrieval-only contexts. Re-run the operation from a primary interactive agent session, or keep `dry_run=true` for inspection.

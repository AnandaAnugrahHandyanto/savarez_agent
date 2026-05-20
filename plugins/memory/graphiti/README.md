# Hermes Graphiti Memory Provider

Local-first temporal graph memory provider for Hermes.

## Defaults

- Graph store: local Kuzu database at `$HERMES_HOME/graphiti/graph.kuzu`
- Embeddings: Ollama `qwen3-embedding:4b`
- LLM extraction: OpenRouter via `OPENROUTER_API_KEY`
- Default LLM model: `deepseek/deepseek-v4-flash`

## Install dependencies

Bundled install / repo checkout:

```bash
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python 'hermes-agent[graphiti]'
```

Standalone user-plugin install:

```bash
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python -r ~/.hermes/plugins/graphiti/requirements.txt
```

## Configure

`$HERMES_HOME/graphiti.json`:

```json
{
  "backend": "kuzu",
  "kuzu_path": "~/.hermes/graphiti/graph.kuzu",
  "ollama_base_url": "http://127.0.0.1:11434",
  "embedding_model": "qwen3-embedding:4b",
  "embedding_dim": 2560,
  "llm_base_url": "https://openrouter.ai/api/v1",
  "llm_model": "deepseek/deepseek-v4-flash",
  "llm_small_model": "deepseek/deepseek-v4-flash",
  "sync_turns": true,
  "prefetch_top_k": 5,
  "group_id": ""
}
```

Secrets stay in env. Do not put `OPENROUTER_API_KEY` in this JSON.

Enable provider:

```bash
hermes config set memory.provider graphiti
```

Restart Hermes after changing memory provider.

## Tools

- `graphiti_search` — search temporal graph memory.
- `graphiti_remember` — store an explicit durable fact/event without waiting for turn sync.
- `graphiti_status` — report backend/model config without printing secrets.

## Privacy Controls

Graph storage and embeddings are local-first, but Graphiti extraction uses the configured OpenRouter-compatible LLM endpoint by default. This means automatically synced turns are sent to that LLM endpoint for entity/relation extraction.

To disable automatic turn ingestion while keeping explicit memory tools available:

```json
{
  "sync_turns": false
}
```

With `sync_turns=false`, use `graphiti_remember` only when the user explicitly wants durable memory.

## Notes

This provider is bundled under `plugins/memory/graphiti` in this branch and can also be installed as a standalone user plugin under `$HERMES_HOME/plugins/graphiti` for local experimentation.

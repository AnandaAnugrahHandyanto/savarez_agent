# Hermex MVP Guide

Hermex v1 is an external cognitive layer for Hermes Agent. It does not patch the Hermes reasoning loop. The MVP ships two surfaces:

- an Anthropic-compatible LLM proxy at `http://localhost:8747/v1/messages`
- a small HTTP MCP endpoint at `http://localhost:8748/mcp`

The proxy is the main demo. It fingerprints sessions, forwards requests to the configured upstream, records streamed traces, and injects small advisory ambient context from prior sessions. The MCP endpoint exposes two static tools backed by the same SQLite store: `hermex_memory_search` and `hermex_what_failed`.

## Run With OpenRouter

Set the upstream and API key:

```bash
export HERMEX_STORE=sqlite
export HERMEX_SQLITE_PATH=.hermex/hermex.sqlite3
export UPSTREAM_BASE=https://openrouter.ai/api/v1
export OPENROUTER_API_KEY=sk-or-...
```

Start the proxy:

```bash
hermex proxy --port 8747
```

Hermex forwards the request body as-is. It does not rewrite model strings. Configure the OpenRouter model in Hermes itself, for example `anthropic/claude-3.5-sonnet`.

## Wire Hermes To The Proxy

Point Hermes' Anthropic-compatible base URL at Hermex:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8747
```

Keep your normal Hermes provider/model configuration responsible for model names and routing. Hermex only appends bounded `[HERMEX_AMBIENT]` context to the system prompt when it finds relevant cross-session telemetry.

## Optional MCP Tools

Start the MCP server:

```bash
hermex mcp --port 8748
```

Add it to Hermes' MCP configuration:

```json
{
  "mcpServers": {
    "hermex": {
      "url": "http://localhost:8748/mcp",
      "transport": "http"
    }
  }
}
```

The v1 MCP tool list is intentionally static:

- `hermex_memory_search`: search prior Hermex execution memories
- `hermex_what_failed`: return known failure modes for a tool or task

## Storage Boundary

All storage goes through abstract interfaces in `hermex/core/store/base.py`. The MVP uses SQLite in `hermex/core/store/sqlite.py`. Redis, dynamic crystallized MCP tools, context compression, and skill synthesis are phase 2 features and should plug in by implementing the same store interfaces rather than rewriting proxy or MCP code.

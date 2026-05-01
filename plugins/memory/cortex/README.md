# Cortex Memory Provider

Native Hermes Agent memory provider for Cortex.

## Configure

Set Hermes config:

```yaml
memory:
  provider: cortex
```

Set environment variables for the server URL and secrets:

```bash
CORTEX_URL=http://127.0.0.1:21100
CORTEX_AUTH_TOKEN=optional-token
CORTEX_AGENT_ID=hermes
CORTEX_PAIRING_CODE=***
```

Non-secret settings can also live in `$HERMES_HOME/cortex.json`. Keep `CORTEX_AUTH_TOKEN` and `CORTEX_PAIRING_CODE` in the environment, not in JSON config.

## Behavior

- `queue_prefetch()` calls Cortex `POST /api/v1/recall` for automatic pre-turn recall.
- `sync_turn()` calls Cortex `POST /api/v1/ingest` for automatic post-turn memory extraction.
- Explicit tools are exposed as `cortex_recall`, `cortex_remember`, `cortex_forget`, `cortex_search`, `cortex_relations`, and `cortex_stats`.

No MCP server is required for this native provider, though Cortex MCP can still be configured separately.

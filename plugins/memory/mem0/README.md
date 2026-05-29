# Mem0 Memory Provider

Server-side LLM fact extraction with semantic search, reranking, and automatic deduplication.

Every conversation turn is sent to Mem0's platform, which extracts facts, deduplicates them, and stores them in a vector index. On each new turn, the agent retrieves the most relevant memories and injects them into context — giving you a brain that grows with every session.

## Requirements

- `mem0ai >= 2.0` (tested on 2.0.4)
- Mem0 API key from [app.mem0.ai](https://app.mem0.ai)

## Setup

### Automatic (recommended)

```bash
hermes memory setup    # select "mem0"
```

### Manual

```bash
# 1. Install the dependency (uv is preferred; falls back to python -m pip)
uv pip install mem0ai --python $(which python)

# 2. Add your API key
echo 'MEM0_API_KEY=your-key-here' >> ~/.hermes/.env

# 3. Activate the provider
hermes config set memory.provider mem0
```

## Config

Optional config file: `$HERMES_HOME/mem0.json`

| Key | Default | Description |
|-----|---------|-------------|
| `user_id` | `hermes-user` | User identifier on Mem0 (override with `MEM0_USER_ID` env var) |
| `agent_id` | `hermes` | Agent identifier (override with `MEM0_AGENT_ID` env var) |
| `rerank` | `true` | Enable reranking for recall quality |
| `keyword_search` | `false` | Enable keyword search in addition to semantic |

Example `mem0.json`:
```json
{
  "user_id": "simon",
  "agent_id": "betty",
  "rerank": true
}
```

## Tools exposed to the agent

| Tool | Description |
|------|-------------|
| `mem0_profile` | Retrieve all stored memories for the current user |
| `mem0_search` | Semantic search with optional reranking |
| `mem0_conclude` | Store a fact verbatim (bypasses LLM extraction) |

## API Compatibility

This plugin targets **mem0ai 2.0+**. The search API changed between 1.x and 2.0:

- ❌ Old (1.x): `client.search(query, user_id="...")`
- ✅ New (2.0+): `client.search(query, filters={"user_id": "..."})`

The plugin uses `filters=` throughout and is compatible with 2.0+.

## Verify it's working

```bash
# After setup, start a new hermes session and check the system prompt
# You should see a "Mem0 Memory" section if memories exist

# Or test the API directly:
python -c "
import os; from mem0 import MemoryClient
c = MemoryClient(api_key=os.environ['MEM0_API_KEY'])
print(c.search('test', filters={'user_id': 'hermes-user'}, limit=1))
"
```

## Circuit Breaker

The plugin has a built-in circuit breaker: after 5 consecutive API failures it pauses
calls for 120 seconds to avoid hammering a degraded server. Failures are logged at
DEBUG level (`hermes logs --level debug`).

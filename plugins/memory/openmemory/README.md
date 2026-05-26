# OpenMemory Plugin

Self-hosted [Mem0](https://github.com/mem0ai/mem0) memory provider for Hermes Agent.

OpenMemory is the official self-hosted version of Mem0, providing semantic memory with vector search, LLM-powered fact extraction, and persistence via PostgreSQL + Qdrant. Unlike the cloud Mem0 Platform API, OpenMemory runs on your own infrastructure (NAS, VPS, homelab).

## Features

- 🏠 **Self-hosted** — Full control over your data
- 🔍 **Semantic search** — Find memories by meaning, not keywords  
- 🧠 **LLM-powered** — Automatic fact extraction and deduplication
- 💾 **Persistent** — PostgreSQL + Qdrant vector database
- 🌐 **Web UI** — Optional dashboard for memory visualization
- 🔒 **Privacy** — All data stays on your infrastructure

## Quick Start

### 1. Deploy OpenMemory

Use the provided `docker-compose.yml`:

```bash
cd ~/.hermes/hermes-agent/plugins/memory/openmemory/
docker-compose up -d
```

This starts:
- **OpenMemory API** on port `8765`
- **Qdrant** vector DB on port `6333`  
- **Web UI** (optional) on port `3001`

### 2. Configure Hermes

Add to `~/.hermes/.env`:

```bash
OPENMEMORY_API_URL=http://localhost:8765
OPENMEMORY_APP_ID=hermes
OPENMEMORY_USER_ID=hermes-user
```

Or for a NAS deployment:

```bash
OPENMEMORY_API_URL=http://192.168.1.100:8765
```

### 3. Activate

```bash
hermes config set memory.provider openmemory
hermes config set memory.memory_enabled true
```

### 4. Test

```bash
hermes chat -q "My name is Alice and I love Python. Remember this."
hermes chat -q "What do you know about me?"
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENMEMORY_API_URL` | ✅ | - | Base URL of your OpenMemory instance |
| `OPENMEMORY_APP_ID` | ❌ | `hermes` | App identifier for memory scoping |
| `OPENMEMORY_USER_ID` | ❌ | `hermes-user` | User identifier |
| `OPENMEMORY_API_KEY` | ❌ | - | Optional API key for auth |

### Config File

Alternatively, create `~/.hermes/openmemory.json`:

```json
{
  "api_url": "http://nas.local:8765",
  "app_id": "hermes",
  "user_id": "my-user"
}
```

## Tools

OpenMemory provides 3 tools to the agent:

### `openmemory_profile`
Retrieve all stored memories. Fast, no reranking. Used at conversation start.

### `openmemory_search`
Search memories semantically by meaning.

**Parameters:**
- `query` (string, required): What to search for
- `top_k` (integer, optional): Max results (default: 10, max: 50)

### `openmemory_conclude`
Store a new memory verbatim (no LLM extraction).

**Parameters:**
- `conclusion` (string, required): The fact to store

## Docker Deployment

### Minimal (API only)

```yaml
version: '3.8'

services:
  openmemory-api:
    image: mem0/openmemory-mcp:latest
    ports:
      - "8765:8765"
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
    depends_on:
      - qdrant
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

volumes:
  qdrant_data:
```

### With UI Dashboard

See the full `docker-compose.yml` in this directory for a setup including:
- OpenMemory API
- Qdrant vector database
- Web UI dashboard on port 3001

### NAS Deployment (Synology, QNAP, etc.)

For NAS systems, use explicit volume paths:

```yaml
volumes:
  - /volume1/docker/openmemory/qdrant:/qdrant/storage
```

Adjust `/volume1/` to match your NAS volume name.

## Cost Optimization

OpenMemory uses an LLM for memory processing. To minimize costs:

### Use OpenRouter with Free Models

```yaml
environment:
  - OPENAI_API_BASE=https://openrouter.ai/api/v1
  - OPENAI_API_KEY=***  - LLM_MODEL=meta-llama/llama-3.1-8b-instruct:free
```

**Free OpenRouter models:**
- `meta-llama/llama-3.1-8b-instruct:free`
- `google/gemini-flash-1.5:free`
- `mistralai/mistral-7b-instruct:free`

### Use Local Embeddings (Coming Soon)

Future versions will support local embedding models to eliminate API costs entirely.

## Troubleshooting

### Circuit Breaker

The plugin includes a circuit breaker to prevent hammering a down server. After 5 consecutive failures, API calls are paused for 2 minutes.

Check logs:
```bash
tail -f ~/.hermes/logs/agent.log | grep -i openmemory
```

### Connection Failed

```
Connection failed. Is OpenMemory running?
```

**Solutions:**
1. Check containers are running: `docker ps`
2. Test API: `curl http://localhost:8765/docs`
3. Verify `OPENMEMORY_API_URL` in `.env`

### No Memories Visible in UI

The UI uses the `user_id` from the environment. Make sure:
1. `OPENMEMORY_USER_ID` matches in both Docker Compose and Hermes config
2. The UI environment variable `NEXT_PUBLIC_USER_ID` matches

## Comparison with Other Providers

| Feature | OpenMemory | Honcho | Mem0 Cloud | Built-in |
|---------|-----------|--------|------------|----------|
| Self-hosted | ✅ | ✅ | ❌ | ✅ |
| Semantic search | ✅ | ✅ | ✅ | ❌ |
| LLM extraction | ✅ | ❌ | ✅ | ❌ |
| Vector DB | Qdrant | pgvector | Qdrant | - |
| Web UI | ✅ | ❌ | ✅ | ❌ |
| Setup complexity | Medium | Low | None | None |
| Cost | Infrastructure only | Infrastructure only | Per-API-call | Free |

## Architecture

```
Hermes Agent
    ↓ (memory tools)
OpenMemory API (FastAPI)
    ↓
├─ Qdrant (vector search)
└─ LLM API (fact extraction)
```

## Links

- [OpenMemory GitHub](https://github.com/mem0ai/mem0/tree/main/openmemory)
- [Mem0 Documentation](https://docs.mem0.ai/open-source/overview)
- [Hermes Memory Docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)

## Contributing

Found a bug or want to improve this plugin? PRs welcome!

1. Test your changes locally
2. Add tests in `tests/plugins/memory/test_openmemory.py`
3. Update this README if you change config or features
4. Submit PR to [hermes-agent](https://github.com/NousResearch/hermes-agent)

# MemTensor Memory Provider

Persistent semantic memory with hybrid search (vector + full-text + recency), powered by [memos-core](https://github.com/MemTensor/MemOS).

## How It Works

MemTensor runs a local Node.js bridge daemon that provides:
- **Hybrid retrieval** — combines vector similarity, BM25 full-text search, and recency scoring via Reciprocal Rank Fusion (RRF)
- **Automatic ingestion** — conversation turns are persisted after each exchange
- **Memory viewer** — a web UI to browse and search stored memories
- **Local-first** — all data stays on your machine (with optional cloud embedding providers)

## Requirements

| Requirement | Notes |
|------------|-------|
| **Node.js 18+** | Auto-installed by `install.sh` if missing |
| **npm or pnpm** | For installing Node.js dependencies |

No API keys required by default — MemTensor includes a local embedding model. For higher quality embeddings, configure an external provider (OpenAI, Cohere, Voyage, etc.).

## Setup

### Quick Install

```bash
bash plugins/memory/memtensor/install.sh
hermes config set memory.provider memtensor
```

The installer will:
1. Check for Node.js >= 18 (auto-installs Node.js 22 if missing)
2. Clone the memos-local-plugin runtime to `~/.hermes/memtensor-runtime/`
3. Install Node.js dependencies
4. Record the bridge path for runtime discovery

### Manual Install

If you already have the MemOS repository cloned:

```bash
export MEMOS_PLUGIN_ROOT=/path/to/MemOS/apps/memos-local-plugin
cd $MEMOS_PLUGIN_ROOT && npm install
echo "$MEMOS_PLUGIN_ROOT/bridge.cts" > plugins/memory/memtensor/bridge_path.txt
hermes config set memory.provider memtensor
```

### Hermes Memory Setup

```bash
hermes memory setup    # select "memtensor"
```

## Config

Config file: `$HERMES_HOME/memtensor.json`

### Embedding

| Variable | Description | Default |
|----------|-------------|---------|
| `MEMOS_EMBEDDING_PROVIDER` | Embedding provider | `local` |
| `MEMOS_EMBEDDING_API_KEY` | API key for embedding provider | — |
| `MEMOS_EMBEDDING_ENDPOINT` | Custom embedding endpoint | — |

Supported embedding providers: `local`, `openai`, `cohere`, `voyage`, `gemini`, `mistral`.

### Ports

| Variable | Description | Default |
|----------|-------------|---------|
| `MEMOS_DAEMON_PORT` | Bridge daemon TCP port | `18992` |
| `MEMOS_VIEWER_PORT` | Memory viewer HTTP port | `18901` |

### Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `MEMOS_STATE_DIR` | Memory database location | `$HERMES_HOME/memos-state` |
| `MEMOS_PLUGIN_ROOT` | memos-local-plugin location | `~/.hermes/memtensor-runtime` |

## Tools

| Tool | Description |
|------|-------------|
| `memory_search` | Search long-term memory with hybrid retrieval |

## Architecture

```
hermes-agent (Python)
  └─ MemTensorProvider
       └─ bridge_client.py ──TCP──► memos-core-bridge (Node.js daemon)
                                      ├─ SQLite + vector index
                                      ├─ embedding engine
                                      └─ HTTP viewer (port 18901)
```

The bridge daemon starts automatically on first session and persists across sessions. It hosts both the JSON-RPC bridge (for Python↔Node.js communication) and the memory viewer web UI.

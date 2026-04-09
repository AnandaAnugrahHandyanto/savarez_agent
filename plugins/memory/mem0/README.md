# Mem0 Memory Provider

Server-side LLM fact extraction with semantic search, reranking, and automatic deduplication.

## Requirements

- `pip install mem0ai`
- Mem0 API key from [app.mem0.ai](https://app.mem0.ai)

## Setup

```bash
hermes memory setup    # select "mem0"
```

Or manually:
```bash
hermes config set memory.provider mem0
echo "MEM0_API_KEY=your-key" >> ~/.hermes/.env
```

## Config

Config file: `$HERMES_HOME/mem0.json`

| Key | Default | Description |
|-----|---------|-------------|
| `user_id` | `hermes-user` | User identifier on Mem0 |
| `agent_id` | `hermes` | Agent identifier |
| `rerank` | `true` | Enable reranking for recall |
| `top_k` / `topK` | `3` | Max memories returned by automatic pre-turn recall |
| `search_threshold` / `searchThreshold` | `0.5` | Minimum score for automatic recall filtering when scores are present |
| `auto_capture` / `autoCapture` | `false` | Automatically capture each completed turn into Mem0 |
| `auto_recall` / `autoRecall` | `true` | Automatically recall relevant memories before each turn |

Notes:
- `top_k` / `search_threshold` apply to automatic prefetch recall, not manual `mem0_search` calls.
- `search_threshold` only filters results that include a score; results without scores are preserved.
- `auto_capture: false` is useful on the Hobby plan when you want to rely on explicit memory tools instead of per-turn ingestion.

## Tools

| Tool | Description |
|------|-------------|
| `mem0_profile` | All stored memories about the user, including memory IDs for curation |
| `mem0_search` | Semantic search with optional reranking, returning memory IDs |
| `mem0_conclude` | Store a fact verbatim (no LLM extraction) |
| `mem0_update` | Update an existing memory by ID |
| `mem0_delete` | Delete an existing memory by ID |

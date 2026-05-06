# NoldoMem Memory Provider

NoldoMem is a long-term memory backend for agent memory retrieval. This
provider connects Hermes to a running NoldoMem HTTP API through the native
Hermes `MemoryProvider` interface.

NoldoMem handles storage, embeddings, hybrid search, decay, and reranking.
Hermes only sends recall/store/pin requests and degrades gracefully when the
service is unavailable.

## Setup

Configure the provider:

```bash
hermes memory setup
```

Or set values directly:

```bash
hermes config set memory.provider noldomem
export NOLDOMEM_API_URL=http://127.0.0.1:8787
export NOLDOMEM_API_KEY=YOUR_KEY
```

Optional environment variables:

```bash
export NOLDOMEM_AGENT=hermes
export NOLDOMEM_NAMESPACE=default
export NOLDOMEM_API_TIMEOUT=2
export NOLDOMEM_MAX_RECALL_RESULTS=5
export NOLDOMEM_MAX_CONTEXT_CHARS=4000
```

## Tools

The provider exposes:

- `noldomem_recall`
- `noldomem_store`
- `noldomem_pin`

## Safety

- API keys are read from environment variables or Hermes secret storage.
- Recall output is bounded by result count and character budget.
- Completed-turn storage runs in a background thread.
- Cron, subagent, and flush contexts skip automatic writes by default.
- Request failures return empty recall context instead of blocking replies.

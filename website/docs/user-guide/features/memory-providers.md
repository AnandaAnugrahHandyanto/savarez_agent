---
sidebar_position: 4
title: "Memory Providers"
description: "External memory provider plugins — Honcho, OpenViking, Mem0, Hindsight, Holographic, RetainDB, ByteRover, Supermemory"
---

# Memory Providers

Hermes Agent ships with 8 external memory provider plugins that give the agent persistent, cross-session knowledge beyond the built-in MEMORY.md and USER.md. Only **one** external provider can be active at a time — the built-in memory is always active alongside it.

## Quick Start

```bash
hermes memory setup      # interactive picker + configuration
hermes memory status     # check what's active
hermes memory off        # disable external provider
```

You can also select the active memory provider via `hermes plugins` → Provider Plugins → Memory Provider.

Or set manually in `~/.hermes/config.yaml`:

```yaml
memory:
  provider: openviking   # or honcho, mem0, hindsight, holographic, retaindb, byterover, supermemory
```

## How It Works

When a memory provider is active, Hermes automatically:

1. **Injects provider context** into the system prompt (what the provider knows)
2. **Prefetches relevant memories** before each turn (background, non-blocking)
3. **Syncs conversation turns** to the provider after each response
4. **Extracts memories on session end** (for providers that support it)
5. **Mirrors built-in memory writes** to the external provider
6. **Adds provider-specific tools** so the agent can search, store, and manage memories

The built-in memory (MEMORY.md / USER.md) continues to work exactly as before. The external provider is additive.

## Available Providers

### Honcho

AI-native cross-session user modeling with dialectic reasoning, session-scoped context injection, semantic search, and persistent conclusions. Base context now includes the session summary alongside user representation and peer cards, giving the agent awareness of what has already been discussed.

| | |
|---|---|
| **Best for** | Multi-agent systems with cross-session context, user-agent alignment |
| **Requires** | `pip install honcho-ai` + [API key](https://app.honcho.dev) or self-hosted instance |
| **Data storage** | Honcho Cloud or self-hosted |
| **Cost** | Honcho pricing (cloud) / free (self-hosted) |

**Tools (5):** `honcho_profile` (read/update peer card), `honcho_search` (semantic search), `honcho_context` (session context — summary, representation, card, messages), `honcho_reasoning` (LLM-synthesized), `honcho_conclude` (create/delete conclusions)

**Architecture:** Two-layer context injection — a base layer (session summary + representation + peer card, refreshed on `contextCadence`) plus a dialectic supplement (LLM reasoning, refreshed on `dialecticCadence`). The dialectic automatically selects cold-start prompts (general user facts) vs. warm prompts (session-scoped context) based on whether base context exists.

**Three orthogonal config knobs** control cost and depth independently:

- `contextCadence` — how often the base layer refreshes (API call frequency)
- `dialecticCadence` — how often the dialectic LLM fires (LLM call frequency)
- `dialecticDepth` — how many `.chat()` passes per dialectic invocation (1–3, depth of reasoning)

**Setup Wizard:**
```bash
hermes memory setup        # select "honcho" — runs the Honcho-specific post-setup
```

The legacy `hermes honcho setup` command still works (it now redirects to `hermes memory setup`), but is only registered after Honcho is selected as the active memory provider.

**Config:** `$HERMES_HOME/honcho.json` (profile-local) or `~/.honcho/config.json` (global). Resolution order: `$HERMES_HOME/honcho.json` > `~/.hermes/honcho.json` > `~/.honcho/config.json`. See the [config reference](https://github.com/NousResearch/hermes-agent/blob/main/plugins/memory/honcho/README.md) and the [Honcho integration guide](https://docs.honcho.dev/v3/guides/integrations/hermes).

<details>
<summary>Full config reference</summary>

| Key | Default | Description |
|-----|---------|-------------|
| `apiKey` | -- | API key from [app.honcho.dev](https://app.honcho.dev) |
| `baseUrl` | -- | Base URL for self-hosted Honcho |
| `peerName` | -- | User peer identity |
| `aiPeer` | host key | AI peer identity (one per profile) |
| `workspace` | host key | Shared workspace ID |
| `contextTokens` | `null` (uncapped) | Token budget for auto-injected context per turn. Truncates at word boundaries |
| `contextCadence` | `1` | Minimum turns between `context()` API calls (base layer refresh) |
| `dialecticCadence` | `2` | Minimum turns between `peer.chat()` LLM calls. Recommended 1–5. Only applies to `hybrid`/`context` modes |
| `dialecticDepth` | `1` | Number of `.chat()` passes per dialectic invocation. Clamped 1–3. Pass 0: cold/warm prompt, pass 1: self-audit, pass 2: reconciliation |
| `dialecticDepthLevels` | `null` | Optional array of reasoning levels per pass, e.g. `["minimal", "low", "medium"]`. Overrides proportional defaults |
| `dialecticReasoningLevel` | `'low'` | Base reasoning level: `minimal`, `low`, `medium`, `high`, `max` |
| `dialecticDynamic` | `true` | When `true`, model can override reasoning level per-call via tool param |
| `dialecticMaxChars` | `600` | Max chars of dialectic result injected into system prompt |
| `recallMode` | `'hybrid'` | `hybrid` (auto-inject + tools), `context` (inject only), `tools` (tools only) |
| `writeFrequency` | `'async'` | When to flush messages: `async` (background thread), `turn` (sync), `session` (batch on end), or integer N |
| `saveMessages` | `true` | Whether to persist messages to Honcho API |
| `observationMode` | `'directional'` | `directional` (all on) or `unified` (shared pool). Override with `observation` object |
| `messageMaxChars` | `25000` | Max chars per message (chunked if exceeded) |
| `dialecticMaxInputChars` | `10000` | Max chars for dialectic query input to `peer.chat()` |
| `sessionStrategy` | `'per-directory'` | `per-directory`, `per-repo`, `per-session`, `global` |

</details>

<details>
<summary>Minimal honcho.json (cloud)</summary>

```json
{
  "apiKey": "your-key-from-app.honcho.dev",
  "hosts": {
    "hermes": {
      "enabled": true,
      "aiPeer": "hermes",
      "peerName": "your-name",
      "workspace": "hermes"
    }
  }
}
```

</details>

<details>
<summary>Minimal honcho.json (self-hosted)</summary>

```json
{
  "baseUrl": "http://localhost:8000",
  "hosts": {
    "hermes": {
      "enabled": true,
      "aiPeer": "hermes",
      "peerName": "your-name",
      "workspace": "hermes"
    }
  }
}
```

</details>

:::tip Migrating from `hermes honcho`
If you previously used `hermes honcho setup`, your config and all server-side data are intact. Just re-enable through the setup wizard again or manually set `memory.provider: honcho` to reactivate via the new system.
:::

**Multi-peer setup:**

Honcho models conversations as peers exchanging messages — one user peer plus one AI peer per Hermes profile, all sharing a workspace. The workspace is the shared environment: the user peer is global across profiles, each AI peer is its own identity. Every AI peer builds an independent representation / card from its own observations, so a `coder` profile stays code-oriented while a `writer` profile stays editorial against the same user.

The mapping:

| Concept | What it is |
|---------|-----------|
| **Workspace** | Shared environment. All Hermes profiles under one workspace see the same user identity. |
| **User peer** (`peerName`) | The human. Shared across profiles in the workspace. |
| **AI peer** (`aiPeer`) | One per Hermes profile. Host key `hermes` → default; `hermes.<profile>` for others. |
| **Observation** | Per-peer toggles controlling what Honcho models from whose messages. `directional` (default, all four on) or `unified` (single-observer pool). |

### New profile, fresh Honcho peer

```bash
hermes profile create coder --clone
```

`--clone` creates a `hermes.coder` host block in `honcho.json` with `aiPeer: "coder"`, shared `workspace`, inherited `peerName`, `recallMode`, `writeFrequency`, `observation`, etc. The AI peer is eagerly created in Honcho so it exists before the first message.

### Existing profiles, backfill Honcho peers

```bash
hermes honcho sync
```

Scans every Hermes profile, creates host blocks for any profile without one, inherits settings from the default `hermes` block, and creates the new AI peers eagerly. Idempotent — skips profiles that already have a host block.

### Per-profile observation

Each host block can override the observation config independently. Example: a code-focused profile where the AI peer observes the user but doesn't self-model:

```json
"hermes.coder": {
  "aiPeer": "coder",
  "observation": {
    "user": { "observeMe": true, "observeOthers": true },
    "ai":   { "observeMe": false, "observeOthers": true }
  }
}
```

**Observation toggles (one set per peer):**

| Toggle | Effect |
|--------|--------|
| `observeMe` | Honcho builds a representation of this peer from its own messages |
| `observeOthers` | This peer observes the other peer's messages (feeds cross-peer reasoning) |

Presets via `observationMode`:

- **`"directional"`** (default) — all four flags on. Full mutual observation; enables cross-peer dialectic.
- **`"unified"`** — user `observeMe: true`, AI `observeOthers: true`, rest false. Single-observer pool; AI models the user but not itself, user peer only self-models.

Server-side toggles set via the [Honcho dashboard](https://app.honcho.dev) win over local defaults — synced back at session init.

See the [Honcho page](./honcho.md#observation-directional-vs-unified) for the full observation reference.

<details>
<summary>Full honcho.json example (multi-profile)</summary>

```json
{
  "apiKey": "your-key",
  "workspace": "hermes",
  "peerName": "eri",
  "hosts": {
    "hermes": {
      "enabled": true,
      "aiPeer": "hermes",
      "workspace": "hermes",
      "peerName": "eri",
      "recallMode": "hybrid",
      "writeFrequency": "async",
      "sessionStrategy": "per-directory",
      "observation": {
        "user": { "observeMe": true, "observeOthers": true },
        "ai": { "observeMe": true, "observeOthers": true }
      },
      "dialecticReasoningLevel": "low",
      "dialecticDynamic": true,
      "dialecticCadence": 2,
      "dialecticDepth": 1,
      "dialecticMaxChars": 600,
      "contextCadence": 1,
      "messageMaxChars": 25000,
      "saveMessages": true
    },
    "hermes.coder": {
      "enabled": true,
      "aiPeer": "coder",
      "workspace": "hermes",
      "peerName": "eri",
      "recallMode": "tools",
      "observation": {
        "user": { "observeMe": true, "observeOthers": false },
        "ai": { "observeMe": true, "observeOthers": true }
      }
    },
    "hermes.writer": {
      "enabled": true,
      "aiPeer": "writer",
      "workspace": "hermes",
      "peerName": "eri"
    }
  },
  "sessions": {
    "/home/user/myproject": "myproject-main"
  }
}
```

</details>

See the [config reference](https://github.com/NousResearch/hermes-agent/blob/main/plugins/memory/honcho/README.md) and [Honcho integration guide](https://docs.honcho.dev/v3/guides/integrations/hermes).


---

### OpenViking

Context database by Volcengine (ByteDance) with filesystem-style knowledge hierarchy, tiered retrieval, and automatic memory extraction into 6 categories.

| | |
|---|---|
| **Best for** | Self-hosted knowledge management with structured browsing |
| **Requires** | `pip install openviking` + running server |
| **Data storage** | Self-hosted (local or cloud) |
| **Cost** | Free (open-source, AGPL-3.0) |

**Tools (5):** `viking_search` (semantic search), `viking_read` (tiered: abstract/overview/full), `viking_browse` (filesystem navigation), `viking_remember` (store facts), `viking_add_resource` (ingest URLs/docs)

**Setup:**

```bash
# 1. Install OpenViking
pip install openviking

# 2. Configure the server — JSON config at ~/.openviking/ov.conf
mkdir -p ~/.openviking
cat > ~/.openviking/ov.conf << 'EOF'
{
  "server": { "host": "127.0.0.1", "port": 1933, "workers": 1 },
  "storage": { "workspace": "/root/.openviking/workspace" },
  "embedding": {
    "dense": {
      "api_base": "https://api.openai.com/v1",
      "api_key": "sk-...",
      "provider": "openai",
      "model": "text-embedding-3-large",
      "dimension": 3072
    },
    "max_concurrent": 10
  },
  "vlm": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "max_concurrent": 100
  }
}
EOF

# 3. Start via systemd (REQUIRED — never run openviking-server manually)
sudo tee /etc/systemd/system/openviking.service > /dev/null << 'EOF'
[Unit]
Description=OpenViking Memory Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/openviking-server --host 127.0.0.1 --port 1933
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now openviking.service

# 4. Configure Hermes
hermes memory setup    # select "openviking"
# Or manually:
hermes config set memory.provider openviking
echo "OPENVIKING_ENDPOINT=http://localhost:1933" >> ~/.hermes/.env
```

:::tip Ubuntu 24.04+ (PEP 668)
The system blocks `pip install` outside a venv. Use `pip3 install --break-system-packages openviking` or `pipx install openviking`.
:::

:::caution Never start the server manually
Running `openviking-server` directly creates data directory locks, conflicts with Hermes, and disappears on reboot. Always use systemd.
:::

**Environment variables** (set in `~/.hermes/.env`, profile-scoped):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENVIKING_ENDPOINT` | `http://127.0.0.1:1933` | Server URL |
| `OPENVIKING_API_KEY` | *(empty)* | API key (leave blank for local dev mode) |
| `OPENVIKING_ACCOUNT` | `default` | Tenant account ID |
| `OPENVIKING_USER` | `default` | Tenant user ID |
| `OPENVIKING_AGENT` | `hermes` | Agent ID (useful in multi-agent setups) |

**How it works:**

Hermes automatically:
1. **Prefetches** relevant memories before each turn via background thread (non-blocking)
2. **Syncs** conversation turns to OpenViking's session after each response
3. **Commits** the session on session end — triggering automatic extraction of 6 memory categories: profile, preferences, entities, events, cases, and patterns
4. **Mirrors** built-in `memory()` tool writes to OpenViking (user profile → preferences, agent notes → patterns)

**Tiered context loading (L0 → L1 → L2):**

The `viking_read` tool supports three detail levels — start with abstract, escalate only when needed:

| Level | Tokens | When to use |
|-------|--------|-------------|
| `abstract` (L0) | ~100 | Quick relevance check |
| `overview` (L1) | ~2,000 | Key points without full detail |
| `full` (L2) | complete | Deep dive into specific content |

**CLI reference** (`ov` command — installed with `openviking`):

| Command | Purpose |
|---------|---------|
| `ov add-resource <path> --to <uri> --wait` | Import file/directory |
| `ov ls <uri>` / `ov tree <uri>` | List / browse hierarchy |
| `ov read <uri>` / `ov abstract <uri>` / `ov overview <uri>` | Read at L2/L0/L1 |
| `ov find <query>` | Semantic search |
| `ov grep <pattern>` | Full-text content search |
| `ov add-memory` | Add memory entry |
| `ov rm <uri>` / `ov mv <old> <new>` | Delete / move |
| `ov system health` | Quick health check |
| `ov status` | Full status (queues, DB, models) |

**viking:// URI scheme:**

Resources are organized hierarchically under `viking://`:
```
viking://resources/           ← imported docs, guides, project files
viking://resources/guides/    ← documentation
viking://resources/projects/  ← project-specific knowledge
viking://user/<id>/memories/  ← user memories (auto-extracted)
viking://agent/<id>/memories/ ← agent identity & memories
```

:::important Scope rules
`viking_add_resource` (tool) and `ov add-resource` (CLI) **only** work under `viking://resources/`. Using `viking://user/...` or `viking://agent/...` returns `INVALID_URI`. For user memories, use `viking_remember` or `ov add-memory`.
:::

**Bulk import example:**

```bash
# Import a GitHub repo's docs
git clone --depth 1 https://github.com/user/repo.git /tmp/repo
ov add-resource /tmp/repo --parent viking://resources/guides/ --include "*.md"

# Monitor processing
ov observer queue
```

**Reading content — use tools, not raw HTTP:**

- **DO** use `viking_read`, `viking_browse`, `viking_search` (Hermes tools) or `ov read`, `ov tree`, `ov ls` (CLI)
- **DO NOT** use `curl` against the REST API content endpoints — they return empty content for direct HTTP reads

<details>
<summary>Server pitfalls & troubleshooting</summary>

- **`storage.workspace` missing in ov.conf** — Without `"storage": { "workspace": "/root/.openviking/workspace" }`, the server uses a default workspace and silently ignores files you copy. Always verify: `grep workspace ~/.openviking/ov.conf`
- **Embedding dimension mismatch** — If you copy a `vectordb/` from a source using `text-embedding-3-large` (3072d) but your `ov.conf` uses `text-embedding-3-small` (512d), vector search returns garbage. Align model and dimension.
- **First systemd start may fail once** — The first `openviking-server` process can exit with `Application startup failed. Exiting.` (embedding model init race). `Restart=always` + `RestartSec=5` handles this automatically.
- **Health endpoint** is `/health`, not `/api/v1/health` or `/v1/health`.
- **`ov mv` on chunked resources fails** — Once OpenViking has processed and chunked a resource, `ov mv` returns `Internal server error`. Fix: delete the old one (`ov rm --recursive`) before re-importing.
- **Large files (>50k chars) timeout with `--wait`** — Add without `--wait`; the resource is processed asynchronously.
- **VLM model** — `gpt-4-vision-preview` is deprecated by OpenAI. Use `gpt-4o-mini` or `gpt-4o` in the `vlm` section of `ov.conf`.
- **Windows: `ov` CLI double-escapes paths** — Use `viking://` URI prefix (not bare paths). `ov ls resources` returns `NOT_FOUND`; use `ov ls viking://resources`.
- **Windows: BOM in ovcli.conf** — If PowerShell created the config file, a UTF-8 BOM makes the CLI fail. Rewrite from Python or scp from Linux.
- **Account mismatch** — If `ov find` returns empty but health check passes, verify the `account` field in `ovcli.conf` matches your server config.
</details>

<details>
<summary>Cross-machine sync (content migration)</summary>

When syncing between machines with different embedding models (e.g. `text-embedding-3-large` 3072d on one, `text-embedding-3-small` 512d on another):

```bash
# 1. Stop OpenViking on both machines
systemctl stop openviking

# 2. Clear target's vectordb (MANDATORY if embedding models differ)
rm -rf /root/.openviking/workspace/vectordb/

# 3. Sync content (exclude vectordb and internal state)
rsync -avz --delete \
  --exclude='vectordb/' --exclude='queue/' --exclude='.openviking.pid' --exclude='LOCK' \
  /root/.openviking/workspace/ root@target:/root/.openviking/workspace/

# 4. Restart both
systemctl start openviking
```

The target's vectordb rebuilds asynchronously on startup. Vector search returns empty until indexing completes (~30s for ~3.5MB of content).

**Critical:** Never copy `vectordb/` between machines with different embedding dimensions — it causes silent corruption.
</details>

<details>
<summary>OpenViking Memory Plugin for OpenCode</summary>

A TypeScript plugin connects OpenViking directly into OpenCode, providing 4 memory tools (`memsearch`, `memread`, `membrowse`, `memcommit`) plus auto-recall (injection into every user message) and auto-commit (background extraction every 10 min).

```bash
mkdir -p ~/.config/opencode/plugins
curl -sL "https://raw.githubusercontent.com/volcengine/OpenViking/main/examples/opencode-memory-plugin/openviking-memory.ts" \
  -o ~/.config/opencode/plugins/openviking-memory.ts
```

Config at `~/.config/opencode/plugins/openviking-config.json`:
```json
{
  "endpoint": "http://localhost:1933",
  "apiKey": "",
  "enabled": true,
  "timeoutMs": 30000,
  "autoCommit": { "enabled": true, "intervalMinutes": 10 },
  "autoRecall": { "enabled": true, "limit": 6, "scoreThreshold": 0.15,
    "maxContentChars": 500, "preferAbstract": true, "tokenBudget": 2000 }
}
```

No entry in `opencode.json` needed. Restart OpenCode server after installation.
</details>

<details>
<summary>REST API reference (for scripting)</summary>

The OpenViking REST API works via curl when the `ov` CLI isn't available.

**Server:** `http://127.0.0.1:1933` (dev mode, no API key needed)

```bash
# Health check
curl -s http://127.0.0.1:1933/health

# Semantic search
curl -s http://127.0.0.1:1933/api/v1/search/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"your search query","limit":10}'

# Find (no session context)
curl -s http://127.0.0.1:1933/api/v1/search/find \
  -H 'Content-Type: application/json' \
  -d '{"query":"hermes","target_uri":"viking://resources","limit":5}'

# Glob (pattern matching)
curl -s http://127.0.0.1:1933/api/v1/search/glob \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"**/*hermes*","uri":"viking://resources","node_limit":20}'

# Grep (full-text search)
curl -s http://127.0.0.1:1933/api/v1/search/grep \
  -H 'Content-Type: application/json' \
  -d '{"uri":"viking://resources","pattern":"hermes","case_insensitive":true}'
```

**Direct filesystem access:** Resources are stored at `/root/.openviking/workspace/viking/default/resources/`. Direct writes bypass the embedding pipeline — use `viking_add_resource` or `ov add-resource` for indexed content.
</details>


---

### Mem0

Server-side LLM fact extraction with semantic search, reranking, and automatic deduplication.

| | |
|---|---|
| **Best for** | Hands-off memory management — Mem0 handles extraction automatically |
| **Requires** | `pip install mem0ai` + API key |
| **Data storage** | Mem0 Cloud |
| **Cost** | Mem0 pricing |

**Tools:** `mem0_profile` (all stored memories), `mem0_search` (semantic search + reranking), `mem0_conclude` (store verbatim facts)

**Setup:**
```bash
hermes memory setup    # select "mem0"
# Or manually:
hermes config set memory.provider mem0
echo "MEM0_API_KEY=your-key" >> ~/.hermes/.env
```

**Config:** `$HERMES_HOME/mem0.json`

| Key | Default | Description |
|-----|---------|-------------|
| `user_id` | `hermes-user` | User identifier |
| `agent_id` | `hermes` | Agent identifier |

---

### Hindsight

Long-term memory with knowledge graph, entity resolution, and multi-strategy retrieval. The `hindsight_reflect` tool provides cross-memory synthesis that no other provider offers. Automatically retains full conversation turns (including tool calls) with session-level document tracking.

| | |
|---|---|
| **Best for** | Knowledge graph-based recall with entity relationships |
| **Requires** | Cloud: API key from [ui.hindsight.vectorize.io](https://ui.hindsight.vectorize.io). Local: LLM API key (OpenAI, Groq, OpenRouter, etc.) |
| **Data storage** | Hindsight Cloud or local embedded PostgreSQL |
| **Cost** | Hindsight pricing (cloud) or free (local) |

**Tools:** `hindsight_retain` (store with entity extraction), `hindsight_recall` (multi-strategy search), `hindsight_reflect` (cross-memory synthesis)

**Setup:**
```bash
hermes memory setup    # select "hindsight"
# Or manually:
hermes config set memory.provider hindsight
echo "HINDSIGHT_API_KEY=your-key" >> ~/.hermes/.env
```

The setup wizard installs dependencies automatically and only installs what's needed for the selected mode (`hindsight-client` for cloud, `hindsight-all` for local). Requires `hindsight-client >= 0.4.22` (auto-upgraded on session start if outdated).

**Local mode UI:** `hindsight-embed -p hermes ui start`

**Config:** `$HERMES_HOME/hindsight/config.json`

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `cloud` | `cloud` or `local` |
| `bank_id` | `hermes` | Memory bank identifier |
| `recall_budget` | `mid` | Recall thoroughness: `low` / `mid` / `high` |
| `memory_mode` | `hybrid` | `hybrid` (context + tools), `context` (auto-inject only), `tools` (tools only) |
| `auto_retain` | `true` | Automatically retain conversation turns |
| `auto_recall` | `true` | Automatically recall memories before each turn |
| `retain_async` | `true` | Process retain asynchronously on the server |
| `retain_context` | `conversation between Hermes Agent and the User` | Context label for retained memories |
| `retain_tags` | — | Default tags applied to retained memories; merged with per-call tool tags |
| `retain_source` | — | Optional `metadata.source` attached to retained memories |
| `retain_user_prefix` | `User` | Label used before user turns in auto-retained transcripts |
| `retain_assistant_prefix` | `Assistant` | Label used before assistant turns in auto-retained transcripts |
| `recall_tags` | — | Tags to filter on recall |

See [plugin README](https://github.com/NousResearch/hermes-agent/blob/main/plugins/memory/hindsight/README.md) for the full configuration reference.

---

### Holographic

Local SQLite fact store with FTS5 full-text search, trust scoring, and HRR (Holographic Reduced Representations) for compositional algebraic queries.

| | |
|---|---|
| **Best for** | Local-only memory with advanced retrieval, no external dependencies |
| **Requires** | Nothing (SQLite is always available). NumPy optional for HRR algebra. |
| **Data storage** | Local SQLite |
| **Cost** | Free |

**Tools:** `fact_store` (9 actions: add, search, probe, related, reason, contradict, update, remove, list), `fact_feedback` (helpful/unhelpful rating that trains trust scores)

**Setup:**
```bash
hermes memory setup    # select "holographic"
# Or manually:
hermes config set memory.provider holographic
```

**Config:** `config.yaml` under `plugins.hermes-memory-store`

| Key | Default | Description |
|-----|---------|-------------|
| `db_path` | `$HERMES_HOME/memory_store.db` | SQLite database path |
| `auto_extract` | `false` | Auto-extract facts at session end |
| `default_trust` | `0.5` | Default trust score (0.0–1.0) |

**Unique capabilities:**
- `probe` — entity-specific algebraic recall (all facts about a person/thing)
- `reason` — compositional AND queries across multiple entities
- `contradict` — automated detection of conflicting facts
- Trust scoring with asymmetric feedback (+0.05 helpful / -0.10 unhelpful)

---

### RetainDB

Cloud memory API with hybrid search (Vector + BM25 + Reranking), 7 memory types, and delta compression.

| | |
|---|---|
| **Best for** | Teams already using RetainDB's infrastructure |
| **Requires** | RetainDB account + API key |
| **Data storage** | RetainDB Cloud |
| **Cost** | $20/month |

**Tools:** `retaindb_profile` (user profile), `retaindb_search` (semantic search), `retaindb_context` (task-relevant context), `retaindb_remember` (store with type + importance), `retaindb_forget` (delete memories)

**Setup:**
```bash
hermes memory setup    # select "retaindb"
# Or manually:
hermes config set memory.provider retaindb
echo "RETAINDB_API_KEY=your-key" >> ~/.hermes/.env
```

---

### ByteRover

Persistent memory via the `brv` CLI — hierarchical knowledge tree with tiered retrieval (fuzzy text → LLM-driven search). Local-first with optional cloud sync.

| | |
|---|---|
| **Best for** | Developers who want portable, local-first memory with a CLI |
| **Requires** | ByteRover CLI (`npm install -g byterover-cli` or [install script](https://byterover.dev)) |
| **Data storage** | Local (default) or ByteRover Cloud (optional sync) |
| **Cost** | Free (local) or ByteRover pricing (cloud) |

**Tools:** `brv_query` (search knowledge tree), `brv_curate` (store facts/decisions/patterns), `brv_status` (CLI version + tree stats)

**Setup:**
```bash
# Install the CLI first
curl -fsSL https://byterover.dev/install.sh | sh

# Then configure Hermes
hermes memory setup    # select "byterover"
# Or manually:
hermes config set memory.provider byterover
```

**Key features:**
- Automatic pre-compression extraction (saves insights before context compression discards them)
- Knowledge tree stored at `$HERMES_HOME/byterover/` (profile-scoped)
- SOC2 Type II certified cloud sync (optional)

---

### Supermemory

Semantic long-term memory with profile recall, semantic search, explicit memory tools, and session-end conversation ingest via the Supermemory graph API.

| | |
|---|---|
| **Best for** | Semantic recall with user profiling and session-level graph building |
| **Requires** | `pip install supermemory` + [API key](https://supermemory.ai) |
| **Data storage** | Supermemory Cloud |
| **Cost** | Supermemory pricing |

**Tools:** `supermemory_store` (save explicit memories), `supermemory_search` (semantic similarity search), `supermemory_forget` (forget by ID or best-match query), `supermemory_profile` (persistent profile + recent context)

**Setup:**
```bash
hermes memory setup    # select "supermemory"
# Or manually:
hermes config set memory.provider supermemory
echo 'SUPERMEMORY_API_KEY=***' >> ~/.hermes/.env
```

**Config:** `$HERMES_HOME/supermemory.json`

| Key | Default | Description |
|-----|---------|-------------|
| `container_tag` | `hermes` | Container tag used for search and writes. Supports `{identity}` template for profile-scoped tags. |
| `auto_recall` | `true` | Inject relevant memory context before turns |
| `auto_capture` | `true` | Store cleaned user-assistant turns after each response |
| `max_recall_results` | `10` | Max recalled items to format into context |
| `profile_frequency` | `50` | Include profile facts on first turn and every N turns |
| `capture_mode` | `all` | Skip tiny or trivial turns by default |
| `search_mode` | `hybrid` | Search mode: `hybrid`, `memories`, or `documents` |
| `api_timeout` | `5.0` | Timeout for SDK and ingest requests |

**Environment variables:** `SUPERMEMORY_API_KEY` (required), `SUPERMEMORY_CONTAINER_TAG` (overrides config).

**Key features:**
- Automatic context fencing — strips recalled memories from captured turns to prevent recursive memory pollution
- Full-session ingest — the entire conversation is sent once at session boundaries
- Session-end conversation ingest (to `/v4/conversations`) for richer profile + graph building in Supermemory
- Profile facts injected on first turn and at configurable intervals
- **Profile-scoped containers** — use `{identity}` in `container_tag` (e.g. `hermes-{identity}` → `hermes-coder`) to isolate memories per Hermes profile
- **Multi-container mode** — enable `enable_custom_container_tags` with a `custom_containers` list to let the agent read/write across named containers. Automatic operations stay on the primary container.

<details>
<summary>Multi-container example</summary>

```json
{
  "container_tag": "hermes",
  "enable_custom_container_tags": true,
  "custom_containers": ["project-alpha", "shared-knowledge"],
  "custom_container_instructions": "Use project-alpha for coding context."
}
```

</details>

**Support:** [Discord](https://supermemory.link/discord) · [support@supermemory.com](mailto:support@supermemory.com)

### Memori

Structured long-term memory using Memori Cloud, with background completed-turn capture, tool-aware turn context, and explicit recall tools for facts, summaries, quota, signup, and feedback.

| | |
|---|---|
| **Best for** | Agent-controlled recall with structured project and session attribution |
| **Requires** | `pip install hermes-memori` + `hermes-memori install` + [Memori API key](https://app.memorilabs.ai/signup) |
| **Data storage** | Memori Cloud |
| **Cost** | Memori pricing |

**Tools:** `memori_recall` (search long-term memory), `memori_recall_summary` (summarized context), `memori_quota` (usage/quota), `memori_signup` (request signup email), `memori_feedback` (send integration feedback)

**Setup:**
```bash
pip install hermes-memori
hermes-memori install
hermes config set memory.provider memori
hermes memory setup
```

---

## Provider Comparison

| Provider | Storage | Cost | Tools | Dependencies | Unique Feature |
|----------|---------|------|-------|-------------|----------------|
| **Honcho** | Cloud | Paid | 5 | `honcho-ai` | Dialectic user modeling + session-scoped context |
| **OpenViking** | Self-hosted | Free | 5 | `openviking` + server | Filesystem hierarchy + tiered loading |
| **Mem0** | Cloud | Paid | 3 | `mem0ai` | Server-side LLM extraction |
| **Hindsight** | Cloud/Local | Free/Paid | 3 | `hindsight-client` | Knowledge graph + reflect synthesis |
| **Holographic** | Local | Free | 2 | None | HRR algebra + trust scoring |
| **RetainDB** | Cloud | $20/mo | 5 | `requests` | Delta compression |
| **ByteRover** | Local/Cloud | Free/Paid | 3 | `brv` CLI | Pre-compression extraction |
| **Supermemory** | Cloud | Paid | 4 | `supermemory` | Context fencing + session graph ingest + multi-container |
| **Memori** | Cloud | Free/Paid | 5 | `hermes-memori` | Tool-aware memory + structured recall |

## Profile Isolation

Each provider's data is isolated per [profile](/user-guide/profiles):

- **Local storage providers** (Holographic, ByteRover) use `$HERMES_HOME/` paths which differ per profile
- **Config file providers** (Honcho, Mem0, Hindsight, Supermemory) store config in `$HERMES_HOME/` so each profile has its own credentials
- **Cloud providers** (RetainDB) auto-derive profile-scoped project names
- **Env var providers** (OpenViking) are configured via each profile's `.env` file

## Building a Memory Provider

See the [Developer Guide: Memory Provider Plugins](/developer-guide/memory-provider-plugin) for how to create your own.

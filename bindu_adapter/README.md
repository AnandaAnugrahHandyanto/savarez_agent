# Hermes ↔ Bindu A2A Adapter

Run Hermes Agent as an **Agent-to-Agent (A2A) microservice** with a cryptographic identity, OAuth2 auth, and optional crypto payments — so *other* agents and gateways can call it the same way humans talk to it from the CLI.

> TL;DR — with ~90 lines of adapter code and `pip install .[bindu]`, your running Hermes becomes a discoverable, signed, callable service. Same agent, same skills, same memory. New interface.

---

## Why would I want this?

Hermes already shines at the human-facing interface — CLI, Telegram, Discord, Slack, WhatsApp, Signal. The gateway makes Hermes talk to *people* on their terms.

This adapter adds the other half: making Hermes talk to *other agents* on their terms. Four concrete things you get:

### 1. A standard protocol other agents can speak

[A2A](https://a2aproject.github.io/A2A/) is a JSON-RPC spec for agent-to-agent calls. LangChain, AG2/AutoGen, the OpenAI Agents SDK, and an increasing number of frameworks speak it natively. Once your Hermes is on A2A, any of those agents can call it — delegate a research task, ask a follow-up, feed results into a pipeline — without anyone writing an HTTP client for Hermes' internals.

```
Other agent (LangChain/AG2/etc.) ──► A2A JSON-RPC ──► your Hermes
                                                         │
                                              full skill loop, memory, tools
                                                         │
                                  ◄──── DID-signed artifact reply ────
```

### 2. A cryptographic identity, not just a URL

Hermes publishes a DID (`did:bindu:<author>:<name>:<uuid>`) derived from an Ed25519 keypair. Every response artifact is signed with that key. For the calling agent, that means:

- **Authenticity** — the response really came from *your* Hermes, not a man-in-the-middle.
- **Accountability** — you can log the DID alongside the artifact for audit.
- **Interop** — DID is a W3C standard; anything that resolves DIDs can verify a Hermes response without a shared database.

### 3. OAuth2 out of the box

The adapter registers Hermes with [Ory Hydra](https://www.ory.sh/hydra/) and issues scoped tokens (`agent:read`, `agent:write`, `agent:execute`). If your hermes-agent deployment is only allowed to talk to a specific other agent — enforce that with a scope, not with a firewall rule and a prayer.

### 4. Monetization that doesn't require Stripe

Bindu ships with [x402](https://www.x402.org/) support — HTTP-native micropayments in USDC on Base. Flip one config flag and callers must pay 0.01 USDC (or whatever you set) before Hermes processes the request. No API gateway, no billing vendor, no webhook reconciliation. Just the HTTP 402 status code doing what it was invented for.

---

## What this isn't

This adapter does **not** replace `hermes gateway`. It's additive.

- Use **`hermes`** (the CLI) to talk to your agent yourself.
- Use **`hermes gateway`** to talk to your agent from Telegram/Discord/Slack/WhatsApp/Signal.
- Use **`hermes-bindu`** to let *other agents* talk to your agent over A2A.

All three can run against the same Hermes configuration. They share skills, memory, tools, and context files.

---

## Quick start

### 1. Install the extra

```bash
pip install -e '.[bindu]'
```

That pulls [`bindu`](https://github.com/GetBindu/Bindu) alongside Hermes. Nothing in your existing Hermes install changes.

### 2. Set an LLM key

```bash
# In ~/.hermes/.env (same file the main CLI uses)
OPENROUTER_API_KEY=sk-or-v1-...
```

Any provider Hermes already supports works — this adapter just delegates to `AIAgent`, so `hermes model` settings carry over. Or override per-process with `HERMES_BINDU_MODEL`.

### 3. Run it

```bash
hermes-bindu
```

The banner prints your agent's DID and the A2A endpoint:

```
🚀 Bindu Server 🚀
Local Server: http://localhost:3773

Agent DID: did:bindu:you_at_example_com:hermes:<uuid>
```

### 4. Call it

Standard A2A JSON-RPC over HTTP. From the same machine:

```bash
uuid() { uuidgen | tr 'A-Z' 'a-z'; }
TID=$(uuid); MID=$(uuid); CID=$(uuid); RID=$(uuid)

curl -sS -X POST http://localhost:3773/ \
  -H 'Content-Type: application/json' \
  -d "{
    \"jsonrpc\":\"2.0\",\"method\":\"message/send\",\"id\":\"$RID\",
    \"params\":{
      \"message\":{
        \"role\":\"user\",
        \"parts\":[{\"kind\":\"text\",\"text\":\"summarize the last Hacker News frontpage\"}],
        \"kind\":\"message\",
        \"messageId\":\"$MID\",\"contextId\":\"$CID\",\"taskId\":\"$TID\"
      }
    }
  }" | jq

# Poll tasks/get until state is completed
curl -sS -X POST http://localhost:3773/ \
  -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"tasks/get\",\"id\":\"$(uuid)\",\"params\":{\"taskId\":\"$TID\"}}" \
  | jq '.result | {state: .status.state, text: .artifacts[0].parts[0].text}'
```

The first call returns immediately with `state: submitted`; the artifact lands when `state: completed`. Authenticated calls also send `Authorization`, `X-DID`, `X-DID-Signature`, `X-DID-Timestamp` headers — see the [A2A spec](https://github.com/GetBindu/Bindu/blob/main/openapi.yaml) and Bindu's examples for the full signing flow.

---

## Safety tiers

Hermes exposes ~20 toolsets. An agent callable over the public internet should not have a shell. Set `HERMES_BINDU_TIER` to gate what the A2A-exposed agent can reach:

| Tier | Toolsets exposed | When to use |
|---|---|---|
| `read` *(default)* | `web` (search + extract) | Public endpoints, tunneled exposure, untrusted callers |
| `sandbox` | `web` + `file` + `moa` | Trusted callers, ephemeral container, filesystem OK |
| `full` | Everything — terminal, browser, code exec, MCP | **Localhost only** |

> ⚠️ **Never combine `full` with `HERMES_BINDU_EXPOSE=true`.** That exposes a remote shell over HTTP to the internet. Don't do it.

---

## Configuration

Every knob is an env var; nothing requires editing code. Add to `~/.hermes/.env` or export inline.

| Variable | Default | Purpose |
|---|---|---|
| `HERMES_BINDU_MODEL` | `anthropic/claude-3.5-haiku` | LLM backing the A2A-exposed agent |
| `HERMES_BINDU_TIER` | `read` | Toolset tier (`read` / `sandbox` / `full`) |
| `HERMES_BINDU_MAX_ITERATIONS` | `30` | Max tool-calling loops per A2A request |
| `HERMES_BINDU_URL` | `http://localhost:3773` | Public URL Bindu advertises in the agent card |
| `HERMES_BINDU_NAME` | `hermes` | Agent display name |
| `HERMES_BINDU_AUTHOR` | `you@example.com` | Author field on the agent card |
| `HERMES_BINDU_DESCRIPTION` | *(see entry.py)* | Agent description on the agent card |
| `HERMES_BINDU_EXPOSE` | `false` | If `true`, Bindu opens a public FRP tunnel |

Bindu-level settings (payments, Hydra URLs, etc.) follow Bindu's own env conventions — see [Bindu's docs](https://docs.getbindu.com) or the generated `~/.hermes/.bindu/` directory.

---

## How it fits together

```
                        ┌──────────────────────────────────────┐
  other agent ─► A2A ──►│  Bindu HTTP server (:3773)           │
                        │    • OAuth2 (Hydra)                   │
                        │    • DID verification                 │
                        │    • x402 payment (optional)          │
                        │    • ManifestWorker                   │
                        │              │                        │
                        │              ▼                        │
                        │    bindu_adapter.handler(messages)    │
                        │              │                        │
                        │              ▼                        │
                        │    AIAgent.chat(latest_user_text)     │
                        │              │                        │
                        │              └─► Hermes tool loop ──► │
                        │                  (web, file, memory,  │
                        │                   skills, …)          │
                        └──────────────────────────────────────┘
```

The handler keeps **one shared `AIAgent`** per process. Bindu is the source of truth for conversation history; Hermes owns the live model state so provider prompt caches stay valid across turns.

---

## Files

| File | Purpose |
|---|---|
| `adapter.py` | `AIAgent` wrapped as a Bindu `handler(messages) -> str` |
| `entry.py` | CLI entry: loads env, builds the Bindu config, calls `bindufy()` |
| `__main__.py` | Enables `python -m bindu_adapter` |

~200 lines of glue. No forked code paths, no parallel tool registry, no second event loop.

---

## Troubleshooting

- **`ImportError: No module named 'bindu'`** — you didn't install the extra. Run `pip install -e '.[bindu]'`.
- **`401` / `403` on requests** — you're hitting the auth layers. The banner at startup prints a curl snippet for fetching a Hydra token; use that as the `Authorization: Bearer <token>` and sign each request with the DID keys in `~/.hermes/.bindu/` (or the project's `.bindu/`).
- **Port 3773 already in use** — another agent is running. Set `HERMES_BINDU_URL=http://localhost:4000` (or any free port).
- **Tool calls silently blocked** — you're on the default `read` tier. Flip to `sandbox` or `full` if (and only if) it's safe for your deployment.

---

## Learn more

- Bindu source: <https://github.com/GetBindu/Bindu>
- A2A protocol: <https://a2aproject.github.io/A2A/>
- x402 payments: <https://www.x402.org/>
- DID method spec: <https://www.w3.org/TR/did-core/>

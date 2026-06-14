---
sidebar_position: 12
title: "A2A (Agent2Agent) Server"
description: "Run Hermes Agent as an A2A server so other agents can discover it and delegate tasks over JSON-RPC + SSE"
---

# A2A (Agent2Agent) Server

Hermes Agent can run as an [A2A](https://a2a-protocol.org) server, letting any
A2A-compatible client or peer agent discover it and delegate tasks over
HTTP(S). Where MCP connects an agent to _tools_, A2A connects an agent to
_other agents_ — so A2A turns Hermes into a callable worker for orchestrators
like LangGraph, CrewAI, Google ADK, the `a2a-inspector`, or another Hermes.

It is the sibling of [ACP](./acp.md) (editor integration over stdio) and the
MCP server (tools over MCP): A2A is **Hermes as a remote agent for other
agents**.

## What Hermes exposes in A2A mode

- An **Agent Card** at `/.well-known/agent-card.json` describing Hermes' name,
  version, capabilities (streaming), and skills.
- `message/send` — synchronous request/response (returns a completed task).
- `message/stream` — Server-Sent Events streaming of task status updates and
  artifacts.
- `tasks/get` and `tasks/cancel`.

Each turn runs with the curated `hermes-a2a` toolset (coding, shell,
filesystem, web/browser, memory, todo, skills, `execute_code`,
`delegate_task`) — the non-interactive counterpart of `hermes-acp`, without
messaging, audio, or clarify UI.

## Installation

Install Hermes normally, then add the A2A extra:

```bash
pip install -e '.[a2a]'
```

This installs the `a2a-sdk[http-server]` dependency and enables:

- `hermes a2a`
- `hermes-a2a`
- `python -m a2a_adapter`

## Launching the A2A server

Any of the following starts Hermes in A2A mode:

```bash
hermes a2a
```

```bash
hermes-a2a
```

```bash
python -m a2a_adapter
```

By default the server binds `127.0.0.1:9100`. The Agent Card is served at
`/.well-known/agent-card.json` and the JSON-RPC endpoint at `/`.

```bash
hermes a2a --host 127.0.0.1 --port 9100
hermes a2a --public-url https://agents.example.com/hermes/   # URL advertised in the card
```

For non-interactive checks:

```bash
hermes a2a --version
hermes a2a --check
```

:::warning Exposing to the network
The A2A endpoint is **unauthenticated**. Binding `--host 0.0.0.0` exposes
Hermes — and its shell/filesystem tools — to anything that can reach the port.
Only do so behind a reverse proxy or auth layer you control. The server logs a
warning when started on `0.0.0.0`.
:::

## Talking to the server

Fetch the card, then send a message. With `curl`:

```bash
curl http://127.0.0.1:9100/.well-known/agent-card.json

curl http://127.0.0.1:9100/ -H 'Content-Type: application/json' -d '{
  "jsonrpc": "2.0", "id": "1", "method": "message/send",
  "params": {"message": {"role": "user", "kind": "message", "messageId": "m1",
    "parts": [{"kind": "text", "text": "Summarize what this repo does."}]}}
}'
```

`message/stream` uses the same body with `"method": "message/stream"` (the
method name is what selects streaming; an `Accept: text/event-stream` header is
the conventional client courtesy). The response is an SSE stream of
`TaskStatusUpdateEvent` (working) and `TaskArtifactUpdateEvent` (the result),
ending in a `completed` status.

## Conversation continuity

A2A `contextId` maps to a persistent Hermes session: one `AIAgent` plus its
rolling history per context. Follow-up messages that reuse the same `contextId`
continue the same conversation. Each `taskId` is one turn within a context.
Sessions are held in memory for the lifetime of the server process.

## Configuration and credentials

A2A mode uses the same Hermes configuration as the CLI:

- `~/.hermes/.env`
- `~/.hermes/config.yaml`
- `~/.hermes/skills/`

Provider resolution uses Hermes' normal runtime resolver, so A2A inherits the
currently configured provider and credentials. Host and port are CLI flags
(not config or env keys); configure credentials with `hermes model` or by
editing `~/.hermes/.env`.

## Troubleshooting

### Server starts but tasks fail immediately

Verify dependencies and provider setup:

```bash
hermes a2a --check
hermes model
hermes doctor
```

### A client cannot discover the agent

Confirm the card is reachable and the client points at the base URL (not the
card URL):

```bash
curl -fsS http://127.0.0.1:9100/.well-known/agent-card.json
```

## See also

- [A2A Internals](../../developer-guide/a2a-internals.md)
- [ACP Editor Integration](./acp.md)
- [Provider Runtime Resolution](../../developer-guide/provider-runtime.md)

---
sidebar_position: 3
title: "A2A Internals"
description: "How the A2A adapter works: lifecycle, context sessions, event bridge, and the Agent Card"
---

# A2A Internals

The A2A adapter wraps Hermes' synchronous `AIAgent` in an async JSON-RPC + SSE
HTTP server built on the [`a2a-sdk`](https://a2a-protocol.org). It mirrors the
[ACP adapter](./acp-internals.md): a protocol server class drives the same
`AIAgent` callback seam, just translating events to A2A instead of ACP.

Key implementation files:

- `a2a_adapter/entry.py`
- `a2a_adapter/card.py`
- `a2a_adapter/executor.py`
- `a2a_adapter/sessions.py`
- `a2a_adapter/events.py`

## Boot flow

```text
hermes a2a / hermes-a2a / python -m a2a_adapter
  -> a2a_adapter.entry.main()
  -> parse --version / --check before server startup
  -> load ~/.hermes/.env
  -> discover MCP tools (tools.mcp_tool.discover_mcp_tools)
  -> build_app(): AgentCard + DefaultRequestHandler + InMemoryTaskStore
                  -> A2AStarletteApplication(...).build()
  -> uvicorn.run(app)
```

The Agent Card is served at `/.well-known/agent-card.json`; the JSON-RPC
endpoint is at `/`.

## Major components

### `HermesAgentExecutor`

`a2a_adapter/executor.py` implements the a2a-sdk `AgentExecutor` interface
(`execute` / `cancel`).

`execute()`:

- reads the user text and resolves (or creates) the task via `new_task`
- creates a `TaskUpdater`, marks the task `working`
- resolves the Hermes session for `contextId`
- wires AIAgent callbacks to A2A events
- runs `AIAgent.run_conversation` in a worker thread (`asyncio.to_thread`)
- emits the final response as an artifact, then marks the task `completed`

`cancel()` signals the session and emits a `canceled` status.

### `ContextSessionStore`

`a2a_adapter/sessions.py` maps `contextId` to a `HermesSession` (an `AIAgent`,
its rolling history, and a cancel event). It is thread-safe, creates agents
lazily, and accepts an `agent_factory` so tests can inject a fake. The real
build mirrors `acp_adapter.session._make_agent`
(`platform="a2a"`, `enabled_toolsets=["hermes-a2a", ...]`).

### Event bridge

`a2a_adapter/events.py` converts AIAgent callbacks into `TaskUpdater` events:

- `stream_delta_callback` -> `working` status with the text chunk
- `tool_progress_callback` -> `working` status tagged `hermes/kind=tool-call`
- `step_callback` -> `working` status tagged `hermes/kind=tool-result`
- `reasoning_callback` -> `working` status tagged `hermes/kind=reasoning`
- final response -> `add_artifact(...)` + `complete()`

Because `AIAgent` runs in a worker thread while the A2A event queue lives on the
server event loop, the bridge marshals each async update with:

```python
asyncio.run_coroutine_threadsafe(...)
```

and blocks briefly on it so updates preserve order relative to the agent's own
progress (and all working updates land before the final artifact). A failed
update is logged and swallowed — it never aborts the turn.

### Agent Card

`a2a_adapter/card.py` builds the `AgentCard` dynamically from the Hermes
version plus a curated skill list (general agent, research). Unlike ACP's
checked-in `acp_registry/agent.json`, the A2A card is built at server startup
(no static JSON manifest to keep in sync) and re-serialized on each
`/.well-known/agent-card.json` request.

## Task lifecycle

```text
message/send | message/stream
  -> DefaultRequestHandler -> HermesAgentExecutor.execute()
     -> new_task() (if no current task) -> enqueue Task
     -> TaskUpdater.start_work()              [status: working]
     -> to_thread(AIAgent.run_conversation)
          stream_delta / tool_progress / step -> working status updates
     -> add_artifact(final_response)          [artifact-update]
     -> complete()                            [status: completed]
```

## Cancelation

`cancel()` sets the session cancel event and calls `agent.interrupt()` when
available, then emits a terminal `canceled` status.

## Current limitations

- In-memory task store and sessions: both are lost on process restart.
- The endpoint is served unauthenticated; bind `127.0.0.1` or front it with a
  proxy/auth layer (see the security note in the user guide).
- Push notifications, persistent task stores, and gRPC / HTTP+JSON transports
  are not part of this cut. (`tasks/resubscribe` is routable via the SDK's
  default handler but is not exercised by this adapter's tests.)
- Input is text-only; the seam accepts richer parts later.

## Related files

- `tests/a2a/` — A2A test suite
- `toolsets.py` — `hermes-a2a` toolset definition
- `hermes_cli/main.py` — `hermes a2a` CLI subcommand
- `pyproject.toml` — `[a2a]` optional dependency + `hermes-a2a` script
- `.plans/a2a-protocol.md` — design + protocol-to-Hermes mapping

---
sidebar_position: 5
title: "Runtime API v0"
description: "Draft contract for Hermes-owned durable runs, observable events, reconnect, and external workbench control planes"
---

# Runtime API v0

This page is the first architecture contract for making Hermes Agent the source of truth for agent run lifecycle while browser or desktop clients stay rich workbenches over that runtime.

The immediate driver is the `nesquena/hermes-webui` architecture tracker [#1925](https://github.com/nesquena/hermes-webui/issues/1925): WebUI should be **thin in execution ownership, not thin in product scope**. WebUI can remain the primary workbench for sessions, files, tool cards, reasoning, approvals, status, and admin surfaces, but Hermes Agent must own durable runs, event ordering, reconnect semantics, controls, and terminal state.

## Current state

Hermes already exposes an API Server adapter in `gateway/platforms/api_server.py` with run-like endpoints:

| Endpoint | Current role |
|---|---|
| `POST /v1/runs` | Start an API-server run and return a `run_id` immediately. |
| `GET /v1/runs/{run_id}` | Return in-process run status retained for a short TTL. |
| `GET /v1/runs/{run_id}/events` | Stream live SSE events from an in-memory queue. |
| `POST /v1/runs/{run_id}/approval` | Resolve a pending dangerous-command approval. |
| `POST /v1/runs/{run_id}/stop` | Interrupt a running agent. |

That surface is useful substrate, but it is not yet the full runtime contract required by first-class clients:

- events are live queue events, not a durable ordered event log with cursor replay;
- active run discovery is process-local;
- `session_id -> active run(s)` mapping is not a stable API;
- terminal status has a TTL rather than durable session/run state;
- clarify response, queue/continue, steer/interrupt variants, and command capability metadata are incomplete;
- restarting the API Server process still loses active in-process runs.

So v0 below is both a target contract and a gap list. Implementations may start behind feature flags, but clients should not paper over missing runtime semantics by rebuilding private runtime state.

## Design goals

1. **Hermes owns execution.** The runtime, not a UI adapter, owns `run_id`, lifecycle, cancellation, approval/clarify state, event ordering, and terminal status.
2. **Clients own presentation.** WebUI, dashboard, TUI, mobile, and other clients can render different experiences over the same runtime truth.
3. **Reconnect is a first-class behavior.** A client may disconnect, refresh, or briefly restart and then catch up from a cursor without duplicating the run.
4. **Controls are authoritative.** Stop, interrupt, queue/continue, approval, clarify, and goal controls mutate Hermes runtime state through APIs, not local client objects.
5. **Compatibility adapters are protocol translators, not runtime surrogates.** If a client adapter recreates `STREAMS`, cached `AIAgent` objects, local cancellation flags, or private approval queues, the boundary has failed.

## Core objects

### Run

A run is one execution attempt owned by Hermes.

Minimum fields:

```json
{
  "object": "hermes.run",
  "run_id": "run_...",
  "session_id": "session_...",
  "status": "queued|running|waiting_for_approval|waiting_for_clarify|stopping|completed|failed|cancelled",
  "created_at": 1778536800.0,
  "updated_at": 1778536812.5,
  "model": "gpt-5.5",
  "provider": "openai-codex",
  "workspace": "/home/michael/projects/example",
  "profile": "default",
  "toolsets": ["terminal", "file"],
  "last_event_id": 42,
  "active_controls": ["cancel", "queue", "approval.respond"],
  "terminal": false
}
```

Terminal runs additionally expose:

```json
{
  "terminal": true,
  "terminal_state": "completed|failed|cancelled",
  "output": "final assistant response when available",
  "error": null,
  "usage": {
    "input_tokens": 1000,
    "output_tokens": 500,
    "total_tokens": 1500
  }
}
```

### Event

An event is an ordered record in a run event log.

Minimum fields:

```json
{
  "object": "hermes.run.event",
  "run_id": "run_...",
  "session_id": "session_...",
  "event_id": 42,
  "event": "message.delta",
  "timestamp": 1778536812.5,
  "payload": {}
}
```

`event_id` is monotonically increasing within a run. Clients use it as the cursor for replay. SSE should emit it as both the SSE `id:` field and inside the JSON body so non-SSE transports can share the same contract.

## Runtime API surface

The transport can be HTTP/SSE first, but the contract should remain portable to stdio, WebSocket, ACP, or plugin-internal IPC.

### Start a run

```text
POST /v1/runs
```

Request:

```json
{
  "session_id": "optional existing session id",
  "input": "user text or structured input",
  "conversation_history": [],
  "workspace": "/path/to/workspace",
  "profile": "default",
  "model": "gpt-5.5",
  "provider": "openai-codex",
  "toolsets": ["terminal", "file"],
  "metadata": {
    "client": "hermes-webui",
    "client_run_key": "idempotency-key-from-client"
  }
}
```

Response:

```json
{
  "object": "hermes.run",
  "run_id": "run_...",
  "session_id": "session_...",
  "status": "queued",
  "events_url": "/v1/runs/run_.../events"
}
```

Requirements:

- `run_id` is allocated by Hermes.
- duplicate client retries should be idempotent when `client_run_key` is supplied;
- the run is discoverable by `run_id` and by `session_id` before the first event is consumed;
- session creation/attachment is Hermes-owned, not client-owned.

### Observe a run

```text
GET /v1/runs/{run_id}/events?cursor=<last_seen_event_id>
```

Requirements:

- returns events with `event_id > cursor` in order;
- if no cursor is supplied, starts at the current live tail unless `replay=all` is requested;
- supports `Last-Event-ID` for SSE clients;
- emits keepalives without advancing the cursor;
- closes cleanly after terminal events, but the event log remains replayable.

### Get run state

```text
GET /v1/runs/{run_id}
```

Returns the current run object, including terminal result/error and `last_event_id`.

### List/discover runs

```text
GET /v1/runs?session_id=<session_id>&status=active
```

Minimum filters:

- `session_id`
- `status=active|terminal|all`
- `profile`
- `workspace`

This is the reconnect primitive a workbench needs after refresh or restart.

### Cancel or interrupt a run

```text
POST /v1/runs/{run_id}/cancel
POST /v1/runs/{run_id}/interrupt
```

`cancel` is the user-facing hard stop. `interrupt` is reserved for softer control semantics where the agent may finish the current step or yield a partial response. The current `/stop` endpoint can remain as a compatibility alias while clients migrate.

### Queue or continue work

```text
POST /v1/runs/{run_id}/queue
```

Request:

```json
{
  "input": "follow-up instruction",
  "mode": "queue|continue|steer"
}
```

This API is needed for `/queue`, `/goal` continuation, background/BTW workflows, and WebUI steer controls. The runtime decides whether the input appends to a live run, creates a child run, or is rejected for the current lifecycle state.

### Respond to approval

```text
POST /v1/runs/{run_id}/approval
```

Request:

```json
{
  "approval_id": "optional explicit approval id",
  "choice": "once|session|always|deny",
  "resolve_all": false
}
```

Requirements:

- approval state is keyed by runtime-owned run/session identity;
- clients do not hold the authoritative approval queue;
- a successful response emits an `approval.responded` event.

### Respond to clarify

```text
POST /v1/runs/{run_id}/clarify
```

Request:

```json
{
  "clarify_id": "clarify_...",
  "response": "user supplied answer"
}
```

Requirements mirror approval: Hermes owns pending clarify state, response application, and the follow-up event.

## Event taxonomy v0

The v0 event set should cover the existing WebUI workbench contract without forcing WebUI to inspect private agent objects.

| Event | Purpose | Required payload |
|---|---|---|
| `run.queued` | run accepted | status, model/provider/profile/workspace |
| `run.started` | agent execution began | status |
| `message.delta` | assistant text token/delta | `delta` |
| `message.completed` | assistant message complete | `content` |
| `reasoning.available` | reasoning/progress text | `text`, optional `phase` |
| `tool.started` | tool call started | `tool`, `call_id`, redacted args/preview |
| `tool.updated` | long-running tool progress | `tool`, `call_id`, preview/progress |
| `tool.completed` | tool call finished | `tool`, `call_id`, duration, error flag, preview/result handle |
| `approval.request` | dangerous action awaiting user | approval id, command/action summary, choices |
| `approval.responded` | approval resolved | approval id, choice |
| `clarify.request` | agent needs user input | clarify id, prompt, options/schema if any |
| `clarify.responded` | clarify answered | clarify id |
| `usage.updated` | token/cost update | input/output/total tokens, cost if available |
| `title.updated` | session title suggestion/change | title |
| `run.status` | coarse lifecycle status change | status, active_controls |
| `run.completed` | terminal success | output, usage |
| `run.failed` | terminal failure | error code/message |
| `run.cancelled` | terminal cancellation | reason |

Event payloads may grow, but clients should be able to implement a competent workbench with only this set.

## Capability discovery

`GET /v1/capabilities` should advertise which runtime controls are safe and implemented:

```json
{
  "object": "hermes.api_server.capabilities",
  "runtime_api": {
    "version": "0",
    "event_replay": true,
    "run_discovery": true,
    "controls": {
      "cancel": true,
      "interrupt": true,
      "queue": true,
      "steer": false,
      "approval": true,
      "clarify": true
    },
    "command_capabilities": {
      "goal": "supported",
      "model": "supported",
      "theme": "client-local"
    }
  }
}
```

This prevents UI clients from guessing which Hermes-native slash/control behaviors can be delegated.

## WebUI gap matrix

The table below maps the WebUI-owned primitives called out in `nesquena/hermes-webui#1925` to Hermes Runtime API responsibilities.

| Current WebUI primitive | Runtime API owner | Notes |
|---|---|---|
| `STREAMS` / `STREAMS_LOCK` | Run event log + observe API | WebUI may keep transient browser SSE connections, but not authoritative run queues. |
| `CANCEL_FLAGS` | `cancel` / `interrupt` control endpoint | Cancellation truth lives on the runtime run. |
| `AGENT_INSTANCES` | Hermes run executor | WebUI should not construct or cache `AIAgent` for normal chat. |
| partial text buffers | Event replay + message completion events | Client may buffer for rendering only. |
| reasoning/tool buffers | Event log | Client may render cards from replayed events. |
| approval callbacks/queues | Runtime approval state + response endpoint | Client renders pending approvals and submits choices. |
| clarify callbacks/queues | Runtime clarify state + response endpoint | Missing in current `/v1/runs`; should be an upstream gap. |
| session -> active run mapping | `GET /v1/runs?session_id=...&status=active` | Required for browser reconnect. |
| reconnect/replay | cursor event log + terminal run state | Required before WebUI can survive restart/refresh cleanly. |
| slash-command parity | command capability metadata + runtime command endpoints | WebUI-local commands remain local; Hermes behavior delegates upstream. |
| provider/model/tool routing | run request + run state fields | Runtime resolves and reports actual provider/model/toolsets used. |

## First milestone

The first meaningful acceptance test is not “basic chat streams through `/v1/runs`.” It is:

1. start a non-trivial run from an external client through the Hermes-owned runtime API;
2. disconnect or restart only the client/WebUI process mid-run;
3. rediscover the active or completed run by `session_id`;
4. reconnect with `cursor` / `Last-Event-ID`;
5. replay/catch up ordered events;
6. cancel still works if the run is active;
7. no client-side adapter owns an `AIAgent` instance, local cancellation truth, or authoritative approval/clarify queue.

If that milestone works, Hermes is becoming the execution source of truth. If it only works by rebuilding a private runtime inside a UI adapter, the architecture has merely renamed the old coupling.

## Implementation ladder

1. **Spec and tests for the contract.** Add fixture-level tests for event ordering, cursor replay, terminal state, and capability discovery.
2. **Durable event log.** Persist run events in Hermes state storage with a per-run `event_id` cursor.
3. **Run discovery.** Add list/filter APIs for active and terminal runs by session/profile/workspace.
4. **Reconnect semantics.** Implement `Last-Event-ID` / cursor replay and terminal catch-up.
5. **Control plane.** Fill gaps for cancel/interrupt, queue/continue/steer, approval, and clarify.
6. **Command capability metadata.** Advertise which slash/control commands clients can safely delegate.
7. **Client adapters.** Migrate clients such as WebUI behind feature flags, starting with new runs and keeping legacy execution fallback until parity is proven.
8. **Retire runtime surrogates.** Remove UI-owned execution/cancellation/approval state only after the restart/reattach milestone and parity tests pass.

## Non-goals for v0

- horizontal scaling;
- Redis/Kafka/NATS requirements;
- changing frontend presentation contracts all at once;
- exposing unsafe gateway-only commands blindly;
- requiring every client to implement every control surface on day one.

The v0 goal is a small, durable, observable run contract that lets clients be rich workbenches without becoming second runtimes.

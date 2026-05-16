# Voice + Chat Panel for the Web Dashboard

> Phase 4 of the voice-and-chat work. Phases 1–3 (Supertonic provider,
> `/api/tts/speak`, `/api/voice/transcribe`, dashboard speak/mic buttons)
> are already shipped. This doc covers the agent-run streaming endpoint
> and the in-dashboard `ChatPage`.

## Goal

A first-class chat surface inside the web dashboard that drives the
existing `AIAgent` (`run_agent.py`) and streams responses back to the
browser. Voice in (via `<MicButton>`) and voice out (via `<SpeakButton>`
per message) are wired into the same surface.

## Constraints we cannot violate

1. **Prompt caching must not break** — `AGENTS.md` §"Important Policies".
   Toolsets cannot change mid-conversation. Memories cannot be reloaded
   mid-conversation. Only context compression may alter past context.
2. **Session token auth** — `/api/*` (except a small public allowlist)
   requires the bearer token injected into `index.html`. Streaming endpoint
   must accept the same header.
3. **No background polling tax** — the chat panel must close its
   connection when the user navigates away or the agent finishes; no
   long-lived sockets per tab.
4. **Tool approval semantics must survive the boundary** — the agent
   can request approval for shell commands; the browser must be able to
   accept/reject and the agent loop must block on that answer.

## Backend: streaming endpoint

### Transport choice — SSE

Use **Server-Sent Events** over WebSocket. Justification:

- Agent → browser is the dominant direction (text deltas, tool events).
- The few browser → agent messages we need (approval responses,
  cancellation) can be plain POSTs against a session-scoped endpoint.
- SSE is one-way HTTP, plays well with FastAPI's `StreamingResponse`,
  doesn't need a separate protocol upgrade, and survives the existing
  bearer-token auth middleware unchanged.
- Reconnect-by-`Last-Event-ID` and per-event types are native to SSE.

### Endpoint shapes

```
POST  /api/chat/sessions               → { session_id }
GET   /api/chat/sessions/{id}/stream   → SSE event stream (one per turn)
POST  /api/chat/sessions/{id}/send     { text } → 202 (kicks off a turn)
POST  /api/chat/sessions/{id}/approve  { call_id, decision } → 202
POST  /api/chat/sessions/{id}/cancel   → 202
GET   /api/chat/sessions/{id}/messages → full history (for resume)
```

A turn is the unit: `send` enqueues a user message; `stream` delivers
the agent's response as events until `done` or `error`.

### SSE event types

```
event: turn-start         data: { call_id }
event: text-delta         data: { delta: "..." }
event: tool-call-start    data: { call_id, tool, args_summary }
event: tool-call-result   data: { call_id, ok, summary }
event: approval-request   data: { call_id, command, description }
event: clarify-request    data: { call_id, question, choices }
event: status             data: { kind: "thinking" | "compressing" | ... }
event: turn-end           data: { final_text }
event: error              data: { detail }
```

Each event is small and structured. `text-delta` is the hot path; everything
else is rare and informational.

### Reusing AIAgent

`AIAgent.run_conversation(stream_callback=...)` already exists
(`run_agent.py:8290`) and emits text deltas. We feed it a callback that
pushes `text-delta` events onto an `asyncio.Queue` consumed by the SSE
generator. For tool events we need either:

- **(a)** A new optional callback on `AIAgent` (`tool_event_callback`)
  invoked from `handle_function_call`, OR
- **(b)** Reading from the session DB after-the-fact and emitting
  events at known points.

(a) is clean but touches the agent. (b) is messier and lossy. We'll
add `tool_event_callback` as a no-op default — non-breaking everywhere.

For **approval** and **clarify**, we pass web-bound callback functions
into the `AIAgent` constructor (the same hooks the CLI uses — see
`hermes_cli/callbacks.py:18,186`). The web versions:

```python
def web_approval_callback(call_id, command, description):
    queue.put({"event":"approval-request","call_id":call_id, ...})
    return wait_for_response(call_id, timeout=300)  # blocks
```

The agent loop already blocks on these, so the SSE generator simply
keeps pumping until the browser POSTs to `/approve` and the wait
resolves.

### Session lifecycle

- `POST /api/chat/sessions` creates a `ChatSession` in-process that
  owns: an `AIAgent` instance, a conversation history list, an
  `asyncio.Queue` for outbound events, and pending-approval futures.
- `AIAgent` is constructed **once** and reused across turns (preserves
  prompt cache; see Constraint #1). Toolsets are frozen at creation.
- Conversation messages are persisted to the existing `SessionDB` so
  `SessionsPage` continues to show them and `--resume` works from CLI.
- A `ChatSession` evicts itself from the in-process registry after
  N minutes of inactivity (or on explicit DELETE). The persisted
  history survives in `SessionDB` and can be reloaded into a new
  in-process session via "resume".
- Multi-tab safety: each browser tab gets its own `session_id`; no
  sharing. (Future: a "join existing session" mode.)

### Cancellation

`/cancel` sets a flag the agent loop checks at every iteration
boundary (we already have `_should_cancel()` in `AIAgent`? — TBD,
see Open Questions). If not present, we add a `cancel_event:
threading.Event` and check it where `iteration_budget` is checked.

## Frontend: `ChatPage`

### New files

```
web/src/pages/ChatPage.tsx              # main page
web/src/components/chat/
  ChatComposer.tsx                      # input box + send + mic
  MessageList.tsx                       # virtualized message list
  Message.tsx                           # bubble + speak button per assistant turn
  ToolCallEvent.tsx                     # collapsible tool-call card
  ApprovalDialog.tsx                    # blocking approval modal
web/src/lib/chat.ts                     # SSE client + chat API wrappers
```

### `lib/chat.ts` sketch

```ts
export class ChatClient {
  constructor(sessionId: string, token: string) { ... }
  async send(text: string): Promise<void> { ... }      // POST /send
  async approve(callId, ok): Promise<void> { ... }     // POST /approve
  async cancel(): Promise<void> { ... }                // POST /cancel
  onEvent(cb: (e: ChatEvent) => void): () => void {
    // Opens EventSource to /stream and dispatches typed events.
  }
}
```

`EventSource` doesn't support custom auth headers, so the bearer token
goes on the URL as a query param (`?token=...`) — backend accepts it on
this endpoint only. Alternatively use `fetch()` with
`response.body.getReader()` and parse SSE manually; that's strictly
better and lets us keep header-based auth. **Recommended: fetch+reader,
not EventSource.**

### Composer

- Textarea + send button + `<MicButton>` (already exists).
- Mic transcript replaces the composer's text (or appends, configurable).
- Enter sends; Shift+Enter newline.

### Message rendering

- User messages: simple bubbles.
- Assistant messages: Markdown via existing `Markdown` component +
  `<SpeakButton text={message.text}>` so any reply can be played.
- Tool-call events: collapsible card. Status shown live (`...`,
  `✓ done`, `✗ error`).
- Approval requests: modal blocking the composer; "Allow once / Always
  allow / Deny" → POST `/approve`.

### Navigation

Add a "Chat" entry to `App.tsx` nav, before Sessions. Default landing
page becomes Chat.

## Decisions (locked in)

1. **Single persistent thread**. One conversation per browser. Sessions
   page continues to show full history; no separate thread sidebar in
   the ChatPage itself.
2. **Reattach on reload**. Store `session_id` in `localStorage` and try
   to resume on page load. If the backend has evicted the session,
   fall back to creating a fresh one; replay persisted history from
   `SessionDB` so the user doesn't lose conversational context.
3. **TTS-by-default = off**. Manual click on a per-message
   `<SpeakButton>`. Header may grow a "voice mode" toggle later.
4. **Always require approval modal** for any tool call that the
   existing approval machinery flags as dangerous. Browser must not
   reuse the CLI's yolo flag — too easy to forget the dashboard is
   open while doing something else.
5. **Toolset scope** = CLI parity, gated by approval modal. No new
   web-safe subset.
6. **Long-running background tool calls** = out of scope for v1.
   `terminal(background=true)` should be either disallowed in the web
   chat (return an error) or treated as foreground for v1. Revisit
   when the chat panel has matured.

## Order of operations (proposed)

1. Add `tool_event_callback` optional hook to `AIAgent`. No-op default.
   Verify zero existing tests break.
2. Build `ChatSession` registry + the six endpoints. Unit-test the
   SSE generator with a stubbed agent.
3. Build `web/src/lib/chat.ts` (SSE consumer over fetch+reader).
4. Build `ChatPage` + composer + message list. Smoke-test against a
   live local agent. Wire mic + speak buttons.
5. Add approval modal. Verify a `terminal` call that triggers approval
   round-trips cleanly.
6. Add cancellation. Verify Ctrl-C-equivalent stops the agent mid-tool.
7. Add navigation entry, polish, ship.

**Estimated effort**: 1–2 days for steps 1–4, another day for 5–7
(approval + cancellation tend to surface edge cases). Total ~3 days
end-to-end, assuming no surprises in the agent-loop reentrance.

## Things explicitly out of scope for v1

- Multi-user / multi-device sync of the same chat.
- Always-on listening (push-to-talk only).
- Streaming TTS (synthesize as deltas arrive) — start with
  per-message playback.
- Voice activity detection / barge-in.
- Persisting partial assistant turns on disconnect (we'll discard and
  let the user retry).

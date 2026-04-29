# HookBus Light for Hermes

Publishes Hermes lifecycle events to HookBus Light, the local event bus for AI agent runtimes. Once enabled, HookBus Light subscribers such as CRE-AgentProtect Light can observe or gate Hermes tool and LLM activity.

## What it does

- Emits `UserPromptSubmit` from gateway messages.
- Emits `PreLLMCall` before LLM API calls; subscribers can block the call.
- Emits `PostLLMCall` with model, token usage, response content, and reasoning content when available.
- Emits `PreToolUse` before tool calls; subscribers can block the tool call.
- Emits `PostToolUse` after tool calls for audit and observation.

## Enable

Install and start HookBus Light separately, then enable this bundled plugin:

```bash
hermes plugins enable hookbus-light
export HOOKBUS_URL=http://localhost:18800/event
export HOOKBUS_TOKEN=<token from HookBus Light>
```

Optional:

```bash
export HOOKBUS_FAIL_MODE=open   # default is closed
export HOOKBUS_SOURCE=hermes-agent
```

`HOOKBUS_FAIL_MODE=closed` denies pre-LLM and pre-tool events when HookBus Light is unreachable. Use `open` for local experiments where Hermes should continue if the bus is offline.

## Security

Prompt text and tool inputs are included in event envelopes so local subscribers can make policy decisions. Point `HOOKBUS_URL` only at a bus you trust for that data.

## Verify

```bash
hermes chat -q "Reply with exactly: PING"
curl -s -H "Authorization: Bearer $HOOKBUS_TOKEN" http://localhost:18800/api/events
```

You should see events with `source=hermes-agent`.

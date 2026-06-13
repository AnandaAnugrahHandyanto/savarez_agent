---
sidebar_position: 7
title: "Gateway Internals"
description: "How the messaging gateway boots, authorizes users, routes sessions, and delivers messages"
---

# Gateway Internals

The messaging gateway is the long-running process that connects Hermes to 20+ external messaging platforms through a unified architecture.

## Key Files

| File | Purpose |
|------|---------|
| `gateway/run.py` | `GatewayRunner` — main loop, slash commands, message dispatch (large file; check git for current LOC) |
| `gateway/session.py` | `SessionStore` — conversation persistence and session key construction |
| `gateway/delivery.py` | Outbound message delivery to target platforms/channels |
| `gateway/voice_sessions.py` | Platform-neutral live voice session lifecycle, provider selection, interruption, and guardrails |
| `gateway/pairing.py` | DM pairing flow for user authorization |
| `gateway/channel_directory.py` | Maps chat IDs to human-readable names for cron delivery |
| `gateway/hooks.py` | Hook discovery, loading, and lifecycle event dispatch |
| `gateway/mirror.py` | Cross-session message mirroring for `send_message` |
| `gateway/status.py` | Token lock management for profile-scoped gateway instances |
| `gateway/builtin_hooks/` | Extension point for always-registered hooks (none shipped) |
| `gateway/platforms/` | Platform adapters (one per messaging platform) |

## Architecture Overview

```text
┌─────────────────────────────────────────────────┐
│                  GatewayRunner                  │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Telegram │  │ Discord  │  │  Slack   │       │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │             │             │             │
│       └─────────────┼─────────────┘             │
│                     ▼                           │
│              _handle_message()                  │
│                     │                           │
│         ┌───────────┼───────────┐               │
│         ▼           ▼           ▼               │
│  Slash command   AIAgent    Queue/BG            │
│    dispatch      creation   sessions            │
│                     │                           │
│                     ▼                           │
│                 SessionStore                    │
│              (SQLite persistence)               │
└───────┴─────────────┴─────────────┴─────────────┘
```

## Message Flow

When a message arrives from any platform:

1. **Platform adapter** receives raw event, normalizes it into a `MessageEvent`
2. **Base adapter** checks active session guard:
   - If agent is running for this session → queue message, set interrupt event
   - If `/approve`, `/deny`, `/stop` → bypass guard (dispatched inline)
3. **GatewayRunner._handle_message()** receives the event:
   - Resolve session key via `_session_key_for_source()` (format: `agent:main:{platform}:{chat_type}:{chat_id}`)
   - Check authorization (see Authorization below)
   - Check if it's a slash command → dispatch to command handler
   - Check if agent is already running → intercept commands like `/stop`, `/status`
   - Otherwise → create `AIAgent` instance and run conversation
4. **Response** is sent back through the platform adapter

### Session Key Format

Session keys encode the full routing context:

```
agent:main:{platform}:{chat_type}:{chat_id}
```

For example: `agent:main:telegram:private:123456789`

Thread-aware platforms (Telegram forum topics, Discord threads, Slack threads) may include thread IDs in the chat_id portion. **Never construct session keys manually** — always use `build_session_key()` from `gateway/session.py`.

### Two-Level Message Guard

When an agent is actively running, incoming messages pass through two sequential guards:

1. **Level 1 — Base adapter** (`gateway/platforms/base.py`): Checks `_active_sessions`. If the session is active, queues the message in `_pending_messages` and sets an interrupt event. This catches messages *before* they reach the gateway runner.

2. **Level 2 — Gateway runner** (`gateway/run.py`): Checks `_running_agents`. Intercepts specific commands (`/stop`, `/new`, `/queue`, `/status`, `/approve`, `/deny`) and routes them appropriately. Everything else triggers `running_agent.interrupt()`.

Commands that must reach the runner while the agent is blocked (like `/approve`) are dispatched **inline** via `await self._message_handler(event)` — they bypass the background task system to avoid race conditions.

## Authorization

The gateway uses a multi-layer authorization check, evaluated in order:

1. **Per-platform allow-all flag** (e.g., `TELEGRAM_ALLOW_ALL_USERS`) — if set, all users on that platform are authorized
2. **Platform allowlist** (e.g., `TELEGRAM_ALLOWED_USERS`) — comma-separated user IDs
3. **DM pairing** — authenticated users can pair new users via a pairing code
4. **Global allow-all** (`GATEWAY_ALLOW_ALL_USERS`) — if set, all users across all platforms are authorized
5. **Default: deny** — unauthorized users are rejected

### DM Pairing Flow

```text
Admin: /pair
Gateway: "Pairing code: ABC123. Share with the user."
New user: ABC123
Gateway: "Paired! You're now authorized."
```

Pairing state is persisted in `gateway/pairing.py` and survives restarts.

## Slash Command Dispatch

All slash commands in the gateway flow through the same resolution pipeline:

1. `resolve_command()` from `hermes_cli/commands.py` maps input to canonical name (handles aliases, prefix matching)
2. The canonical name is checked against `GATEWAY_KNOWN_COMMANDS`
3. Handler in `_handle_message()` dispatches based on canonical name
4. Some commands are gated on config (`gateway_config_gate` on `CommandDef`)

### Running-Agent Guard

Commands that must NOT execute while the agent is processing are rejected early:

```python
if _quick_key in self._running_agents:
    if canonical == "model":
        return "⏳ Agent is running — wait for it to finish or /stop first."
```

Bypass commands (`/stop`, `/new`, `/approve`, `/deny`, `/queue`, `/status`) have special handling.

## Config Sources

The gateway reads configuration from multiple sources:

| Source | What it provides |
|--------|-----------------|
| `~/.hermes/.env` | API keys, bot tokens, platform credentials |
| `~/.hermes/config.yaml` | Model settings, tool configuration, display options |
| Environment variables | Override any of the above |

Unlike the CLI (which uses `load_cli_config()` with hardcoded defaults), the gateway reads `config.yaml` directly via YAML loader. This means config keys that exist in the CLI's defaults dict but not in the user's config file may behave differently between CLI and gateway.

## Platform Adapters

Each messaging platform has an adapter in `gateway/platforms/`:

```text
gateway/platforms/
├── base.py              # BaseAdapter — shared logic for all platforms
├── telegram.py          # Telegram Bot API (long polling or webhook)
├── discord.py           # Discord bot via discord.py
├── slack.py             # Slack Socket Mode
├── whatsapp.py          # WhatsApp Business Cloud API
├── signal.py            # Signal via signal-cli REST API
├── matrix.py            # Matrix via mautrix (optional E2EE)
├── mattermost.py        # Mattermost WebSocket API
├── email.py             # Email via IMAP/SMTP
├── sms.py               # SMS via Twilio
├── dingtalk.py          # DingTalk WebSocket
├── feishu.py            # Feishu/Lark WebSocket or webhook
├── wecom.py             # WeCom (WeChat Work) callback
├── weixin.py            # Weixin (personal WeChat) via iLink Bot API
├── bluebubbles.py       # Apple iMessage via BlueBubbles macOS server
├── qqbot/               # QQ Bot (Tencent QQ) via Official API v2 (sub-package: adapter.py, crypto.py, keyboards.py, …)
├── yuanbao.py           # Yuanbao (Tencent) DM/group adapter
├── feishu_comment.py    # Feishu document/drive comment-reply handler
├── msgraph_webhook.py   # Microsoft Graph change-notification webhook (Teams, Outlook, etc.)
├── webhook.py           # Inbound/outbound webhook adapter
├── api_server.py        # REST API server adapter
└── homeassistant.py     # Home Assistant conversation integration
```

Adapters implement a common interface:
- `connect()` / `disconnect()` — lifecycle management
- `send_message()` — outbound message delivery
- `on_message()` — inbound message normalization → `MessageEvent`

## Live Voice Sessions

Discord `/voice live` is wired as a gateway-managed live voice session rather than a separate agent loop. The Discord adapter still owns joining/leaving voice channels, decrypting RTP, decoding Discord-native 48 kHz stereo PCM frames, and playing TTS audio. `GatewayRunner` owns the `VoiceSessionManager`, authorization, config loading from `voice.live`, and cleanup on `/voice leave`, timeout, disconnect, or guardrail failure.

The MVP provider stack is intentionally conservative:

- `pipeline` is the default provider and reuses the existing STT → Hermes text agent → TTS path.
- `openai_realtime` is a readiness gate: it checks for `OPENAI_API_KEY` or `VOICE_TOOLS_OPENAI_KEY`, marks the session degraded, and falls back to `pipeline` until the websocket event adapter is implemented.
- Raw audio is not persisted by default; decoded frames are used for state, barge-in, and budget accounting.

Important contracts for future realtime providers:

1. Keep provider-specific websocket/event code behind `RealtimeVoiceProvider`; do not put provider protocol details in the Discord adapter.
2. Preserve `VoiceSessionManager` as the single owner of session conflict checks, auth checks, duration/input/event guardrails, and session snapshots.
3. Barge-in must call the runner playback stopper before provider cancellation so Discord audio stops even if a provider call hangs or fails.
4. Network/provider failures should close or degrade the live session with a user-visible reason rather than leaving the bot connected with a dead audio path.
5. Do not persist raw audio unless `voice.live.allow_raw_audio_persistence` is explicitly enabled by config and documented for the provider.

### Token Locks

Adapters that connect with unique credentials call `acquire_scoped_lock()` in `connect()` and `release_scoped_lock()` in `disconnect()`. This prevents two profiles from using the same bot token simultaneously.

## Delivery Path

Outgoing deliveries (`gateway/delivery.py`) handle:

- **Direct reply** — send response back to the originating chat
- **Home channel delivery** — route cron job outputs and background results to a configured home channel
- **Explicit target delivery** — `send_message` tool specifying `telegram:-1001234567890`, or the [`hermes send` CLI](/guides/pipe-script-output) wrapping the same tool for shell scripts
- **Cross-platform delivery** — deliver to a different platform than the originating message

Cron job deliveries are NOT mirrored into gateway session history — they live in their own cron session only. This is a deliberate design choice to avoid message alternation violations.

## Hooks

Gateway hooks are Python modules that respond to lifecycle events:

### Gateway Hook Events

| Event | When fired |
|-------|-----------|
| `gateway:startup` | Gateway process starts |
| `session:start` | New conversation session begins |
| `session:end` | Session completes or times out |
| `session:reset` | User resets session with `/new` |
| `agent:start` | Agent begins processing a message |
| `agent:step` | Agent completes one tool-calling iteration |
| `agent:end` | Agent finishes and returns response |
| `command:*` | Any slash command is executed |

Hooks are discovered from `gateway/builtin_hooks/` (an extension point — currently empty in the shipped distribution; `_register_builtin_hooks()` is a no-op stub) and `~/.hermes/hooks/` (user-installed). Each hook is a directory with a `HOOK.yaml` manifest and `handler.py`.

## Memory Provider Integration

When a memory provider plugin (e.g., Honcho) is enabled:

1. Gateway creates an `AIAgent` per message with the session ID
2. The `MemoryManager` initializes the provider with the session context
3. Provider tools (e.g., `honcho_profile`, `viking_search`) are routed through:

```text
AIAgent._invoke_tool()
  → self._memory_manager.handle_tool_call(name, args)
    → provider.handle_tool_call(name, args)
```

4. On session end/reset, `on_session_end()` fires for cleanup and final data flush

### Memory Flush Lifecycle

When a session is reset, resumed, or expires:
1. Built-in memories are flushed to disk
2. Memory provider's `on_session_end()` hook fires
3. A temporary `AIAgent` runs a memory-only conversation turn
4. Context is then discarded or archived

## Background Maintenance

The gateway runs periodic maintenance alongside message handling:

- **Cron ticking** — checks job schedules and fires due jobs
- **Session expiry** — cleans up abandoned sessions after timeout
- **Memory flush** — proactively flushes memory before session expiry
- **Cache refresh** — refreshes model lists and provider status

## Process Management

The gateway runs as a long-lived process, managed via:

- `hermes gateway start` / `hermes gateway stop` — manual control
- `systemctl` (Linux) or `launchctl` (macOS) — service management
- PID file at `~/.hermes/gateway.pid` — profile-scoped process tracking

**Profile-scoped vs global**: `start_gateway()` uses profile-scoped PID files. `hermes gateway stop` stops only the current profile's gateway. `hermes gateway stop --all` uses global `ps aux` scanning to kill all gateway processes (used during updates).

## Related Docs

- [Session Storage](./session-storage.md)
- [Cron Internals](./cron-internals.md)
- [ACP Internals](./acp-internals.md)
- [Agent Loop Internals](./agent-loop.md)
- [Messaging Gateway (User Guide)](/user-guide/messaging)

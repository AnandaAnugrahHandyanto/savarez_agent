---
name: hypura-channel-readiness
description: Diagnose LINE and Telegram credential readiness versus live roundtrip readiness through Hypura Harness without exposing tokens or raw routing ids.
category: automation, channels, diagnostics
version: 1.0.0
user-invocable: false
---

# Hypura Channel Readiness

Use this skill when an agent needs to decide whether LINE or Telegram is ready
for a real live proof. The readiness check is diagnostic only: it does not send
messages, does not print tokens, and does not print raw user, group, room, or
chat ids.

## Tool

```text
hypura_harness_channel_readiness({})
```

The tool calls `GET /channels/readiness` on the Hypura daemon. It inspects the
active OpenClaw config and returns redacted facts:

- LINE credential presence: channel access token and channel secret.
- Telegram credential presence: bot token.
- LINE live target candidate counts: direct users, groups, and rooms.
- Telegram live target candidate counts: direct chats and group chats.
- Target candidates from the local channel `allowFrom` store, when present.
- Structured session-route target candidates from prior inbound activity.
- Recent Telegram sent-message history candidates, when present.
- `liveRoundtripReady` booleans for each channel.
- `needs` entries that explain the missing next input.

## Operating rules

- Treat routing ids as private. Report counts, shape, and readiness state unless
  the user explicitly needs the raw id.
- Do not treat credential readiness as a live roundtrip. LINE still needs a real
  `userId`, `groupId`, or `roomId`; Telegram still needs a real chat id.
- If a channel has credentials but no live target candidate, ask the operator to
  send one inbound message to the configured bot/webhook.
- After the inbound message exists, use the channel skill for the final
  roundtrip proof: `line-channel` for LINE and `telegram-channel` for Telegram.

## Interpreting results

- `success=false` with `config_not_found`: start from OpenClaw config selection.
- `success=false` with `config_parse_failed`: fix the local config before
  blaming channel runtime.
- `liveRoundtripReady.line=false` with credentials present: LINE setup may be
  correct, but a live recipient still has not been discovered or configured.
- `liveRoundtripReady.telegram=false` with credentials present: Telegram setup
  may be correct, but a live chat target still has not been discovered or
  configured.

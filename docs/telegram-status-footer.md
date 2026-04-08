# Telegram DM Status Footer

This document describes the Telegram DM status footer added to Hermes gateway responses.

## Goal

Surface lightweight runtime context directly inside Telegram private-chat replies so the user can see:

- which model answered
- which reasoning effort level is active
- how much context the current request used relative to the model's context window

The feature is intentionally narrow. It is designed for Telegram DMs first, not for every platform or chat type.

## User-facing format

The footer is appended as a compact three-line block:

```text
────────────
🧠 gpt-5.4 · 💨 high
📊 45k / 1050k · 4%
```

Meaning:

- `🧠` — resolved model label
- `💨` — reasoning effort label (`low`, `medium`, `high`, `default`, or `none`)
- `📊` — current request context tokens vs. model context window, plus percent used

## Scope

The footer is appended only when all of the following are true:

1. the destination platform is Telegram
2. the chat type is DM
3. the message has non-empty text
4. the message does not already contain the footer separator

It is intentionally skipped for:

- Telegram group chats
- non-Telegram platforms
- empty responses
- messages that already contain a footer block

## Data sources

### Model label

The footer uses the resolved runtime model from the active agent instance.

### Reasoning label

The footer uses the gateway reasoning configuration and normalizes it for display:

- disabled reasoning => `none`
- missing/empty reasoning => `default`
- otherwise the configured effort string is displayed as-is

### Current token count

The preferred source is:

- `agent.context_compressor.last_prompt_tokens`

This best represents the actual prompt size sent on the current request.

If that value is unavailable, the footer falls back to:

- `result["total_tokens"]`

### Context window

The footer uses `agent.model_metadata.get_model_context_length(...)` to resolve the best-known context limit for the active provider/model combination.

## Integration points

### `gateway/telegram_status_footer.py`

This file owns the presentation and append rules:

- `build_telegram_status_footer(...)`
- `maybe_append_telegram_status_footer(...)`

Responsibilities:

- format token counts into compact `k` labels
- compute the usage percentage
- normalize reasoning labels
- guard Telegram-only / DM-only behavior
- avoid duplicate footer insertion

### `gateway/run.py`

The main gateway runner resolves the values needed for the footer:

- display reasoning label
- model context window
- current request token count

For non-streaming responses it appends the footer to the final response before delivery.

For streaming responses it computes a final suffix and passes that suffix to the stream consumer so the footer appears on the final edit rather than as a duplicate follow-up message.

### `gateway/stream_consumer.py`

Streaming delivery now supports a final suffix via:

- `set_final_suffix(...)`

On stream completion, the suffix is appended only to the final edit/send. This keeps the streamed reply and the footer in one message.

## Design decisions

### Telegram DM only

The first version is intentionally limited to Telegram DMs. Group chats and other platforms were left untouched to avoid adding unsolicited metadata where it may be noisy or undesirable.

### Use prompt-size context pressure, not cumulative session spend

The footer shows the size of the current request context, not total tokens ever spent in the session. This makes the percentage line useful for real-time context pressure monitoring.

### Keep the format static and readable

The current formatting uses rounded `k` values (`45k`, `1050k`) and a simple separator line. The output is optimized for fast scanning in Telegram bubbles rather than for exact accounting.

## Tests

The change is covered by targeted tests:

- `tests/gateway/test_telegram_status_footer.py`
- `tests/gateway/test_stream_consumer.py`
- `tests/gateway/test_update_streaming.py`

Coverage includes:

- footer formatting
- missing reasoning fallback
- Telegram DM-only gating
- duplicate footer suppression
- final streamed message suffix behavior

## Known limitations

- The context line is a best-effort runtime display, not a billing report.
- The footer currently has no user-facing on/off toggle.
- The feature is not yet generalized for Discord, Slack, WhatsApp, or Telegram groups.
- Some local test environments can affect auxiliary-client tests if they read a real `~/.hermes/config.yaml`; isolated HOME runs are safer for local verification when debugging unrelated failures.

## Future extensions

Possible follow-ups if desired:

- add a config toggle for enabling/disabling the footer
- support more compact context-window formatting (for example `1.05M`)
- optionally extend to additional platforms
- expose more runtime metadata only when explicitly enabled

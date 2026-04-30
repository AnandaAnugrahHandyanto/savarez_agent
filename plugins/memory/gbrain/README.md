# GBrain Memory Provider

Hermes MemoryProvider plugin for routing durable knowledge through the local `gbrain` CLI.

## Setup

```bash
hermes config set memory.provider gbrain
# restart the active Hermes gateway/session after changing memory.provider
```

`gbrain` must already be on PATH and initialized. This provider does not require a new API key.

## Config

Run `hermes memory setup` and select `gbrain`, or set optional config under `plugins.gbrain` in `$HERMES_HOME/config.yaml`:

```yaml
plugins:
  gbrain:
    brain_slug_prefix: agents/hermes/memory
    auto_sync_turns: "false"
    capture_on_pre_compress: "false"
    max_results: "5"
```

## Tools

- `gbrain_search` — keyword search via `gbrain search --json`.
- `gbrain_query` — hybrid semantic query via `gbrain query --json`.
- `gbrain_get` — read a page by slug via `gbrain get`.
- `gbrain_remember` — write a durable markdown page via `gbrain put`.

## Lifecycle hooks

- `prefetch` / `queue_prefetch` recall task-relevant GBrain context for the next turn.
- `on_memory_write` mirrors explicit built-in Hermes memory writes into GBrain.
- `on_pre_compress` optionally captures important context before Hermes compression discards it (`capture_on_pre_compress: "true"`).
- `sync_turn` is opt-in with `auto_sync_turns: "true"`; default off to avoid storing routine chat noise.

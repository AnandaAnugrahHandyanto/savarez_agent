# SIMPLICIO_PROMPT

SIMPLICIO_PROMPT is an opt-in Hermes plugin that injects the SIMPLICIO_PROMPT V2 execution overlay into every main-agent turn through the `pre_llm_call` hook.

## Enable

Environment flag:

```bash
SIMPLICIO_PROMPT=true hermes chat
```

Config flag:

```yaml
simplicio_prompt:
  enabled: true
```

The plugin also activates when explicitly enabled through the normal plugin allow-list:

```bash
hermes plugins enable SIMPLICIO_PROMPT
```

`plugins.disabled: [SIMPLICIO_PROMPT]` still wins and prevents loading.

## What It Adds

| Item | Behaviour |
|---|---|
| Automatic prompt pass-through | Every main-agent turn receives the overlay before the model call; the user does not need to type "Implement". |
| Tuple-space planning | Requests are framed as root tuple plus explicit work graph, lane, authority, receipts, and source pointers. |
| Massive-agent abstraction | `batch_spawn(depth, branching, compression_threshold)` is used as a summarized hierarchy for 1,000,000+ subagents without enumerating them. |
| Safe speed policy | Cache by receipt/input hash, batch small tasks, compress context, route deterministic work to local tools, and use speculative work only when idempotent. |
| Provider safety | Backoff with jitter and circuit breakers are required; provider limits and terms must be respected. |
| Stable reporting | The default output contract keeps tuple-space state, active agents, totals, next yool, and partial result visible. |

The plugin is intentionally lightweight. It does not call external services and does not bypass provider throttles. Its runtime work is a local boolean check plus a static context string returned from `pre_llm_call` when enabled.

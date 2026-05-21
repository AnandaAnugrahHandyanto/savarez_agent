# SIMPLICIO_PROMPT

SIMPLICIO_PROMPT is an opt-in Hermes plugin that injects the SIMPLICIO_PROMPT V2 execution overlay into every main-agent turn through the `pre_llm_call` hook.

Canonical reference: [wesleysimplicio/simplicio-prompt](https://github.com/wesleysimplicio/simplicio-prompt).

![YOOL V2 Safe-Speed Runtime reference infographic](../../website/static/img/simplicio-prompt/yool-v2-safe-speed-infographic-en.png)

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

## Canonical V2 Reference Data

The canonical `simplicio-prompt` README reports these local V2 benchmark highlights for the safe-speed runtime:

| Area | Reported V2 result |
|---|---:|
| Scale representation | `2,833.75x` faster than normal instruction flow |
| Active execution | `26.93x` faster than normal sequential execution |
| Receipt/input cache | `4x` fewer provider calls, a `75%` reduction |
| Small-task batching | `32x` fewer small-task calls, a `96.88%` reduction |
| Circuit breaker | `64x` fewer failure attempts, a `98.44%` reduction |
| Token economy | `76.32%` estimated savings through context compression |

Those numbers are reference data for the V2 execution policy. This Hermes plugin injects that policy automatically; it does not claim to bypass hosted-provider latency, quotas, or rate limits.

## High-Throughput Reference Knobs

The canonical runtime documents these safe-speed environment settings for local tuple-space execution:

```bash
YOOL_TUPLE_LANE_CONCURRENCY=32
YOOL_TUPLE_MAX_LANE_CONCURRENCY=64
YOOL_TUPLE_CPU_QUOTA_PCT=95
YOOL_TUPLE_QUEUE_MAXSIZE=8192
YOOL_TUPLE_COMPRESSION_THRESHOLD=1024
YOOL_TUPLE_CACHE_MAX_ENTRIES=16384
YOOL_TUPLE_CACHE_TTL_S=3600
YOOL_TUPLE_API_MAX_RETRIES=3
YOOL_TUPLE_API_BACKOFF_BASE_MS=100
YOOL_TUPLE_API_BACKOFF_MAX_MS=5000
YOOL_TUPLE_CIRCUIT_FAILURE_THRESHOLD=5
YOOL_TUPLE_CIRCUIT_COOLDOWN_S=30
YOOL_TUPLE_BATCH_SMALL_TASK_SIZE=32
YOOL_TUPLE_CONTEXT_COMPRESSION_CHARS=6000
```

Hermes keeps these as model-visible execution guidance through the overlay. Provider-facing behavior must still respect configured Hermes limits and the provider's terms.

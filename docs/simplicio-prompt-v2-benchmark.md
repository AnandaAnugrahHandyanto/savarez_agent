# SIMPLICIO_PROMPT V2 Benchmark

![YOOL V2 Safe-Speed Runtime reference infographic](../website/static/img/simplicio-prompt/yool-v2-safe-speed-infographic-en.png)

This report compares three local message-preparation paths for the Hermes
SIMPLICIO_PROMPT plugin. It does not call a hosted model, so it does not claim
provider-side latency, quality, or tool-success improvements. It measures the
part this PR changes directly: pre-LLM prompt injection and token footprint.

Command:

```bash
python scripts/benchmark_simplicio_prompt.py --iterations 10000
```

## Results

| Case | Median ms/build | p95 ms/build | Rough input tokens | Chars |
|---|---:|---:|---:|---:|
| normal_instruction | 0.000100 | 0.000200 | 28 | 112 |
| manual_v2_prompt | 0.000300 | 0.000700 | 329 | 1,318 |
| simplicio_prompt_plugin | 0.000300 | 0.000400 | 269 | 1,079 |

## Deltas

| Comparison | Result |
|---|---:|
| Plugin token savings vs manually pasted V2 prompt | 18.24% fewer rough input tokens |
| Plugin token overhead vs normal instruction | 860.71% more rough input tokens |
| Plugin local preprocessing overhead vs normal instruction | ~0.0002 ms median absolute delta |
| Extra model calls introduced by plugin | 0 |

## Interpretation

`normal_instruction` is the fastest and cheapest local path because it carries
no execution overlay. It also gives the model no tuple-space policy, no V2 safe
speed rules, and no stable reporting contract.

`manual_v2_prompt` gives the model the V2 policy, but the user has to paste it
or remember it each turn. In this benchmark it costs about 329 rough input
tokens.

`simplicio_prompt_plugin` gives the model the same operating policy
automatically through `pre_llm_call`, using a compact static overlay. It saves
18.24% rough input tokens versus the manually pasted V2 prompt and adds no
external calls. The local preprocessing cost is effectively noise relative to
network/model latency.

## V2 Coverage

| V2 improvement | Plugin behaviour |
|---|---|
| Cache by receipt/input hash | Included in the overlay as a required execution policy for repeat work. |
| Adaptive lane pool | Included as adaptive lanes in the safe-speed rules. |
| Backoff with jitter | Included and paired with provider-limit compliance. |
| Circuit breaker | Included as required provider safety. |
| Batching tiny tasks | Included to reduce tool/model turn overhead. |
| Prompt/context compression | Included before expensive model calls. |
| Local routing before LLM | Included for deterministic/simple work. |
| Idempotent-only speculation | Included explicitly; unsafe speculation is disallowed. |

The plugin is an execution-policy overlay, not a provider throttle bypass. It
does not attempt to evade rate limits, account limits, or terms of service.

## Canonical V2 Report Data

The canonical `wesleysimplicio/simplicio-prompt` README describes the broader
V2 safe-speed runtime as a tuple-space execution policy with lazy `batch_spawn`,
adaptive lanes, cache, batching, circuit breakers, backoff with jitter, context
compression, local yool routing, and idempotent-only speculation.

Canonical README highlights:

| Area | Reported V2 result |
|---|---:|
| Scale representation | `2,833.75x` faster than a normal instruction flow |
| Active execution | `26.93x` faster than normal sequential execution |
| Cache | `4x` fewer provider calls, a `75%` reduction |
| Batching | `32x` fewer small-task calls, a `96.88%` reduction |
| Circuit breaker | `64x` fewer failure attempts, a `98.44%` reduction |
| Token economy | `76.32%` estimated savings through context compression |

Those broader numbers are included as reference data for the policy this plugin
injects. The Hermes benchmark above remains intentionally narrower: it measures
the automatic pre-LLM overlay path introduced by this PR.

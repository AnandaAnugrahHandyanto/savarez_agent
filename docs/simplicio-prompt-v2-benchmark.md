# SIMPLICIO_PROMPT V2 Benchmark

![YOOL V2 Safe-Speed Runtime reference infographic](../website/static/img/simplicio-prompt/yool-v2-safe-speed-infographic-en.png)

This report compares three local message-preparation paths for the Hermes
SIMPLICIO_PROMPT plugin. It does not call a hosted model, so it does not claim
provider-side latency, quality, or tool-success improvements. It measures the
part this PR changes directly: pre-LLM prompt injection and token footprint.
In this PR, V2 means the `SIMPLICIO_PROMPT` policy from
`wesleysimplicio/simplicio-prompt`; the comparison baselines are normal
instructions and the earlier V1/manual instruction path.

Command:

```bash
python scripts/benchmark_simplicio_prompt.py --iterations 10000
```

## Results

| Case | Meaning | Median ms/build | p95 ms/build | Rough input tokens | Chars |
|---|---|---:|---:|---:|---:|
| normal_instruction | Normal/V1 baseline with no overlay | 0.000100 | 0.000200 | 28 | 112 |
| manual_v2_prompt | SIMPLICIO_PROMPT V2 pasted manually into the user prompt | 0.000300 | 0.000500 | 334 | 1,336 |
| simplicio_prompt_plugin | Automatic SIMPLICIO_PROMPT V2 overlay through the Hermes hook | 0.000300 | 0.000400 | 314 | 1,258 |

## Deltas

| Comparison | Result |
|---|---:|
| Automatic SIMPLICIO_PROMPT V2 plugin vs manually pasted SIMPLICIO_PROMPT V2 prompt | 5.99% fewer rough input tokens |
| SIMPLICIO_PROMPT V2 plugin vs normal/V1 instruction baseline | 1021.43% more rough input tokens |
| Plugin local preprocessing overhead vs normal/V1 instruction baseline | ~0.0002 ms median absolute delta |
| Extra model calls introduced by plugin | 0 |

## Interpretation

`normal_instruction` is the normal/V1 baseline. It is the fastest and cheapest
local path because it carries no execution overlay. It also gives the model no
tuple-space policy, no SIMPLICIO_PROMPT V2 safe-speed rules, and no stable
reporting contract.

`manual_v2_prompt` gives the model the SIMPLICIO_PROMPT V2 policy by manually
pasting the prompt into the message. It represents the V1-style adoption path:
the user has to paste it or remember it each turn. In this benchmark it costs
about 334 rough input tokens.

`simplicio_prompt_plugin` gives the model the same SIMPLICIO_PROMPT V2 policy
automatically through `pre_llm_call`, using a compact static overlay. It saves
5.99% rough input tokens versus the manually pasted SIMPLICIO_PROMPT V2 prompt
and adds no external calls. The local preprocessing cost is effectively noise
relative to network/model latency. Activation is config-driven rather than
text-driven: once enabled, the hook injects the overlay for every main-agent
turn, including messages that do not contain "Implement" or any other trigger
word.

## SIMPLICIO_PROMPT V2 Coverage

| SIMPLICIO_PROMPT V2 improvement | Plugin behaviour |
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

## Canonical SIMPLICIO_PROMPT V2 Report Data

The canonical `wesleysimplicio/simplicio-prompt` README describes the broader
SIMPLICIO_PROMPT V2 safe-speed runtime as a tuple-space execution policy with
lazy `batch_spawn`, adaptive lanes, cache, batching, circuit breakers, backoff
with jitter, context compression, local yool routing, and idempotent-only
speculation.

Canonical README highlights compare SIMPLICIO_PROMPT V2 against normal/V1
baselines:

| Area | Reported SIMPLICIO_PROMPT V2 result vs normal/V1 |
|---|---:|
| Scale representation | `2,833.75x` faster than a normal/V1 instruction flow |
| Active execution | `26.93x` faster than normal/V1 sequential execution |
| Cache | `4x` fewer provider calls, a `75%` reduction |
| Batching | `32x` fewer small-task calls, a `96.88%` reduction |
| Circuit breaker | `64x` fewer failure attempts, a `98.44%` reduction |
| Token economy | `76.32%` estimated savings through context compression |

Those broader numbers are included as reference data for the SIMPLICIO_PROMPT V2
policy this plugin injects. The Hermes benchmark above remains intentionally
narrower: it measures the automatic pre-LLM overlay path introduced by this PR.

# SIMPLICIO_PROMPT V2 Benchmark

![YOOL V2 Safe-Speed Runtime reference infographic](../website/static/img/simplicio-prompt/yool-v2-safe-speed-infographic-en.png)

This report compares three local message-preparation paths for the Hermes
SIMPLICIO_PROMPT plugin. It does not call a hosted model, so it does not claim
provider-side latency, quality, or tool-success improvements. It measures the
part this PR changes directly: pre-LLM prompt injection and token footprint.
In this PR, V2 means the bundled `SIMPLICIO_PROMPT` runtime snapshot under
`plugins/simplicio_prompt/vendor/simplicio_prompt`; the comparison baselines are
normal instructions and the earlier V1/manual instruction path.
The PR includes the prompt, spec, kernel, guardrails, examples, benchmarks, PDFs,
and image assets locally so Hermes does not need an external repository lookup.

Command:

```bash
python scripts/benchmark_simplicio_prompt.py --iterations 10000
```

## Results

| Case | Meaning | Median ms/build | p95 ms/build | Rough input tokens | Chars |
|---|---|---:|---:|---:|---:|
| normal_instruction | Normal/V1 baseline with no overlay | 0.000200 | 0.000400 | 28 | 112 |
| manual_v2_prompt | SIMPLICIO_PROMPT V2 local-path prompt pasted manually into the user prompt | 0.000500 | 0.000600 | 428 | 1,712 |
| simplicio_prompt_plugin | Automatic SIMPLICIO_PROMPT V2 overlay loaded from the bundled runtime snapshot | 0.000500 | 0.000600 | 1,660 | 6,642 |

## Deltas

| Comparison | Result |
|---|---:|
| Automatic vendored SIMPLICIO_PROMPT V2 plugin vs manually pasted local-path V2 prompt | 287.85% more rough input tokens |
| SIMPLICIO_PROMPT V2 plugin vs normal/V1 instruction baseline | 5828.57% more rough input tokens |
| Plugin local preprocessing overhead vs normal/V1 instruction baseline | ~0.0003 ms median absolute delta |
| Extra model calls introduced by plugin | 0 |
| External GitHub fetches introduced by plugin | 0 |

## Interpretation

`normal_instruction` is the normal/V1 baseline. It is the fastest and cheapest
local path because it carries no execution overlay. It also gives the model no
tuple-space policy, no SIMPLICIO_PROMPT V2 safe-speed rules, and no stable
reporting contract.

`manual_v2_prompt` gives the model the SIMPLICIO_PROMPT V2 policy by manually
pasting local bundle paths into the message. It represents the V1-style
adoption path: the user has to paste it or remember it each turn. In this
benchmark it costs about 428 rough input tokens.

`simplicio_prompt_plugin` gives the model the same SIMPLICIO_PROMPT V2 policy
automatically through `pre_llm_call`, loaded from the bundled local runtime
snapshot. The vendored plugin intentionally carries more context than the compact
manual prompt because it includes the local source-of-truth instruction and file
map needed to run without consulting an external GitHub repository. That costs
1,660 rough input tokens in this local benchmark, but it adds no external calls
and no provider calls. The local preprocessing cost is effectively noise
relative to network/model latency. Activation is config-driven rather than
text-driven: once enabled, the hook injects the overlay for every main-agent
turn, including messages that do not contain "Implement" or any other trigger
word.

## SIMPLICIO_PROMPT V2 Coverage

| SIMPLICIO_PROMPT V2 improvement | Plugin behaviour |
|---|---|
| Bundled runtime snapshot | All source files needed by the prompt are copied under `plugins/simplicio_prompt/vendor/simplicio_prompt/`. |
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

## Bundled SIMPLICIO_PROMPT V2 Report Data

The bundled `plugins/simplicio_prompt/vendor/simplicio_prompt/README.md`
describes the broader SIMPLICIO_PROMPT V2 safe-speed runtime as a tuple-space
execution policy with lazy `batch_spawn`, adaptive lanes, cache, batching,
circuit breakers, backoff with jitter, context compression, local yool routing,
and idempotent-only speculation.

Bundled README highlights compare SIMPLICIO_PROMPT V2 against normal/V1
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

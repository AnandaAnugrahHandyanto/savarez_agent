# Guarded Spark Compression Benchmark

Question: does the implemented disabled-by-default guardrail path make `gpt-5.3-codex-spark` safe enough for the next staged compression test?

## Method

- Exercised the actual `ContextCompressor._generate_summary()` prompt, latest-user anchor, validator, redaction, and deterministic repair code.
- Monkeypatched only the LLM call to route through `hermes chat -Q --provider openai-codex`; no production config or gateway state was changed.
- Compared three lanes: baseline `gpt-5.5` legacy prompt, Spark legacy prompt, and Spark guarded prompt.
- Fixtures covered rollout continuity, meta-instruction echo, and completed-request `None.` non-resurrection.

## Results

| Fixture | Lane | Score | Verdict | Time | Guardrail counters | Key misses |
|---|---|---:|---|---:|---|---|
| `spark-rollout` | `baseline-gpt-5.5-legacy` | 100.0% | PASS | 58.9s | repair=0, validate=0, fallback=0 | none |
| `spark-rollout` | `spark-legacy` | 100.0% | PASS | 14.6s | repair=0, validate=0, fallback=0 | none |
| `spark-rollout` | `spark-guarded` | 100.0% | PASS | 14.9s | repair=0, validate=0, fallback=0 | none |
| `meta-echo` | `baseline-gpt-5.5-legacy` | 100.0% | PASS | 50.7s | repair=0, validate=0, fallback=0 | none |
| `meta-echo` | `spark-legacy` | 100.0% | PASS | 14.6s | repair=0, validate=0, fallback=0 | none |
| `meta-echo` | `spark-guarded` | 100.0% | PASS | 13.7s | repair=0, validate=0, fallback=0 | none |
| `completed-none` | `baseline-gpt-5.5-legacy` | 100.0% | PASS | 30.1s | repair=0, validate=0, fallback=0 | none |
| `completed-none` | `spark-legacy` | 100.0% | PASS | 14.0s | repair=0, validate=0, fallback=0 | none |
| `completed-none` | `spark-guarded` | 100.0% | PASS | 13.7s | repair=0, validate=0, fallback=0 | none |

## Aggregate

| Lane | Avg score | Pass/Partial/Fail | Avg time |
|---|---:|---|---:|
| `baseline-gpt-5.5-legacy` | 100.0% | 3/0/0 | 46.6s |
| `spark-legacy` | 100.0% | 3/0/0 | 14.4s |
| `spark-guarded` | 100.0% | 3/0/0 | 14.1s |

## Verdict

Guarded Spark passed this 3-fixture implementation benchmark. This supports moving to a larger shadow benchmark, not a live default switch.
Legacy Spark average: 100.0%. Guarded Spark average: 100.0%.

## Artifacts

- Scores JSON: `/home/joe/.hermes/hermes-agent/spikes/003-spark-guarded-compression-benchmark/artifacts/scores.json`
- Per-lane prompts/outputs/stderr: `/home/joe/.hermes/hermes-agent/spikes/003-spark-guarded-compression-benchmark/artifacts`

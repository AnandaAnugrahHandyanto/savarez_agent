# Spark Trusted-State Shadow Benchmark

Candidate: `openai-codex / gpt-5.3-codex-spark` with guarded compression enabled in-process only.

## Method

- Exercised actual `ContextCompressor._generate_summary()` guarded path.
- Monkeypatched only `call_llm` to route through `hermes chat -Q`; production config and gateway were not edited or restarted.
- 25 fixtures cover active-task anchoring, stale-state correction, secret redaction, exact blockers/config values, file paths, multi-user Discord context, previous-summary iteration, completed `None.`, and no-live-rollout wording.

## Aggregate

| Fixtures | Pass/Partial/Fail | Avg score | Avg time | Guardrail counters |
|---:|---|---:|---:|---|
| 25 | 25/0/0 | 100.0% | 19.2s | repair=0, validate=0, fallback=0 |

## Results

| Fixture | Score | Verdict | Time | Misses |
|---|---:|---|---:|---|
| `trusted-01-spark-rollout` | 100.0% | PASS | 15.6s | none |
| `trusted-02-meta-echo` | 100.0% | PASS | 14.4s | none |
| `trusted-03-completed-none` | 100.0% | PASS | 14.2s | none |
| `trusted-04-stale-correction` | 100.0% | PASS | 17.3s | none |
| `trusted-05-secret-redaction` | 100.0% | PASS | 61.7s | none |
| `trusted-06-windows-literal` | 100.0% | PASS | 13.6s | none |
| `trusted-07-discord-multiuser` | 100.0% | PASS | 18.0s | none |
| `trusted-08-error-preservation` | 100.0% | PASS | 13.4s | none |
| `trusted-09-file-paths` | 100.0% | PASS | 34.5s | none |
| `trusted-10-pending-two-tasks` | 100.0% | PASS | 14.4s | none |
| `trusted-11-iterative-previous-summary` | 100.0% | PASS | 14.3s | none |
| `trusted-12-long-tool-noise` | 100.0% | PASS | 13.7s | none |
| `trusted-13-config-guardrails` | 100.0% | PASS | 14.0s | none |
| `trusted-14-threshold-risk` | 100.0% | PASS | 15.3s | none |
| `trusted-15-live-config-invariant` | 100.0% | PASS | 15.8s | none |
| `trusted-16-handoff-reference-skip` | 100.0% | PASS | 14.8s | none |
| `trusted-17-spanish-language` | 100.0% | PASS | 14.9s | none |
| `trusted-18-structured-state` | 100.0% | PASS | 14.4s | none |
| `trusted-19-quality-gate` | 100.0% | PASS | 15.8s | none |
| `trusted-20-rate-limit-fallback` | 100.0% | PASS | 13.0s | none |
| `trusted-21-no-live-rollout` | 100.0% | PASS | 16.1s | none |
| `trusted-22-artifact-links` | 100.0% | PASS | 28.2s | none |
| `trusted-23-model-route` | 100.0% | PASS | 14.7s | none |
| `trusted-24-current-vs-staged` | 100.0% | PASS | 14.8s | none |
| `trusted-25-final-report` | 100.0% | PASS | 43.1s | none |

## Live config after run

```json
{
  "main_provider": "openai-codex",
  "main_model": "gpt-5.5",
  "main_context": 272000,
  "compression_provider": "openai-codex",
  "compression_model": "gpt-5.5",
  "compression_context": 272000,
  "compression_guardrails": null
}
```

## Verdict

Guarded Spark reached the local trusted-state bar for this expanded shadow set. This still supports a staged canary/shadow rollout next, not an immediate live default switch.

## Artifacts

- Scores JSON: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/artifacts/scores.json`
- Live config snapshot: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/artifacts/live_config_after.json`
- Per-fixture prompts/outputs/stderr: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/artifacts`

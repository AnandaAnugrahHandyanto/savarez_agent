# Spark Compression Benchmark Spike

Question: can `gpt-5.3-codex-spark` preserve Hermes context-compression quality well enough to use its subscription bucket?

## Method

- Generated a realistic Hermes/GSD context-compaction fixture with must-keep facts, current-vs-stale corrections, secret traps, and filler/noise.
- Sent the same Hermes-style compaction prompt to `gpt-5.5` and `gpt-5.3-codex-spark` via `hermes chat -Q --provider openai-codex --toolsets safe`.
- Initial exact-ID score was too brittle, so this report uses semantic continuity checks: active task fidelity, current config, candidate context, blockers, redaction, stale-state handling, and pending asks.
- This spike did not modify `~/.hermes/config.yaml` and did not restart the gateway.

## Results

| Model | Semantic score | Verdict | Key misses | Output |
|---|---:|---|---|---|
| `gpt-5.5` | 100.0% | PASS | none | `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/baseline-gpt-5.5.md` |
| `gpt-5.3-codex-spark` | 88.0% | PARTIAL | active_task_user_request | `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/spark-gpt-5.3-codex-spark.md` |

## Findings

- Baseline `gpt-5.5`: 100.0% (PASS), 71.9s in the first full synthetic run.
- Spark `gpt-5.3-codex-spark`: 88.0% (PARTIAL), 19.1s in the first full synthetic run.
- Spark retained most technical facts, blockers, model/context values, redaction behavior, and the current-state correction that `gpt-5.5` remains active while Spark is only a candidate.
- Spark's first-run miss: it put the harness instruction itself in `## Active Task` instead of Joe's latest unfulfilled request. That is serious because `## Active Task` is Hermes' most important continuity field.
- Targeted retest with the exact Hermes Active Task wording passed for both models:
  - `gpt-5.5`: `User asked: "[LokiLore] gpt-5.3-codex-spark Yeah, let's do the testing..."`
  - `gpt-5.3-codex-spark`: `User asked: "gpt-5.3-codex-spark Yeah, let's do the testing..."`
- Config was verified unchanged after tests: main and compression remain `openai-codex / gpt-5.5 / 272000`.

## Verdict

Spark is promising but not baseline-equivalent yet. It is fast and retained most facts, and the Active Task failure did not reproduce under the exact Hermes wording. I would not switch default compression yet; next step is a real-session transcript benchmark. If that passes, use a staged rollout with quick rollback, not a blind default flip.

## Artifacts

- Prompt: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/prompt.txt`
- Turns fixture: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/turns.txt`
- Baseline output: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/baseline-gpt-5.5.md`
- Spark output: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/spark-gpt-5.3-codex-spark.md`
- Active-task retest JSON: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/active_task_retest.json`
- Active-task Spark output: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/spark-gpt-5.3-codex-spark-active-task.md`
- Original exact-ID scores: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/scores.json`
- Semantic scores: `/home/joe/.hermes/hermes-agent/spikes/001-spark-compression-benchmark/artifacts/scores_v2_semantic.json`

# Guarded Spark Compression Trusted-State Report

## Status

Guarded Spark reached the local trusted-state bar for an expanded shadow benchmark and blocker-focused code review. It is still **not live** and should remain disabled-by-default until a staged canary/shadow rollout is explicitly approved.

## Live Production Config Verified

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

## What Changed

- Added disabled-by-default compression guardrails wiring via `auxiliary.compression.guardrails.enabled`.
- Added latest-user anchor extraction and guarded prompt boundaries.
- Escaped user/tool/previous-summary/focus-topic content before inserting it into XML-like prompt blocks.
- Added deterministic Active Task repair for meta-echo, stale anchors, invalid `None.`, and overlap failures.
- Added structural validation for required headings using anchored markdown-heading checks.
- Added fail-closed behavior: if guarded summary validation cannot be repaired or main-model fallback also fails, Hermes returns `None` instead of persisting unsafe compacted state.
- Preserved fallback-to-main behavior for invalid auxiliary summaries when `summary_model` differs from the main model.

## Verification

- `tests/agent/test_context_compressor.py::TestSparkCompressionGuardrails`: `16 passed`
- `tests/agent/test_context_compressor.py tests/agent/test_context_compressor_summary_continuity.py`: `98 passed`
- Python compile check for touched production/test/benchmark files: passed
- `hermes config check`: passed
- Static added-line scan for common secret/shell/eval/pickle patterns: no findings
- Expanded Spark trusted shadow benchmark: `25/0/0`, average `16.6s`, guardrail counters `repair=0, validate=0, fallback=0`
- Independent follow-up review: passed; no blocking security or logic issues found

## Benchmark Artifacts

- README: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/README.md`
- Scores JSON: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/artifacts/scores.json`
- Live config snapshot: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/artifacts/live_config_after.json`
- Per-fixture prompts/outputs/stderr: `/home/joe/.hermes/hermes-agent/spikes/004-spark-trusted-shadow-benchmark/artifacts/`

## Review Blockers Found and Resolved

1. Previous-summary prompt boundary injection
   - Fixed by escaping previous summaries before guarded prompt insertion.
2. Invalid guarded output persisted when fallback unavailable/exhausted
   - Fixed by failing closed and returning `None` instead of storing invalid summaries.
3. `None.` Active Task accepted with generic completion wording
   - Fixed with non-generic anchor-term completion evidence.
4. Pending User Asks incorrectly counted as completion evidence
   - Fixed by only using Completed Actions and Resolved Questions for `None.` completion evidence.
5. Required headings validated by substring only
   - Fixed with anchored markdown-heading regex validation.

## Verdict

Guarded Spark is now locally trusted as a **disabled-by-default candidate** for staged shadow/canary evaluation. It is not approved as the live default compression model yet.

## Recommended Next Step

Create a staged canary/shadow config path that keeps production writes on `gpt-5.5`, records Spark guarded summaries and counters out-of-band, and promotes only after live-session shadow evidence confirms no continuity regressions.

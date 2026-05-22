# Tiny shadow-only compression canary config proposal

Status: **proposal only**. Do not enable without explicit approval. This is scoped to one controlled session and one shadow attempt.

## Purpose

Evaluate `gpt-5.3-codex-spark` as a no-write shadow compression candidate while keeping the production compression summary on the known-good route:

- Primary/live compression remains `openai-codex / gpt-5.5 / 272000`.
- Spark runs only as a guarded shadow candidate.
- Candidate output is validated and counted, but is not returned to the user and is not written to `_previous_summary`.
- Shadow egress stays on the same `openai-codex` subscription route; no Anthropic/OpenRouter/direct API fallback is introduced.

## Current verified baseline

Verified before writing this proposal:

```text
model:       openai-codex / gpt-5.5 / 272000
compression: openai-codex / gpt-5.5 / 272000
guardrails:  absent / disabled
hermes config check: OK
```

## Exact config block to enable for one controlled session

Add only the `guardrails` block under the existing `auxiliary.compression` section. Keep the existing primary compression provider/model/context unchanged.

```yaml
auxiliary:
  compression:
    provider: openai-codex
    model: gpt-5.5
    context_length: 272000
    timeout: 600
    base_url: ""
    api_key: ""
    extra_body: {}
    guardrails:
      enabled: true
      shadow:
        enabled: true
        model: gpt-5.3-codex-spark
        max_per_session: 1
        timeout: 20
```

Why these values:

- `guardrails.enabled: true` is required because the shadow path depends on the guarded prompt and validator.
- `shadow.enabled: true` opts into the no-write candidate path.
- `shadow.model: gpt-5.3-codex-spark` is the candidate under test.
- `max_per_session: 1` makes this a tiny canary: one shadow attempt per compressor instance/session.
- `timeout: 20` bounds latency impact; shadow errors/timeouts should increment counters and must not fail primary compression.
- Primary `provider/model/context_length` stays at the current known-good baseline.

## Controlled-session procedure

1. Back up config:
   ```bash
   cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-shadow-canary-$(date +%Y%m%d-%H%M%S)
   ```
2. Add the `guardrails` block above.
3. Validate config:
   ```bash
   hermes config check
   ```
4. Restart only when ready to test the single canary session:
   ```bash
   hermes gateway restart
   ```
5. Run exactly one controlled session that is expected to trigger compression, then stop and inspect telemetry/logs.
6. Roll back immediately after the controlled run unless Joe explicitly approves a wider shadow soak.

## Rollback

Surgical rollback: remove this entire subtree and leave all other compression settings untouched:

```yaml
    guardrails:
      enabled: true
      shadow:
        enabled: true
        model: gpt-5.3-codex-spark
        max_per_session: 1
        timeout: 20
```

Then verify and restart:

```bash
hermes config check
hermes gateway restart
```

Rollback success state:

```text
auxiliary.compression.provider = openai-codex
auxiliary.compression.model = gpt-5.5
auxiliary.compression.context_length = 272000
auxiliary.compression.guardrails = absent/null
```

Emergency rollback: restore the timestamped backup, run `hermes config check`, then restart the gateway.

## Telemetry counters to watch

Guardrail counters:

- `_summary_repair_count`
- `_summary_validation_failure_count`
- `_summary_guardrail_fallback_count`

Shadow counters/state:

- `_compression_shadow_count`
- `_compression_shadow_success_count`
- `_compression_shadow_validation_failure_count`
- `_compression_shadow_error_count`
- `_compression_shadow_last_model`
- `_compression_shadow_last_summary_hash`
- `_compression_shadow_last_issues`
- `_compression_shadow_last_error`

Expected single-session result:

```text
_compression_shadow_count == 1
_compression_shadow_success_count == 1
_compression_shadow_validation_failure_count == 0
_compression_shadow_error_count == 0
_summary_guardrail_fallback_count == 0
```

Acceptable but not rollout-qualifying result:

```text
_compression_shadow_count == 1
_compression_shadow_validation_failure_count == 1
# or
_compression_shadow_error_count == 1
```

This means primary compression stayed safe, but Spark is not ready to widen without fixing the issue.

Immediate rollback triggers:

- Any primary compression failure.
- Any returned/persisted summary that appears to come from Spark instead of `gpt-5.5`.
- `_summary_guardrail_fallback_count > 0` during the canary.
- `_compression_shadow_error_count > 0` caused by route/auth/provider errors.
- `_compression_shadow_validation_failure_count > 0` for active-task, required-heading, redaction, or stale-state issues.
- Noticeable gateway latency from the shadow call despite the 20s timeout.

## Log strings to inspect

Look in `~/.hermes/logs/gateway.log`, `~/.hermes/logs/agent.log`, and `~/.hermes/logs/errors.log` for:

```text
Context compression shadow model 'gpt-5.3-codex-spark' passed guardrail validation
Context compression shadow model 'gpt-5.3-codex-spark' failed validation
Context compression shadow model 'gpt-5.3-codex-spark' errored
Context compression summary guardrail
```

Do not paste raw logs into Discord; summarize the counter values and attach an artifact if needed.

## Canary acceptance gate

This single-session canary may only justify moving to a slightly larger shadow soak if all are true:

- Production response continuity is correct.
- Primary summary remains `gpt-5.5`-backed.
- Shadow attempt count is exactly `1`.
- Shadow success count is exactly `1`.
- Shadow validation/error counts are `0`.
- No secrets appear in candidate-related logs/artifacts.
- Config is rolled back or left enabled only with explicit approval.

It does **not** justify switching live/default compression to Spark.

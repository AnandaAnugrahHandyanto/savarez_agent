# Spark Compression Claude Roundtable

## Decision

Claude-only MoA found a viable path to make `gpt-5.3-codex-spark` usable for compression as **system parity**, not blind model parity:

1. Prompt restructure with XML-ish source boundaries and explicit anti-echo rules.
2. Deterministic latest-user-request anchor injected into the compression prompt.
3. Runtime validator across required sections, with active-task repair from the anchor.
4. Hybrid fallback to `gpt-5.5` on validator failure, high repair/fallback rate, or iterative-chain risk.
5. Spark remains disabled by default until expanded benchmark + shadow soak passes.

## Winner

`pipeline_architect` + `prompt_engineer` + `ops_rollout`, with `skeptic_redteam`'s iterative cap.

Reason: prompt-only reduces failure probability, but anchor+validator+repair eliminates the specific continuity failure. Fallback makes parity a system property.

## Prototype evidence

Existing fixture with optimized prompt and anchor:

- Model: `gpt-5.3-codex-spark`
- Return code: `0`
- Elapsed: `16.66s`
- Semantic score: `100.0% (100/100)`
- Active task validator: `True`
- Anchor overlap: `1.0`
- Production config changed: no

Artifacts:

- Chair synthesis: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/chair.md`
- Alignment review: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/alignment_review.md`
- Prototype script: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/prototype_anchor_prompt.py`
- Optimized prompt: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/artifacts/optimized_prompt.txt`
- Spark optimized output: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/artifacts/spark_optimized_output.md`
- Latest-user-request anchor: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/artifacts/latest_user_request.txt`
- Prototype JSON: `/home/joe/.hermes/hermes-agent/spikes/002-spark-compression-claude-roundtable/artifacts/prototype_result.json`

## Corrections required before production S0

- Extend validator beyond Active Task: required headings, non-empty important sections, anti-echo globally, secret redaction, sane lengths.
- Define economic floor: Spark must preserve enough subscription-bucket value after repair/retry/fallback overhead.
- Expand B1 to >=25 fixtures plus sanitized production transcript samples.
- Define anchor-miss fallback behavior.
- Persist/telemetry-count repair and fallback rates, or document restart reset as intentional.
- Use neutral repair wording: `Latest user request: "..."`.
- Require >=20 independent iterative chains before releasing iterative cap.
- Use stable hash-based session cohort assignment for canary/shadow.

## Rollout gate

Do not switch live compression yet. Next executable step is a code spike/PR behind disabled flags:

- `auxiliary.compression.candidate.enabled=false`
- candidate model `gpt-5.3-codex-spark`, context `128000`
- strict validator + repair + fallback
- shadow mode first; live summaries still come from `gpt-5.5`

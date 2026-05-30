# Hermes ↔ OpenClaw A2A v2.6.2 Validation

## 结论

PASS：v2.6.2 已完成 negative / failure-path evidence validator。

Validation marker：`A2A_V262_NEGATIVE_VALIDATION_OK`

## 本版目标

证明坏证据不会被误判为成功，并确保 v2.6.1 正例 evidence validator 回归仍通过。

## 实际执行命令

```bash
cd /.hermes/hermes-agent
python3 -m py_compile scripts/validate_a2a_v260_negative.py
python3 scripts/validate_a2a_v260_evidence.py \
  --write-summary examples/v2.6.0/evidence-validation-summary.json
python3 scripts/validate_a2a_v260_negative.py \
  --write-summary examples/v2.6.0/negative-validation-summary.json
```

## Negative validation result

```json
{
  "schema_version": "a2a-v262-negative-validation-v1",
  "ok": true,
  "case_count": 5,
  "matched_count": 5,
  "cases": [
    {
      "file": "examples/v2.6.0/negative-fixtures/neg-missing-marker.json",
      "expected_failure": "marker_missing",
      "detected_failures": [
        "marker_missing"
      ],
      "matched": true
    },
    {
      "file": "examples/v2.6.0/negative-fixtures/neg-token-recorded.json",
      "expected_failure": "token_recorded_true",
      "detected_failures": [
        "token_recorded_true"
      ],
      "matched": true
    },
    {
      "file": "examples/v2.6.0/negative-fixtures/neg-secret-like.json",
      "expected_failure": "forbidden_literal",
      "detected_failures": [
        "forbidden_literal"
      ],
      "matched": true
    },
    {
      "file": "examples/v2.6.0/negative-fixtures/neg-missing-evidence.json",
      "expected_failure": "evidence_missing",
      "detected_failures": [
        "evidence_missing"
      ],
      "matched": true
    },
    {
      "file": "examples/v2.6.0/negative-fixtures/neg-side-effect-live.json",
      "expected_failure": "unexpected_side_effect",
      "detected_failures": [
        "unexpected_side_effect"
      ],
      "matched": true
    }
  ],
  "positive_regression_ok": true,
  "side_effects": {
    "new_live_a2a_call": false,
    "gateway_restart": false,
    "openclaw_restart": false,
    "cron_enabled": false,
    "platform_send": false
  },
  "errors": []
}
```

## Positive regression result

```text
positive evidence validator ok: True
```

## Negative cases

本版覆盖 5 个预期失败：

1. `marker_missing`
2. `token_recorded_true`
3. `forbidden_literal`
4. `evidence_missing`
5. `unexpected_side_effect`

5 个 case 均 matched=true。

## Side Effects

```json
{
  "new_live_a2a_call": false,
  "gateway_restart": false,
  "openclaw_restart": false,
  "cron_enabled": false,
  "platform_send": false
}
```

本轮没有执行新的 live A2A call，没有重启服务，没有启用 cron，也没有平台外发。

## 证据路径

- Plan：`docs/hermes-openclaw-a2a-task-plan-v2.6.2.md`
- Negative fixtures：`examples/v2.6.0/negative-fixtures/`
- Validator：`scripts/validate_a2a_v260_negative.py`
- Summary：`examples/v2.6.0/negative-validation-summary.json`

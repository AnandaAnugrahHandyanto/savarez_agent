# Hermes ↔ OpenClaw A2A v2.6.1 Validation

## 结论

PASS：v2.6.1 已完成统一 evidence validator，并对 mock / dry-run / live three evidence dirs 完成验证。

Validation marker：`A2A_V261_EVIDENCE_VALIDATION_OK`

## 本版目标

补齐 v2.6.0 Phase 6 后的低风险自动验证层：不新增 live 调用，不扩张自动化边界，只回读既有证据并统一校验。

## 实际执行命令

```bash
cd /.hermes/hermes-agent
python3 -m py_compile scripts/validate_a2a_v260_evidence.py
python3 scripts/validate_a2a_v260_evidence.py \
  --write-summary examples/v2.6.0/evidence-validation-summary.json
```

## 实际执行结果

```json
{
  "schema_version": "a2a-v260-evidence-validation-v1",
  "ok": true,
  "results": [
    {
      "kind": "mock-fixtures",
      "path": "examples/v2.6.0/mock-fixtures",
      "ok": true,
      "receipt_count": 2,
      "accepted_count": 2,
      "overall": "accepted_with_boundary",
      "errors": []
    },
    {
      "kind": "two-worker-run",
      "path": "examples/v2.6.0/dry-run-two-worker",
      "expected_live": false,
      "ok": true,
      "run_id": "a2a-v260-two-worker-20260530T091037Z",
      "receipt_count": 2,
      "accepted_count": 2,
      "overall": "accepted_with_boundary",
      "errors": []
    },
    {
      "kind": "two-worker-run",
      "path": "examples/v2.6.0/live-two-worker",
      "expected_live": true,
      "ok": true,
      "run_id": "a2a-v260-two-worker-20260530T091052Z",
      "receipt_count": 2,
      "accepted_count": 2,
      "overall": "accepted_with_boundary",
      "errors": []
    }
  ],
  "side_effects": {
    "new_live_a2a_call": false,
    "gateway_restart": false,
    "openclaw_restart": false,
    "cron_enabled": false,
    "platform_send": false
  }
}
```

## 校验对象

- `examples/v2.6.0/mock-fixtures`
- `examples/v2.6.0/dry-run-two-worker`
- `examples/v2.6.0/live-two-worker`

## 校验内容

validator 已检查：

- JSON 可解析。
- receipt 必填字段存在。
- `schema_version=a2a-worker-receipt-v1`。
- `source_agent=hermes`。
- `ok=true`。
- `http_status=200`。
- `state=completed`。
- `auth.token_recorded=false`。
- evidence path 存在。
- marker 存在于 evidence 文件。
- acceptance report overall 为 `accepted_with_boundary`。
- dry-run 目录 `live_a2a_call=false`。
- live 目录 `live_a2a_call=true`。
- gateway / OpenClaw / cron / platform send 均未发生。
- forbidden literal scan 无命中。

## Side Effects

本轮没有执行新的 live A2A call。

summary 记录：

```json
{
  "new_live_a2a_call": false,
  "gateway_restart": false,
  "openclaw_restart": false,
  "cron_enabled": false,
  "platform_send": false
}
```

## 证据路径

- Validator：`scripts/validate_a2a_v260_evidence.py`
- Summary：`examples/v2.6.0/evidence-validation-summary.json`
- Plan：`docs/hermes-openclaw-a2a-task-plan-v2.6.1.md`

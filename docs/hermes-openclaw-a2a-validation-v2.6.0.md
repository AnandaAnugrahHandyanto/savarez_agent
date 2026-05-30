# Hermes ↔ OpenClaw A2A v2.6.0 Validation

## 结论

PASS：本轮完成的是 **本地 mock two-worker schema validation**，不是 live A2A 调用。

验证结果：`A2A_V260_MOCK_VALIDATION_OK`

## 本轮验证范围

- Dispatch Envelope fixture：2 个
  - `examples/v2.6.0/mock-fixtures/dispatch-worker-readiness.json`
  - `examples/v2.6.0/mock-fixtures/dispatch-worker-review.json`
- Worker Receipt fixture：2 个
  - `examples/v2.6.0/mock-fixtures/receipt-worker-readiness.json`
  - `examples/v2.6.0/mock-fixtures/receipt-worker-review.json`
- Acceptance Report fixture：1 个
  - `examples/v2.6.0/mock-fixtures/acceptance-report.json`
- Validator：
  - `scripts/validate_a2a_v260_mock.py`
- Validation Summary：
  - `examples/v2.6.0/mock-fixtures/validation-summary.json`

## 实际执行命令

```bash
cd /.hermes/hermes-agent
python3 -m py_compile scripts/validate_a2a_v260_mock.py
python3 scripts/validate_a2a_v260_mock.py \
  --fixture-dir examples/v2.6.0/mock-fixtures \
  --write-summary examples/v2.6.0/mock-fixtures/validation-summary.json
```

## 实际执行结果

```json
{
  "ok": true,
  "fixture_dir": "examples/v2.6.0/mock-fixtures",
  "dispatch_count": 2,
  "receipt_count": 2,
  "acceptance_overall": "accepted_with_boundary",
  "errors": [],
  "side_effects": {
    "live_a2a_call": false,
    "gateway_restart": false,
    "openclaw_restart": false,
    "cron_enabled": false,
    "platform_send": false
  }
}
```

## 校验点

- `schema_version` 与 fixture 类型匹配。
- `source_agent=hermes`，保持 Hermes-controller 边界。
- dispatch 中包含 `allowed_actions` / `forbidden_actions` / `expected_outputs` / `acceptance_criteria` / `stop_conditions`。
- receipt 中 `state=completed`、`http_status=200`、`auth.credential_recorded=false`。
- receipt 的 `marker` 已在本地 evidence 文件中找到。
- acceptance report 中两条 item 均可对应 receipt。
- external side effects 全部为 false。
- 本地 fixture 目录 secret-like literal scan 通过。

## 修正记录

第一次运行 validator 时发现 `dispatch-worker-review.json` 的 forbidden boundary 缺少 `cron` 与 `webhook` 明示项。已补齐：

- `enable cron or recurring jobs`
- `create or trigger webhooks`

修正后重新执行 validator，结果 PASS。

## 明确未做

- 未执行 live A2A call。
- 未读取或写入真实授权凭据。
- 未重启 Hermes gateway。
- 未重启 OpenClaw。
- 未启用 cron / daemon / webhook。
- 未向当前通道以外做平台发送。

## 下一步

下一步若继续，应进入 **live two-worker A2A 样例设计/实施**，但前提是继续保持 Hermes 作为 controller 和 final acceptor：

1. Worker A：只读 readiness live task。
2. Worker B：独立 review live task。
3. Hermes 回收两个 receipt，生成 acceptance report 和 compact current-channel summary。

进入 live 样例前仍需先做 endpoint/credential/source 状态确认，并且不得把 OpenClaw 自报完成当作最终验收。

Verification marker: live_a2a_call=false

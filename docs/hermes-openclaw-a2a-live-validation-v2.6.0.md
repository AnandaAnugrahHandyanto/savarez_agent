# Hermes ↔ OpenClaw A2A v2.6.0 Live Validation

## 结论

PASS with boundary：v2.6.0 已完成从本地 mock 到 live two-worker 的受控样例验证。

Validation marker：`A2A_V260_LIVE_TWO_WORKER_OK`

## 执行范围

本次执行严格对应 v2.6.0 实施顺序：

1. 计划落盘并回读验证：已完成。
2. 总入口文档指向 v2.6.0：已完成。
3. dispatch envelope / receipt / acceptance fixture：已完成。
4. 本地 mock schema validation：已完成。
5. live two-worker A2A 样例：已完成。
6. Hermes 回收 evidence 并生成 acceptance report：已完成。

未进入第 7 步：未固化为 queue CLI 或 Kanban/Swarm 模板。

## 实际执行命令

```bash
cd /.hermes/hermes-agent
python3 -m py_compile scripts/hermes_openclaw_v260_two_worker.py
python3 scripts/hermes_openclaw_v260_two_worker.py \
  --out-dir examples/v2.6.0/live-two-worker
```

## 真实执行结果

```json
{
  "ok": true,
  "run_id": "a2a-v260-two-worker-20260530T091052Z",
  "dry_run": false,
  "receipt_count": 2,
  "accepted_count": 2,
  "overall": "accepted_with_boundary",
  "secret_scan_ok": true,
  "out_dir": "examples/v2.6.0/live-two-worker",
  "compact_summary": "结论：A2A v2.6.0 two-worker 样例 accepted_with_boundary\nrun_id: a2a-v260-two-worker-20260530T091052Z\nOpenClaw 子任务：2 个，accepted 2 / rejected 0 / blocked 0\n证据：examples/v2.6.0/live-two-worker\n边界：未启用反向调用 / 未启用 cron / 未重启 gateway / 未外发平台消息\n下一步：只在明确要求后，才固化为 queue CLI 或 Kanban/Swarm 模板\n"
}
```

## 关键证据

- live evidence dir：`examples/v2.6.0/live-two-worker`
- dry-run evidence dir：`examples/v2.6.0/dry-run-two-worker`
- live readiness：`examples/v2.6.0/live-two-worker/readiness.json`
- Worker A receipt：`examples/v2.6.0/live-two-worker/a2a-v260-worker-readiness-receipt.json`
- Worker B receipt：`examples/v2.6.0/live-two-worker/a2a-v260-worker-review-receipt.json`
- Acceptance report：`examples/v2.6.0/live-two-worker/acceptance-report.json`
- Execution summary：`examples/v2.6.0/live-two-worker/execution-summary.json`
- Compact summary：`examples/v2.6.0/live-two-worker/compact-summary.md`

## Live readiness

`readiness.json` 记录：

- `agent_card_http_status=200`
- `agent_card_live=true`
- `credential_loaded=true`
- `credential_recorded=false`

这表示 live endpoint 可达，授权凭据仅用于本次请求，不写入证据文件。

## Worker 验收

Acceptance report 中两个子任务均为 accepted：

- `a2a-v260-worker-readiness`：accepted
- `a2a-v260-worker-review`：accepted

两个 receipt 均满足：

- `schema_version=a2a-worker-receipt-v1`
- `ok=true`
- `http_status=200`
- `state=completed`
- `auth.token_recorded=false`
- marker 在对应 evidence 文件中存在

## Side effects

Acceptance report 记录：

```json
{
  "gateway_restart": false,
  "openclaw_restart": false,
  "cron_enabled": false,
  "platform_send": false,
  "live_a2a_call": true
}
```

解释：

- `live_a2a_call=true`：本轮确实执行了 live Hermes → OpenClaw A2A JSON-RPC `message/send`。
- `gateway_restart=false`：未重启 Hermes gateway。
- `openclaw_restart=false`：未重启 OpenClaw。
- `cron_enabled=false`：未启用 cron。
- `platform_send=false`：未做额外平台外发。

## Secret scan

Acceptance report 记录：

```json
{
  "ok": true,
  "token_recorded": false,
  "forbidden_literals_found": []
}
```

本地回读扫描也显示：`violations=[]`。

## 边界

本轮通过的是受控 live two-worker 样例，不是开放式自治协作：

- 未启用 OpenClaw → Hermes 反向调用。
- 未启用 daemon / webhook / recurring automation。
- 未将该样例固化为 queue CLI 或 Kanban/Swarm 模板。
- Hermes 仍是 controller 和 final acceptor。

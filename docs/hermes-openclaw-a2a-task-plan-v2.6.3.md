# Hermes ↔ OpenClaw A2A v2.6.3 Verify Chain Plan

## 目标
将 v2.6.0 two-worker runner、v2.6.1 positive evidence validator、v2.6.2 negative validator 收束成一条本地可复跑的一键 verify 链路，输出统一 PASS / FAIL 结论。

## 版本判断
- 版本：v2.6.3
- 类型：patch
- 理由：不改变 Hermes Controller / OpenClaw Bounded Worker 能力边界，只补齐现有 v2.6.x 证据链的一键复跑入口与 runbook。

## 范围
1. 新增 `scripts/verify_a2a_v263_chain.py`。
2. 默认只执行本地 dry-run runner，不发起新的 live A2A call。
3. 复跑 positive evidence validator。
4. 复跑 negative failure-path validator。
5. 写入统一 summary：`examples/v2.6.0/verify-chain-summary.json`。
6. 补齐 validation / review 文档。

## 非范围
- 不启用 cron / daemon / webhook。
- 不重启 Hermes gateway 或 OpenClaw。
- 不新增 live A2A call。
- 不发送平台消息。
- 不开放 OpenClaw 反向调度。

## 验收标准
- `python3 -m py_compile scripts/verify_a2a_v263_chain.py` 通过。
- `python3 scripts/verify_a2a_v263_chain.py` 返回 exit code 0。
- summary 中 `ok=true`。
- `steps[].ok=true`。
- `side_effects.new_live_a2a_call=false`。
- `side_effects.gateway_restart=false`。
- `side_effects.openclaw_restart=false`。
- `side_effects.cron_enabled=false`。
- `side_effects.platform_send=false`。
- 生成的 v2.6.3 文档回读通过。

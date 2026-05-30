# Hermes ↔ OpenClaw A2A v2.6.4 Runbook

## 当前结论
v2.6.x 当前稳定边界是：Hermes 作为 Controller，OpenClaw 作为 Bounded Worker；v2.6.0 已有一次受控 live two-worker evidence，v2.6.1/v2.6.2/v2.6.3/v2.6.4 均不新增 live call。

## 一键本地 verify
在 Hermes Agent 仓库执行：

```bash
cd /.hermes/hermes-agent
python3 scripts/verify_a2a_v263_chain.py
```

预期结果：

```text
"ok": true
"result": "PASS"
```

该命令会：
1. 复跑 v2.6.0 dry-run two-worker runner，写入 `examples/v2.6.0/dry-run-two-worker/`。
2. 复跑 v2.6.1 positive evidence validator。
3. 复跑 v2.6.2 negative failure-path validator。
4. 写入统一 summary：`examples/v2.6.0/verify-chain-summary.json`。

## 只校验已有证据，不重写 dry-run runner
如果只想验证当前证据与负例，不重新生成 dry-run evidence：

```bash
cd /.hermes/hermes-agent
python3 scripts/verify_a2a_v263_chain.py --skip-dry-run-runner
```

## 单项命令
### positive evidence validator
```bash
cd /.hermes/hermes-agent
python3 scripts/validate_a2a_v260_evidence.py
```

### negative failure-path validator
```bash
cd /.hermes/hermes-agent
python3 scripts/validate_a2a_v260_negative.py
```

### dry-run two-worker runner
```bash
cd /.hermes/hermes-agent
python3 scripts/hermes_openclaw_v260_two_worker.py --dry-run --out-dir examples/v2.6.0/dry-run-two-worker
```

## 证据入口
- 统一 verify summary：`examples/v2.6.0/verify-chain-summary.json`
- v2.6.3 validation：`docs/hermes-openclaw-a2a-validation-v2.6.3.md`
- v2.6.3 review：`docs/hermes-openclaw-a2a-review-v2.6.3.md`
- v2.6.x 文件清单：`docs/hermes-openclaw-a2a-file-inventory-v2.6.x.md`

## 安全边界
运行本 runbook 不应触发：
- 新 live A2A call
- Hermes gateway restart
- OpenClaw restart
- cron / daemon / webhook enable
- platform send
- reverse autonomous loop

如果 summary 中任一上述 side effect 为 true，应视为 FAIL，先停止继续扩边界。

## 后续建议
v2.6.x 当前建议先整理 commit 或做文档审查；不要直接启用自动调度。若确需进入调度，必须另立新版本并明确审批边界。

# Hermes ↔ OpenClaw A2A v2.6.0 提升计划

状态：已立项 / 待实施  
版本：2.6.0  
类型：minor  
日期：2026-05-30  
维护者：Hermes 豆子  

## 1. 结论

本版目标是把 Hermes ↔ OpenClaw A2A 从“可通信 / 可跑队列 / 可控 cron 模板”提升为更接近 Hermes v0.15 Kanban/Swarm 思路的 **Hermes-controller / OpenClaw-worker 结构化协作模式**。

本版不启用新的 daemon、cron、webhook、反向 autonomous loop，也不重启 Hermes gateway 或 OpenClaw。先完成计划、协议、验收口径和最小真实样例设计，实施时再按低风险步骤推进。

## 2. 背景与当前边界

已有事实：

- Phase 6 结论为 `accepted_with_boundary`。
- Hermes 已能作为 controller 发起 bounded two-turn A2A 对话。
- OpenClaw 已能作为 bounded worker/peer 返回可验收结果。
- failure paths、queue runner、compact cron callback、paused recurring cron template 已有阶段性验证。
- 当前 recurring cron job `170596628792` 保持 paused。

当前边界：

- 不默认进入 OpenClaw 主动反向调用 Hermes。
- 不默认启用 autonomous bidirectional daemon。
- 不把 OpenClaw 自报完成当作最终验收。
- 当前通道只回流 compact summary，不刷原始 JSON。

## 3. 本版为什么是 minor

本版不是简单补文档，也不是修复同一脚本的小问题。它会新增一套明确的协作能力边界：

- Hermes 负责拆分、派发、验收、汇总。
- OpenClaw 负责 bounded worker / checker / implementer 子任务。
- 每个子任务都必须有 dispatch envelope、receipt、evidence、acceptance classification。

因此按 minor 版本处理：`2.5.x → 2.6.0`。

## 4. 本版目标

建立可复用的 A2A 任务拆分与验收机制：

1. Hermes 根据用户目标做动态拆分，不机械固定拆，也不盲目拆。
2. OpenClaw 只接收有边界的子任务，不获得路线决策权。
3. 每个子任务包含明确 allowed / forbidden actions。
4. OpenClaw 返回 receipt 和 evidence，而不是只返回自然语言“完成”。
5. Hermes 做 goal-level acceptance，分类为：
   - `accepted`
   - `accepted_with_boundary`
   - `rejected`
   - `blocked`
   - `unsafe`
6. 当前通道只输出一份短汇总：任务安排、执行状态、验收结论、证据路径、下一步。

## 5. 范围

### 5.1 本版包含

- 设计 dispatch envelope schema。
- 设计 OpenClaw worker receipt schema。
- 设计 Hermes acceptance report schema。
- 设计最小 two-worker A2A 样例。
- 设计 evidence 目录结构。
- 设计 compact current-channel summary 模板。
- 明确低风险自动授权规则。
- 明确 stop conditions。
- 更新总入口文档，说明 v2.6.0 是下一步提升方向。

### 5.2 本版不包含

- 不启用 OpenClaw → Hermes 反向调用。
- 不启用 daemon / webhook / recurring cron 自动执行。
- 不修改生产 gateway 配置。
- 不重启 Hermes gateway。
- 不重启 OpenClaw gateway。
- 不打印、复制、落盘 A2A 凭据。
- 不让 OpenClaw 自行扩展目标或创建后续任务。

## 6. 角色边界

### 6.1 Hermes Controller

Hermes 固定承担：

- 理解用户目标。
- 判断是否需要拆分。
- 生成 bounded subtask。
- 决定任务派发顺序。
- 设置 allowed_actions / forbidden_actions。
- 验收 OpenClaw receipt / artifact / evidence。
- 输出 compact summary 给当前通道。

### 6.2 OpenClaw Worker

OpenClaw 固定承担：

- 执行被派发的 bounded task。
- 只在 allowed_actions 范围内行动。
- 遇到 stop condition 即停止并返回 blocked / unsafe / rejected 线索。
- 生成可验证 artifact / evidence / marker。
- 不做项目路线决策。
- 不启用自动外发或后台循环。

## 7. Dispatch Envelope 草案

每个派发给 OpenClaw 的子任务必须包含：

```json
{
  "schema_version": "a2a-dispatch-envelope-v1",
  "task_id": "a2a-v260-worker-001",
  "source_agent": "hermes",
  "target_agent": "openclaw-247-main",
  "goal": "bounded task goal",
  "context": "only the context needed for this task",
  "allowed_actions": [
    "read-only checks",
    "write evidence files under agreed evidence directory",
    "run non-destructive validation commands"
  ],
  "forbidden_actions": [
    "modify production config",
    "restart gateway/systemd/cron/daemon/webhook",
    "print or persist secrets",
    "delete unknown files",
    "send platform messages directly"
  ],
  "expected_outputs": [
    "receipt JSON",
    "artifact preview",
    "evidence file path",
    "deterministic marker"
  ],
  "acceptance_criteria": [
    "HTTP 200 / JSON-RPC result when live A2A is used",
    "state completed for success tasks",
    "expected marker present",
    "token_recorded=false",
    "no authorization-header / bearer-token literals in evidence"
  ],
  "stop_conditions": [
    "credential/token needed",
    "destructive action required",
    "service restart required",
    "task scope ambiguous",
    "evidence cannot be produced"
  ]
}
```

## 8. Receipt Schema 草案

OpenClaw 子任务回执必须包含：

```json
{
  "schema_version": "a2a-worker-receipt-v1",
  "ok": true,
  "task_id": "a2a-v260-worker-001",
  "source_agent": "hermes",
  "target_agent": "openclaw-247-main",
  "protocol": "a2a-jsonrpc",
  "http_status": 200,
  "remote_task_id": "...",
  "remote_context_id": "...",
  "state": "completed",
  "marker": "A2A_V260_WORKER_001_OK",
  "artifact_text_preview": "...",
  "evidence_path": "examples/v2.6.0/...",
  "auth": {
    "type": "bearer",
    "token_recorded": false
  },
  "error": null
}
```

## 9. Acceptance Report 草案

Hermes 验收报告必须包含：

```json
{
  "schema_version": "a2a-acceptance-report-v1",
  "run_id": "a2a-v260-YYYYMMDD-HHMMSS",
  "overall": "accepted_with_boundary",
  "items": [
    {
      "task_id": "a2a-v260-worker-001",
      "classification": "accepted",
      "reason": "marker and evidence verified",
      "evidence_path": "examples/v2.6.0/..."
    }
  ],
  "secret_scan": {
    "ok": true,
    "token_recorded": false,
    "forbidden_literals_found": []
  },
  "external_side_effects": {
    "gateway_restart": false,
    "openclaw_restart": false,
    "cron_enabled": false,
    "platform_send": false
  },
  "next_step": "only proceed to live two-worker sample after explicit implementation start"
}
```

## 10. 最小 two-worker 样例设计

建议实施时先跑两个低风险任务：

### Worker A：只读状态核查

目标：让 OpenClaw 回报自身 A2A endpoint / agent card / runtime 状态，输出 marker：

```text
A2A_V260_READINESS_OK
```

允许：只读检查、写 evidence。  
禁止：改配置、重启、开端口、写 token。

### Worker B：独立复核 / 反向审查

目标：让 OpenClaw 审查 Hermes 给出的 dispatch envelope 是否边界清晰，输出 marker：

```text
A2A_V260_REVIEW_OK
```

允许：只读分析、输出审查意见。  
禁止：执行实施、触发真实外发、创建自动化任务。

### Hermes Final Acceptance

Hermes 回收两个 receipt 后：

- 校验 marker。
- 校验证据路径存在。
- 校验 secret scan。
- 校验无未授权 side effect。
- 输出一个 compact summary。

## 11. Evidence 目录结构

建议路径：

```text
examples/v2.6.0/
  run-<timestamp>/
    dispatch-worker-readiness.json
    dispatch-worker-review.json
    receipt-worker-readiness.json
    receipt-worker-review.json
    acceptance-report.json
    compact-summary.md
    secret-scan.txt
```

## 12. Compact Summary 模板

当前通道只回：

```text
结论：A2A v2.6.0 two-worker 样例 accepted_with_boundary
run_id: ...
OpenClaw 子任务：2 个，accepted 2 / rejected 0 / blocked 0
证据：examples/v2.6.0/run-...
边界：未启用反向调用 / 未启用 cron / 未重启 gateway / 未外发平台消息
下一步：是否把该样例固化为 queue CLI 模板
```

## 13. 低风险自动授权规则

Hermes 可自动允许 OpenClaw 执行以下动作：

- 只读状态检查。
- 读取自身项目目录内非 secret 文件。
- 写入 agreed evidence directory。
- 运行非破坏性验证命令。
- 生成 receipt / summary / validation artifact。

必须停止并等待用户确认的动作：

- 修改生产配置。
- 打印、复制、迁移 secret/token/key。
- 重启 Hermes/OpenClaw gateway。
- 启用 cron/daemon/webhook/reverse loop。
- 删除或覆盖未知文件。
- 对外发送平台消息。

## 14. 实施顺序

1. v2.6.0 计划落盘并回读验证。
2. 更新总入口文档指向 v2.6.0。
3. 编写 dispatch envelope / receipt / acceptance schema fixture。
4. 先做本地 mock schema validation。
5. 再做 live two-worker A2A 样例。
6. Hermes 回收 evidence 并生成 acceptance report。
7. 只在用户确认后，再决定是否固化为 queue CLI 或 Kanban/Swarm 风格模板。

## 15. 验收标准

本版计划阶段 PASS 条件：

- `docs/hermes-openclaw-a2a-task-plan-v2.6.0.md` 存在。
- 总入口文档包含 v2.6.0 下一步说明。
- 文档包含 dispatch envelope、receipt、acceptance report、two-worker sample、side-effect boundary。
- 回读验证关键 marker 存在。
- 不改 config。
- 不重启 gateway。
- 不触发 OpenClaw live call。

后续实施阶段 PASS 条件：

- 至少两个 OpenClaw bounded tasks 返回 receipt。
- Hermes 能验收并生成 `acceptance-report.json`。
- secret scan 通过。
- compact summary 不包含原始 JSON 大块。
- 未启用新的自动化边界。

## 16. Side Effects

本计划文件落盘只修改仓库文档。

未执行：

- 未改 `/root/.hermes/config.yaml`。
- 未改 `/root/.hermes/.env`。
- 未重启 Hermes gateway。
- 未重启 OpenClaw。
- 未创建/启用 cron。
- 未执行真实 A2A live call。
- 未发送额外平台消息。

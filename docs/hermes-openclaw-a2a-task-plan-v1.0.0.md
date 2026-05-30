# Hermes ↔ OpenClaw A2A Task Plan v1.0.0

> 本计划用于约束 Hermes 与 OpenClaw 相互对话、任务转达、结果验收与当前通道回流。  
> 核心原则：Hermes 是任务派出关键 agent，也是验收内容关键 agent；OpenClaw 是被明确分发 bounded task 的执行/协作 agent。禁止为了“能力扩张”跳过验收、跳过边界、跳到 daemon/cron/webhook 自动化。

## 0. 最终目标

建立一条可持续维护的 Hermes ↔ OpenClaw 协作链路：

1. Hermes 能按任务类型决定是否分发给 OpenClaw。
2. Hermes 能把任务拆成明确、有限、有验收标准的 bounded task。
3. OpenClaw 执行后返回可验证结果，而不是只自称完成。
4. Hermes 负责验收：核对 receipt、artifact、marker、错误状态、证据路径和 secret scan。
5. Hermes 将每次交流最终结果以短摘要回流到当前用户通道。
6. 所有原始 JSON、日志、receipt、summary、run index 落盘，方便后续修复/升级追溯。

一句话：**不是让两个 agent 无限聊天，而是让 Hermes 有控制地派工、验收、回报。**

## 1. 角色边界

### 1.1 Hermes / 豆子

职责：

- 项目 controller。
- 任务入口判断者。
- 任务拆分者。
- 分发 agent。
- 验收 agent。
- 当前通道回流 agent。
- 证据和推进记录维护者。

Hermes 必须做的判断：

- 这个任务是否需要 OpenClaw，还是 Hermes 自己做更稳。
- 如果需要 OpenClaw，应该派一个原子任务，还是 2-5 个 bounded queue items。
- OpenClaw 的结果是否满足验收标准。
- 失败是协议失败、执行失败、回流失败、证据缺失，还是验收不通过。
- 是否允许进入下一阶段；未验收通过不能扩张边界。

### 1.2 OpenClaw

职责：

- 接收 Hermes 派发的 bounded task。
- 在自己的能力范围内执行、分析、实现或核查。
- 返回结构化/可摘取的结果。
- 提供 task id / context id / artifact / marker / preview 等可验证信息。

OpenClaw 不负责：

- 决定整体项目路线。
- 决定是否启用 cron/daemon/webhook。
- 直接向用户当前通道刷长 JSON。
- 替代 Hermes 做最终验收。

### 1.3 用户当前通道

只接收 compact summary：

- 安排了什么任务。
- 谁执行。
- 执行状态。
- 验收结果。
- 失败原因或下一步。
- 证据路径。

不接收：完整 raw JSON、完整日志、内部队列 dump，除非巡山大王明确要求。

## 2. 不盲扩张规则

任何阶段都必须满足“当前阶段验收通过”才进入下一阶段。

禁止跳跃：

- readiness 没过，不做 authenticated task。
- authenticated task 没过，不做 reusable runner。
- runner 没过，不做 queue。
- queue 没过，不做 cron。
- failure path 没过，不做 daemon/webhook。
- compact callback 没过，不开启自动回流。

默认不做的事：

- 不默认启用长期 daemon。
- 不默认开启 recurring cron。
- 不默认让 OpenClaw 反向调 Hermes。
- 不默认让 OpenClaw 直接发用户消息。
- 不默认把所有任务都分发给 OpenClaw。

扩张边界必须满足：

1. 本阶段有明确收益。
2. 有独立验收标准。
3. 有失败回退路径。
4. 有证据落盘。
5. 不影响当前 Hermes/Feishu 正常通道。

## 3. 分发策略

### 3.1 Hermes 自己处理

适合：

- 本地文件检查、配置核实、文档整理。
- 简单命令、状态查询、短修复。
- 涉及 Hermes 当前通道、gateway、cronjob 状态判断。
- 最终验收和用户回流。

### 3.2 分发给 OpenClaw

适合：

- OpenClaw 本机/自身运行态核查。
- 需要另一个 agent 独立审查的实现、文档、计划。
- 中等复杂但边界清晰的代码/配置任务。
- 可用明确 marker 或 artifact 验收的任务。

### 3.3 拆成多个 queue items

适合：

- 可自然分成 2-5 个独立项的任务。
- 每项有单独 expected_marker。
- 任一项失败不应阻塞其他项落证据。

不适合：

- 目标不清的探索。
- 需要大量往返沟通才能定义需求的任务。
- 高风险系统改动。

## 4. 版本化推进计划

### Phase 0 — 当前状态基线

目标：确认现有文档、skill、runner、cron、OpenClaw endpoint 的真实状态。

交付物：

- 当前状态记录：`docs/hermes-openclaw-a2a-current-state.md`
- evidence/runner/cron manifest：记录可用脚本、证据目录、cron job 状态。

验收标准：

- 回读确认文档存在。
- 明确哪些是已验证能力，哪些只是历史记录。
- 不调用 OpenClaw，不改配置，除非单独进入 smoke test。

当前建议：下一步先做这一阶段。

### Phase 1 — 最小 A2A smoke test

目标：证明当前 Hermes 能对 OpenClaw 发一个 authenticated bounded task，并拿到可验证 receipt。

任务：

1. 读取 OpenClaw agent card。
2. 读取/定位 token 来源，但不打印 token。
3. 发送 deterministic marker 任务，例如 `A2A_SMOKE_V1_0_0`。
4. 保存 request/response/receipt。
5. 验证 HTTP、JSON-RPC、state、artifact/preview、marker。
6. secret scan。
7. 当前通道回流短摘要。

验收标准：

- receipt `ok=true`。
- state 为 completed 或明确可接受状态。
- marker 出现在 artifact/agent preview。
- token_recorded=false。
- evidence 路径存在且可回读。

### Phase 2 — Hermes 分发器/验收器最小 runner

目标：把手动 smoke test 固化成明确 runner，而不是靠临时命令。

交付物：

- 一个显式 runner 脚本或 CLI。
- 输入：task_id、task text、expected_marker。
- 输出：receipt JSON、summary JSON、compact Markdown。

验收标准：

- 成功任务能生成 receipt + compact summary。
- 失败任务不会被标记成功。
- stdout 不刷 raw JSON。
- 所有原始数据落盘。

### Phase 3 — 失败路径验证

目标：证明 Hermes 作为验收 agent 能拒绝坏结果。

必须覆盖：

- 错 token / 无 token。
- bad endpoint。
- malformed receipt。
- marker 缺失。
- secret-like callback 内容。
- duplicate callback guard。

验收标准：

- 失败不进入 sent/passed 状态。
- 不产生误导性成功 summary。
- 不泄漏 token/header。

### Phase 4 — 小批量 queue runner

目标：允许 Hermes 一次派发 2-5 个 bounded tasks，但仍由 Hermes 逐项验收。

交付物：

- queue schema。
- queue validate。
- queue run。
- per-item receipt。
- aggregate summary。

验收标准：

- success_count / failure_count 准确。
- 单项失败不阻塞其他项落盘。
- aggregate summary 简短可回流当前通道。

### Phase 5 — 受控 cron 模板，不默认启用

目标：仅在前面阶段稳定后，把 runner 包装成 paused recurring cron template。

边界：

- 创建后立即 pause。
- 不自动运行。
- 手动 run 时必须 capture baseline → resume → run → monitor → verify → pause。

验收标准：

- cron job `enabled=false/state=paused`。
- runbook 写清楚。
- 真实执行与 scheduler accepted 分开报告。

### Phase 6 — 双向/反向能力评估，暂不实现为默认

目标：评估 OpenClaw 主动回 Hermes 或多轮对话是否必要。

进入条件：

- Phase 1-5 都稳定。
- 用户明确要求双向自动协作。
- 已有防循环、max_round、duplicate guard、failure policy。

默认结论：当前不作为近期目标，避免盲扩张。

## 5. 当前下一步执行建议

下一步只做 Phase 0，不直接扩张：

1. 盘点当前 repo docs / skill references / scripts / cron jobs / evidence directories。
2. 写 `docs/hermes-openclaw-a2a-current-state.md`。
3. 明确：哪些能力“历史上验证过”，哪些能力“当前运行态已验证”。
4. 回读验证文件。
5. 给巡山大王短摘要。

Phase 0 完成后，再决定是否做 Phase 1 smoke test。

## 6. 验收口径

每个阶段必须回答：

- 是否真的执行了？
- 是否真的落盘了？
- 是否真的回读了？
- 是否真的验收通过？
- 是否有副作用？
- 是否影响 gateway/current channel？
- 下一步是否扩张边界？为什么？

未满足验收标准时，只能汇报“未通过 / 阻塞 / 待补证据”，不能宣告完成。

## 7. 汇报格式

每次回流当前通道采用：

```markdown
# 报告巡山大王

**结论**：通过 / 未通过 / 部分通过。

**本次派发**：派给谁、派了什么、task_id。

**执行结果**：成功/失败、关键结果。

**验收结果**：Hermes 验收通过/退回，理由。

**证据**：路径。

**边界**：未触发什么、未扩张什么、下一步是什么。
```

## 8. 本计划的当前状态

- 版本：v1.0.0。
- 类型：任务计划与边界约束。
- 当前只写文档，不执行 OpenClaw 任务。
- 下一步推荐：执行 Phase 0 current-state capture。

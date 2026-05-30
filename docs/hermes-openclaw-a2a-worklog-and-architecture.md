# Hermes ↔ OpenClaw A2A 推进记录与工作原理

状态：持续维护中的运行/升级入口文档  
最后更新：2026-05-29  
维护者：Hermes 豆子  
目标：让以后修复、升级、扩展 Hermes ↔ OpenClaw 相互对话/任务转达能力时，不依赖聊天记忆，能从磁盘文档恢复设计意图、落地点、验证边界和下一步。

## 1. 总判断

Hermes ↔ OpenClaw 的稳定交流方式应以 **A2A JSON-RPC** 为主线：

- Hermes 当前作为 controller / orchestrator。
- OpenClaw 作为 remote worker / peer agent。
- 单次任务通过 OpenClaw A2A `message/send` 接口传递。
- 每次跨代理调用必须生成 receipt / summary / evidence。
- 当前通道回流只展示关键短摘要：安排了什么任务、执行状态、成功/失败、证据路径。
- 原始 JSON、请求、响应、完整日志只落盘，不刷屏发给用户。

这条线的核心不是“两个端口能通”，而是：

1. Hermes 能把任务可靠发给 OpenClaw；
2. OpenClaw 能产出可验证结果；
3. Hermes 能校验 receipt 和 artifact；
4. Hermes 能把简要结果回流到用户当前通道；
5. 所有推进和证据都能从磁盘复盘。


## 1.1 当前下一版提升方向：v2.6.0

当前下一版计划已落盘：

- `/.hermes/hermes-agent/docs/hermes-openclaw-a2a-task-plan-v2.6.0.md`

目标：把 A2A 从“可通信 / 可队列 / 可控 cron 模板”提升为 **Hermes-controller / OpenClaw-worker 结构化协作模式**。

关键原则：

- Hermes 负责拆分、派发、验收、汇总回流。
- OpenClaw 负责 bounded worker / checker / implementer 子任务。
- 每个子任务必须有 dispatch envelope、receipt、evidence、acceptance classification。
- 当前通道只回 compact summary，不刷原始 JSON。
- v2.6.0 计划阶段不启用 daemon / cron / webhook / reverse autonomous loop，不重启 gateway，不执行真实 live call。

## 2. 已有落盘位置

### 主仓库文档

- `/.hermes/hermes-agent/docs/hermes-openclaw-a2a-worklog-and-architecture.md`
  - 本文件。总入口、工作原理、推进记录、升级边界。
- `/.hermes/hermes-agent/docs/hermes-openclaw-a2a-v240-recurring-cron-template.md`
  - 已有的 recurring cron template 记录。
- `/.hermes/hermes-agent/docs/hermes-openclaw-a2a-v250-cron-monitor-race-hardening.md`
  - 已有的 cron monitor race hardening 记录。

### Skill 长期知识

- `/root/.hermes/skills/autonomous-ai-agents/agent-to-agent-a2a-bridging/SKILL.md`
  - A2A 桥接主 skill。
- `/root/.hermes/skills/autonomous-ai-agents/agent-to-agent-a2a-bridging/references/`
  - v0.6.7 到 v2.6.0 的具体阶段参考，包括 authenticated ping、callback loop、guarded send、queue runner、cron wrapper、failure paths、manual cron verification 等。

### 相关专员/平台路由知识

- `/root/.hermes/skills/software-development/hermes-specialist-workflow-routing/references/`
  - Hermes ↔ OpenClaw 专员链、webhook bridge、gateway live install、OpenClaw readiness 等早期参考。
- `/root/.hermes/skills/software-development/hermes-platform-delivery-and-channel-routing/references/hermes-openclaw-a2a-receipt-callback.md`
  - receipt callback / 平台回流相关参考。

## 3. 通信架构

### 3.1 首选通信方式

首选：OpenClaw 暴露的 A2A JSON-RPC endpoint。

典型调用：

```json
{
  "jsonrpc": "2.0",
  "id": "<local-request-id>",
  "method": "message/send",
  "params": {
    "configuration": {
      "blocking": true,
      "acceptedOutputModes": ["text/plain"],
      "historyLength": 5
    },
    "message": {
      "kind": "message",
      "messageId": "<uuid>",
      "role": "user",
      "parts": [
        {"kind": "text", "text": "<bounded task>"}
      ],
      "metadata": {
        "source_agent": "hermes",
        "target_agent": "openclaw-247-main",
        "task_id": "<task-id>"
      }
    },
    "metadata": {
      "source_agent": "hermes",
      "target_agent": "openclaw-247-main",
      "task_id": "<task-id>",
      "protocol": "a2a-jsonrpc"
    }
  }
}
```

### 3.2 回流方式

当前阶段默认：Hermes 主会话负责把最终关键短摘要回流给用户当前通道。

不要让 OpenClaw 直接往用户通道发长 JSON。原因：

- 当前通道目标、topic/thread、平台格式由 Hermes 更清楚。
- Hermes 可以做 duplicate guard、secret scan、summary render。
- 用户明确希望当前通道只看关键短摘要。

### 3.3 不推荐作为首选的方式

- 平台消息互相 @：可作为兜底，不适合作为稳定任务总线。
- Webhook：可以后续作为自动触发入口，但不应跳过 A2A receipt 验证。
- Cron/daemon：必须在 one-shot runner、failure path、queue schema、compact callback 都稳定后再启用。

## 4. 核心工件约定

每次跨代理任务至少落盘这些内容：

- request：请求体，不能包含 A2A 凭据明文。
- raw response：原始响应，安全时保存。
- receipt JSON：规范化结果。
- summary JSON / Markdown：用于当前通道回流的短摘要来源。
- secret scan 结果：确认没有 bearer-token / authorization-header 等敏感字面量泄漏。
- run index：批量/队列场景用 run_id 索引证据目录。

receipt 必备字段：

```json
{
  "ok": true,
  "task_id": "...",
  "source_agent": "hermes",
  "target_agent": "openclaw-247-main",
  "protocol": "a2a-jsonrpc",
  "http_status": 200,
  "remote_task_id": "...",
  "remote_context_id": "...",
  "state": "completed",
  "artifact_text_preview": "...",
  "agent_text_preview": "...",
  "summary": "...",
  "auth": {
    "type": "bearer",
    "token_source": "remote:ssh-openclaw-config 或 env/secret-manager",
    "token_recorded": false
  }
}
```

## 5. 推进版本线

已沉淀在 skill references 中的主线：

- v0.6.x：readiness / authenticated A2A ping / reusable forwarder。
- v0.7.x：callback loop / guarded callback send / one-shot runner。
- v1.0.0：bounded two-turn loop。
- v1.1.0：failure-path validation。
- v1.2.0：explicit local queue runner。
- v1.3.0：mixed success/failure queue isolation。
- v1.4.0：queue CLI/schema validation。
- v2.0.0：controlled cron progression。
- v2.1.0：dispatch strategy + compact callback。
- v2.2.0：compact cron callback wrapper。
- v2.3.x：cronjob boundary / scheduler run verification / runtime monitor。
- v2.4.0：paused recurring cron template。
- v2.5.0：cron monitor race hardening。
- v2.6.0：controlled manual run wrapper for paused recurring jobs。

本文件不是替代这些 references，而是作为总入口和工作原理说明。

## 6. 当前安全边界

### 已确认的设计边界

- 用户当前通道只应收到 compact summary。
- 原始 JSON 和完整 evidence 必须落盘。
- `cronjob run accepted` 不等于脚本已经执行。
- evidence directory exists 不等于 summary 已完成。
- monitor 没看到新 evidence 可能是 baseline race，不等于 cron 没跑。
-  recurring cron template 应默认创建后暂停，除非用户明确要求启用。
- A2A auth token 不进入 stdout、docs、receipt、request 文件。文档中也避免写入真实 token 或可直接匹配的敏感头样例。

### 仍需每次运行时验证的状态

- OpenClaw endpoint 当前是否在线。
- A2A 凭据来源是否仍有效。
- OpenClaw 返回 task state 是否 completed。
- artifact/agent preview 是否包含预期 marker。
- 当前 Hermes gateway/cron delivery 是否正常。
- 当前证据目录是否落盘且没有 secret 泄漏。

## 7. 以后修复/升级时的恢复步骤

从零恢复上下文时，按这个顺序检查：

1. 读本文件：
   - `/.hermes/hermes-agent/docs/hermes-openclaw-a2a-worklog-and-architecture.md`
2. 读 A2A skill：
   - `/root/.hermes/skills/autonomous-ai-agents/agent-to-agent-a2a-bridging/SKILL.md`
3. 按目标版本读对应 reference：
   - 例如 cron monitor 问题先看 v2.3.1、v2.3.2、v2.4.0、v2.5.0、v2.6.0。
4. 检查仓库当前状态：
   - `cd /.hermes/hermes-agent && git status --short --branch && git diff --stat`
5. 检查 OpenClaw 247 状态：
   - `192.168.31.247`，gateway 常见端口 `18789`。
   - 注意：systemd service failed 不一定代表 OpenClaw 不可用，可能已有 node gateway 进程占用端口。
6. 检查当前 Hermes gateway/cron 状态：
   - `hermes gateway status`
   - `hermes cron list`
7. 执行最小 smoke test：
   - readiness → authenticated ping → receipt → compact summary → secret scan。
8. 只有在 smoke test 通过后，才继续 queue / cron / daemon 类升级。

## 8. 推荐下一步路线

按风险从低到高：

1. 必须：保持本文件与 skill references 同步更新。
2. 推荐：把当前可用的 runner/script/evidence 目录统一列到一个 manifest。
3. 推荐：补一个 `docs/hermes-openclaw-a2a-current-state.md`，只记录当前运行态和最新可执行命令。
4. 可选：为 queue CLI 增加 `doctor` 子命令，自动检查 endpoint/token/secret-scan/evidence-dir。
5. 可选：等 one-shot 和 failure path 再次验证后，再启用受控 cron 或 webhook。

## 9. 回流给用户的固定格式

每次 A2A 任务完成，当前通道只回：

```markdown
# 报告巡山大王

**结论**：成功/失败/部分成功。

**任务**：安排给 OpenClaw 的任务简述。

**结果**：OpenClaw 返回的关键结果或失败原因。

**证据**：`/absolute/path/to/evidence_dir`

**边界**：是否发送了外部消息、是否只是当前回复承载回流、是否有待验证项。
```

## 10. 本次落盘记录

2026-05-29：

- 用户要求把“推进记录、怎么推进、以后修复升级如何回忆工作原理”做好落盘。
- 已检查现有 A2A 文档和 skill references。
- 确认长期知识主要在 `agent-to-agent-a2a-bridging` skill references。
- 新增本总入口文档：`/.hermes/hermes-agent/docs/hermes-openclaw-a2a-worklog-and-architecture.md`。
- 本次未修改运行配置、未重启服务、未触发 cron、未调用 OpenClaw。

## v2.6.3 Verify Chain

- 状态：PASS with boundary。
- 新增入口：`scripts/verify_a2a_v263_chain.py`。
- 统一 summary：`examples/v2.6.0/verify-chain-summary.json`。
- 验证范围：v2.6.0 dry-run two-worker runner + v2.6.1 positive evidence validator + v2.6.2 negative failure-path validator。
- 边界：没有新增 live A2A call，没有 cron / daemon / webhook，没有服务重启，没有平台外发，没有反向调度。

## v2.6.4 Runbook Closure

- 状态：runbook closure in place。
- Runbook：`docs/hermes-openclaw-a2a-runbook-v2.6.4.md`。
- 文件清单：`docs/hermes-openclaw-a2a-file-inventory-v2.6.x.md`。
- 一键验证命令：`python3 scripts/verify_a2a_v263_chain.py`。
- 只读校验命令：`python3 scripts/verify_a2a_v263_chain.py --skip-dry-run-runner`。
- 边界：不新增 live A2A call，不启用 cron / daemon / webhook，不重启服务，不平台外发，不启用反向调度。


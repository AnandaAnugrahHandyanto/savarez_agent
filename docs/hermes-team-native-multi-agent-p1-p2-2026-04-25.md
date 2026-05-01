# Hermes-native 多智能体框架 P1/P2 收口记录

日期：2026-04-25
位置：`~/.hermes/runtime-hermes-agent/hermes_team/`，同步到 `~/.hermes/hermes-agent/hermes_team/`

## 结论

Hermes 已从“单 agent + 状态存储”推进为可由工具入口直接调用的 Hermes-native 多智能体框架。当前能力覆盖：

- 角色注册：`cio / researcher / planner / executor / reviewer / risk_officer`
- 编排入口：`TeamOrchestrator.run(TeamRunSpec)`
- 工具入口：`team_run_task / team_status / team_events / team_roles`
- 工作流模式：sequential 与基础 DAG
- 执行层：每个角色可通过 `TeamRunner` 启动独立 `AIAgent`
- 状态持久化：`runs.json / events.json / registry.json / approvals.json`
- 治理门禁：危险动作 approval gate，默认阻断生产、凭证、交易、外部 webhook、删除等风险信号
- 测试覆盖：orchestration / tool entrypoint / task graph / approval gate

## 新增核心文件

- `hermes_team/approval_gate.py`
- `hermes_team/task_graph.py`
- `tools/hermes_team_tool.py`
- `tests/test_hermes_team_tool.py`
- `tests/test_hermes_team_task_graph.py`
- `tests/test_hermes_team_approval_gate.py`

## 工具入口

### `team_run_task`

运行 Hermes-native team workflow。

参数：
- `goal`: 目标
- `context`: 上下文/路径/验证命令
- `task_id`: 可选，已有 team task id
- `roles`: sequential 模式的角色顺序
- `mode`: `sequential` 或 `dag`
- `graph`: DAG 节点列表
- `require_review`: 是否自动要求 reviewer
- `metadata`: 可携带 priority/risk/requires_approval

### `team_status`

按 `run_id` / `task_id` / latest 查询 runs。

### `team_events`

按 `run_id` / `task_id` 查询 events。

### `team_roles`

列出 Hermes team 角色和 toolsets。

## DAG 节点格式

```json
{
  "id": "plan",
  "role": "planner",
  "goal": "produce execution plan",
  "depends_on": ["research"],
  "context": "optional context",
  "toolsets": ["file"],
  "metadata": {"risk": "low"}
}
```

DAG 当前是确定性拓扑顺序执行；已经具备依赖失败阻断后续节点的能力。并行执行留给 P3。

## Approval Gate

`ApprovalGate` 会检测以下风险信号并写入 pending approval：

- production/prod/deploy
- credential/secret/api key/token
- financial/trade/trading/payment
- delete/destructive/irreversible
- external/webhook/send_message
- metadata.requires_approval=true 或 metadata.risk=high/critical
- risk_officer role

阻断时：
- 不调用 runner
- 写 `approvals.json`
- 写 `team.approval_required` event
- registry 状态变为 `approval_pending`

若 `approvals.json` 中存在同 scope 的 `approved` 记录，则允许继续执行。

## 验证命令

runtime：

```bash
cd ~/.hermes/runtime-hermes-agent
source venv/bin/activate
pytest tests/test_hermes_team_orchestration.py tests/test_hermes_team_tool.py tests/test_hermes_team_task_graph.py tests/test_hermes_team_approval_gate.py tests/test_hermes_team_registry_api.py tests/test_hermes_team_task_hook.py -q
```

source：

```bash
cd ~/.hermes/hermes-agent
pytest tests/test_hermes_team_orchestration.py tests/test_hermes_team_tool.py tests/test_hermes_team_task_graph.py tests/test_hermes_team_approval_gate.py tests/test_hermes_team_registry_api.py tests/test_hermes_team_task_hook.py -q
```

## 下一阶段 P3

- DAG 并行 runner
- 长任务 watcher/status UI
- CLI `/team` 子命令
- approval approve/reject 工具入口
- 子 agent 成本/耗时统计
- 更细的 spec-review 与 quality-review 双阶段模板化

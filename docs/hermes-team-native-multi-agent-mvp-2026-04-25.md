# Hermes-native 多智能体框架 MVP

日期: 2026-04-25

## 结论

Hermes 已具备自有多智能体框架的最小可运行闭环，不依赖 OpenClaw 写路径。

本次补齐的是 control plane + execution adapter 层：

- roles: Hermes-native 角色定义与注册表
- dispatcher: 角色任务分派、事件记录、registry 绑定
- runner: 角色执行抽象，默认可接 AIAgent，测试可注入 fake executor
- orchestrator: 顺序 workflow，自动补 reviewer，汇总 run
- messages/events: team 事件持久化
- policies: role/toolset 基础权限策略
- tests: 覆盖角色、分派、策略阻断、orchestrator e2e

## 架构边界

当前模块位置：

- `hermes_team/roles.py`
- `hermes_team/messages.py`
- `hermes_team/policies.py`
- `hermes_team/runner.py`
- `hermes_team/dispatcher.py`
- `hermes_team/orchestrator.py`

持久化仍限定在：

- `$HERMES_HOME/state/team/`

新增状态文件：

- `events.json`
- `runs.json`

复用既有状态文件：

- `tasks.json`
- `archive.json`
- `task_run_session_registry.json`
- `approvals.json`

## 运行流

```text
TeamRunSpec
  -> TeamOrchestrator.run()
  -> TeamRunStore records run
  -> TeamEventStore records lifecycle events
  -> TeamDispatcher.dispatch(role step)
  -> TeamRunner.run_role()
  -> RegistryStore.bind_mapping(task/run/session/status)
  -> reviewer step
  -> TeamRunResult
```

默认顺序流：

```text
pending -> cio_triage -> assigned -> executing -> review -> done
```

失败流：

```text
... -> blocked
```

## 验证

live runtime:

```bash
cd ~/.hermes/runtime-hermes-agent
source venv/bin/activate
pytest tests/test_hermes_team_orchestration.py tests/test_hermes_team_registry_api.py tests/test_hermes_team_task_hook.py -q
# 12 passed in 1.58s
```

source repo:

```bash
cd ~/.hermes/hermes-agent
source .venv/bin/activate 2>/dev/null || source venv/bin/activate
pytest tests/test_hermes_team_orchestration.py tests/test_hermes_team_registry_api.py tests/test_hermes_team_task_hook.py -q
# 12 passed, 10 warnings in 1.88s
```

## 后续 P1/P2

P1:

- 增加 team tool/CLI：`team_run_task`, `team_status`, `team_events`
- 将 dispatcher 接入现有 `delegate_task` batch execution
- 增加 planner/task_graph，支持 DAG 与并行层

P2:

- approval gate：对外部副作用、生产、凭证、金融动作接入审批
- watcher/status UI：长期运行 team task 可观测
- reviewer 双阶段：spec compliance + code quality

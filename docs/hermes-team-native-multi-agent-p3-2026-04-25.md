# Hermes-native 多智能体框架 P3 收口记录

日期：2026-04-25
位置：`~/.hermes/runtime-hermes-agent/`，已同步到 `~/.hermes/hermes-agent/`

## 结论

P3 高价值能力已补齐到可验收状态：Hermes team 已具备 CLI `/team` 入口、审批 approve/reject、并行 DAG、watcher/status/events、metrics 与模板化 workflow。OpenClaw 仍仅作为历史只读参考；本轮写入均在 Hermes runtime/source 双路径内完成。

## P3 能力矩阵

| 能力 | 状态 | 入口/文件 | 验收证据 |
|---|---:|---|---|
| CLI `/team` 子命令 | 已完成 | `cli.py::_handle_team_command`，`hermes_cli/commands.py` | `tests/cli/test_team_slash_command.py` |
| 工具入口注册 | 已完成 | `tools/hermes_team_tool.py`，`toolsets.py` | `tests/test_hermes_team_tool.py` |
| approve/reject | 已完成 | `team_approve` / `team_reject` / `TeamApprovalManager` | `tests/test_hermes_team_tool.py` 与 approval gate 套件 |
| watcher/status/events | 已完成 | `team_status` / `team_events` / `/team status` / `/team events` | CLI + tool tests |
| metrics | 已完成 | `hermes_team/metrics.py`，`team_metrics`，`/team metrics` | `tests/test_hermes_team_tool.py` |
| 并行 DAG | 已完成 | `hermes_team/task_graph.py` | `tests/test_hermes_team_task_graph.py` |
| 模板化 workflow | 已完成 | `hermes_team/workflow_templates.py`，`team_templates`，`template` 参数 | `tests/test_hermes_team_workflow_templates.py` |
| runtime/source parity | 已完成 | rsync runtime → source | 双路径定向测试 48 passed |

## 新增/更新入口

### CLI

```text
/team run <goal>
/team status [run_id|task_id]
/team events [run_id|task_id]
/team roles
/team approvals [pending|approved|rejected]
/team approve <approval_id> [reason]
/team reject <approval_id> [reason]
/team metrics
/team templates [template_name]
```

### Tools

- `team_run_task`
- `team_status`
- `team_events`
- `team_roles`
- `team_approvals`
- `team_approve`
- `team_reject`
- `team_metrics`
- `team_templates`

### Built-in workflow templates

- `implementation_review`: planner → executor → reviewer
- `research_plan_execute`: researcher → planner → executor → reviewer
- `parallel_audit`: security/tests/docs 并行审计 → synthesis 汇总

## 并行 DAG 语义

- `TeamTaskGraph.execution_levels()` 会按依赖层级分组。
- `TeamGraphRunner.run(..., parallel=True, max_concurrency=N)` 会在同一 dependency level 内并行 dispatch。
- 返回 `execution_order` 记录每批并行节点，`parallel=True` 标记并行执行。
- 如果依赖失败，后续节点进入 blocked，不绕过治理门禁。

## 验证命令与结果

runtime：

```bash
cd ~/.hermes/runtime-hermes-agent
source venv/bin/activate
pytest tests/test_hermes_team_tool.py tests/test_hermes_team_workflow_templates.py tests/test_hermes_team_task_graph.py tests/test_hermes_team_approval_gate.py tests/test_hermes_team_orchestration.py tests/test_hermes_team_health_probe.py tests/test_hermes_team_source_bridge.py tests/test_hermes_team_audit_diff.py tests/test_hermes_team_task_hook.py tests/test_hermes_team_no_legacy_writes.py tests/test_hermes_team_registry_api.py tests/cli/test_team_slash_command.py -q
# 48 passed in 20.82s
```

source：

```bash
cd ~/.hermes/hermes-agent
source venv/bin/activate
pytest tests/test_hermes_team_tool.py tests/test_hermes_team_workflow_templates.py tests/test_hermes_team_task_graph.py tests/test_hermes_team_approval_gate.py tests/test_hermes_team_orchestration.py tests/test_hermes_team_health_probe.py tests/test_hermes_team_source_bridge.py tests/test_hermes_team_audit_diff.py tests/test_hermes_team_task_hook.py tests/test_hermes_team_no_legacy_writes.py tests/test_hermes_team_registry_api.py tests/cli/test_team_slash_command.py -q
# 48 passed in 19.25s
```

parity check：

```bash
python - <<'PY'
from pathlib import Path
for p in ['hermes_team','tools/hermes_team_tool.py','toolsets.py','hermes_cli/commands.py','cli.py','tests/test_hermes_team_workflow_templates.py','tests/test_hermes_team_task_graph.py','tests/cli/test_team_slash_command.py']:
 r=Path('/Users/zezesun/.hermes/runtime-hermes-agent')/p
 s=Path('/Users/zezesun/.hermes/hermes-agent')/p
 print(p, 'OK' if (r.is_dir() and s.is_dir()) or (r.read_bytes()==s.read_bytes()) else 'DIFF')
PY
# all OK
```

## 剩余建议

- 后续如果要进一步增强，可补真实长任务 watcher 的持续刷新 UI；当前 status/events/metrics 已可做运行可观测闭环。
- 真实外部执行、交易、生产、凭证等仍必须走 approval gate，不因 team 自动化而绕过治理。

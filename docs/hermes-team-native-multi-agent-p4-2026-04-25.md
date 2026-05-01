# Hermes-native 多智能体框架 P4 增强收口记录

日期：2026-04-25
位置：`~/.hermes/runtime-hermes-agent/`，已同步到 `~/.hermes/hermes-agent/`

## 结论

P4 高价值增强已落地：Hermes team 在 P3 的 run/status/events/metrics/templates 基础上，补齐了 live-style watcher、增强 metrics report、sandbox policy/audit、失败后 bounded dynamic replanning、approval audit。OpenClaw 仍仅作为历史只读参考；本轮写入均在 Hermes runtime/source 双路径内完成。

## P4 能力矩阵

| 能力 | 状态 | 入口/文件 | 验收证据 |
|---|---:|---|---|
| watch snapshot/UI | 已完成 | `hermes_team/watcher.py`，`team_watch` | `tests/test_hermes_team_p4_enhancements.py` |
| enhanced metrics report | 已完成 | `hermes_team/metrics_reporter.py`，`team_metrics` | `tests/test_hermes_team_tool.py` |
| sandbox policy/audit | 已完成 | `hermes_team/sandbox.py`，`team_sandbox_audit`，dispatch `team.sandbox_applied` | `tests/test_hermes_team_p4_enhancements.py`，`tests/test_hermes_team_orchestration.py` |
| dynamic replanning | 已完成 | `hermes_team/replanner.py`，`TeamRunSpec.auto_replan`，`team_replans` | `tests/test_hermes_team_p4_enhancements.py` |
| approval audit | 已完成 | `hermes_team/approval_audit.py`，`team_approval_audit` | `tests/test_hermes_team_tool.py` |
| runtime/source parity | 已完成 | rsync runtime → source | 双路径 `tests/test_hermes_team*.py` 均 46 passed |

## 新增/更新 tool 入口

- `team_watch`
  - 输入：`run_id` / `task_id` / `limit` / `format=json|text`
  - 输出：run 状态、steps、errors、最新事件、stale 标记。
- `team_sandbox_audit`
  - 输入：`run_id` / `task_id` / `role`
  - 输出：每次 dispatch 的 sandbox policy 记录。
- `team_replans`
  - 输入：`run_id` / `task_id`
  - 输出：replan decision、proposed graph、skip/needed 原因。
- `team_approval_audit`
  - 输出：审批总量、pending/approved/rejected 分布、过期 pending、风险信号统计。
- `team_metrics`
  - 输出从原始 snapshot 升级为 `{snapshot, derived}`，derived 包含 completion_rate、failed_runs、pending_approvals、top_events、event_density。
- `team_run_task`
  - 新增参数：`auto_replan`，失败时可触发 bounded recovery DAG。

## 关键语义

- Sandbox：dispatcher 在实际 runner 前生成 `TeamSandboxPolicy`，记录 `team.sandbox_applied` 事件与 `sandbox_audit.json`；默认禁网，危险 metadata 可强制 read-only。
- Replan：仅对非 approval gate 阻断的失败运行生效；最多按 `metadata.max_replan_attempts` 有界重试；生成 planner → executor → reviewer recovery DAG；不绕过 approval gate。
- Watcher：从 `runs.json` + `events.json` 聚合快照，支持按 run/task/latest 查询，并持久化到 `watch.json`。
- Store parity：orchestrator 在 run 前同步 task/event/run/registry/approval/sandbox store path，避免测试或 runtime 中临时 state_dir 改动导致跨目录漂移。

## 验证命令与结果

runtime：

```bash
cd ~/.hermes/runtime-hermes-agent
source venv/bin/activate
python -m pytest tests/test_hermes_team*.py -q
# 46 passed in 1.60s
```

source：

```bash
cd ~/.hermes/hermes-agent
source venv/bin/activate
python -m pytest tests/test_hermes_team*.py -q
# 46 passed in 1.53s
```

定向 P4：

```bash
python -m pytest tests/test_hermes_team_tool.py tests/test_hermes_team_p4_enhancements.py -q
# 6 passed
```

## 修复过的回归点

- watcher `not_found`：根因是测试/调用方只改 `task_store.state_dir`，`run_store.path` 仍指旧目录；已加 `_sync_store_paths()`。
- dynamic replanning 被 approval gate 误拦：根因是 replan goal 文案含 `produce`，命中 `prod` 关键字；已改为安全措辞，并强化 `non-production sandbox` 归一。
- registry metrics 为 0：根因是 `_sync_store_paths()` 将 registry path 错指到 `registry.json`，与 `RegistryStore` canonical 文件名不一致；已修回 `task_run_session_registry.json`。

## 当前剩余判断

已达到可收口状态。继续增强的高价值方向只剩真实前端/TUI streaming watch、跨进程长任务 heartbeat、以及生产级 approval reviewer 分级；这些属于下一阶段而非本轮必须项。

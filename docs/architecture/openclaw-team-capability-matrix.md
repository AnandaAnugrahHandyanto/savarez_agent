# OpenClaw 多智能体团队能力映射矩阵

> 结论先行：**Hermes 已吸收 OpenClaw 多智能体团队的运行底座与默认写路径切流，但尚未完整吸收 OpenClaw/Honcho 历史高级多智能体语义。** 本矩阵用于把“已吸收 / 部分吸收 / 未吸收”落实到具体实现与验收证据。

## 1. 结论摘要

| 维度 | 结论 |
|---|---|
| P0 运行底座 | **已吸收** |
| 默认运行态切流 | **已完成** |
| delegate/subagent 协同骨架 | **部分吸收** |
| observer / peerPerspective / agentPeerMap（Hermes 当前仅完成 `workspaceAgentPeerMap` metadata persistence/query merge 部分） | **部分吸收（增强）** |
| multi-agent setup 自动迁移 | **未吸收** |

## 2. 能力映射矩阵

| OpenClaw 团队能力 | Hermes 当前对应实现 | 状态 | 迁移口径 | 关键证据 | 说明 |
|---|---|---|---|---|---|
| 团队状态目录（runtime state） | `HERMES_HOME/state/team` | **已吸收** | 非迁移导入项；已 Hermes-native 吸收 | `hermes_team/paths.py` | 默认运行态已脱离 OpenClaw 目录 |
| 任务存储 | `TaskStore` + `task_hook.py` | **已吸收** | 非迁移导入项；已 Hermes-native 吸收 | `hermes_team/task_store.py`, `hermes_team/task_hook.py` | 任务创建/列出/归档走 Hermes-native store |
| 审批存储 | `ApprovalStore` + compat 读取 | **已吸收** | 非迁移导入项；已 Hermes-native 吸收 | `hermes_team/approval_store.py`, `tests/test_hermes_approval_compat.py` | 保留兼容读取，但运行态主写路径在 Hermes |
| task/job/session/run 注册表 | `RegistryStore` + `registry_api.py` | **已吸收** | 非迁移导入项；已 Hermes-native 吸收 | `hermes_team/registry_store.py`, `hermes_team/registry_api.py`, `tests/test_hermes_team_registry_api.py` | 已形成 Hermes 自有 registry |
| cron_upsert 调度 | `hermes_team/task_cron.py` | **已吸收** | 非迁移导入项；已 Hermes-native 吸收 | `hermes_team/task_cron.py`, `tests/test_hermes_team_task_hook.py` | 调度创建/更新与 registry 绑定已原生化 |
| 默认不写 legacy 目录 | Hermes-native state only | **已吸收** | 非迁移导入项；默认切流保护 | `tests/test_hermes_team_no_legacy_writes.py` | 满足“不污染 openclaw”要求 |
| legacy 团队数据桥接 | `LegacyOpenClawBridge` | **已吸收** | 只读桥接 / 审计；非自动迁移 | `hermes_team/source_bridge.py`, `tests/test_hermes_team_source_bridge.py` | 只读桥接，仅用于显式 bootstrap / 审计 |
| legacy bootstrap 默认关闭 | env gate `HERMES_ENABLE_OPENCLAW_TEAM_BOOTSTRAP=1` | **已吸收** | 显式开关；非默认迁移 | `hermes_team/source_bridge.py` | 防止误把历史目录当默认主存储 |
| delegate/subagent 隔离执行 | `delegate_task` | **部分吸收** | Hermes-native 运行能力；非 direct import | `tools/delegate_tool.py` | 子代理拥有隔离上下文/终端/工具集 |
| 父子 session 关联 | `parent_session_id` 写入 session DB | **部分吸收** | Hermes-native 运行能力；非 direct import | `tools/delegate_tool.py`, `run_agent.py`, `hermes_state.py` | 已有 lineage，但不是 OpenClaw observer hierarchy 全替代 |
| delegation 结果回灌父代理观察面 | `MemoryManager.on_delegation(...)` + Honcho observer context block + provider-side observer memory merge | **部分吸收（增强）** | Hermes-native 运行能力；非 direct import | `tools/delegate_tool.py`, `agent/memory_provider.py`, `agent/memory_manager.py`, `plugins/memory/honcho/__init__.py`, `tests/tools/test_delegate.py`, `tests/agent/test_memory_provider.py`, `tests/honcho_plugin/test_session.py` | 父代理可收到 child session + parent observer session + peer perspective + agent peer map 元数据；Honcho 首轮上下文与后续工具读取均可保留最小 observer block / summary 语义，但仍不是完整 peer observer 模型 |
| multi-agent parent observer（Honcho 语义） | delegation metadata 已透传至 parent memory hook，但无层级 observer 编排 | **部分吸收** | 不在当前 direct migration contract；后续吸收项 | `tools/delegate_tool.py`, `tests/tools/test_delegate.py` | 已有 parent observer session id 挂载，仍未对齐完整 Honcho observer hierarchy |
| `peerPerspective` on context() | delegation hook 已可携带 `peer_perspective` 元数据，但未进入独立 context 读取语义 | **部分吸收** | 不在当前 direct migration contract；后续吸收项 | `tools/delegate_tool.py`, `tests/tools/test_delegate.py`, `tests/agent/test_memory_provider.py` | 已补最小透传，不等于完整 context peer semantics |
| workspace `agentPeerMap` | delegation hook + Honcho session metadata `workspaceAgentPeerMap` + observer query merge | **部分吸收（增强）** | 不在当前 direct migration contract；后续吸收项 | `tools/delegate_tool.py`, `plugins/memory/honcho/session.py`, `tests/tools/test_delegate.py`, `tests/agent/test_memory_provider.py`, `tests/honcho_plugin/test_session.py` | 已完成 workspace 级持久化/恢复，父代理观测面会合并 workspace peer map 与本轮 delegation peer map；但 Hermes 当前仅完成最小 metadata persistence/query merge，不等于完整 workspace-level canonical peer state |
| multi-agent setup 自动迁移 | 无直接导入，仍属 manual review | **未吸收** | archive/manual review only | `website/docs/reference/cli-commands.md`, `docs/migration/openclaw.md` | 官方迁移文档仍未把该能力纳入直接迁移 |
| channel bindings / hooks/webhooks 团队相关迁移 | manual review / archive only | **未吸收** | archive/manual review only | `website/docs/reference/cli-commands.md` | 不能宣称一键吸收 |

## 3. 关键缺口

### 已补齐的 P0
- 任务 / 审批 / registry / cron 运行底座已 Hermes-native 化
- 默认写路径已切离 OpenClaw
- legacy 仅用于只读桥接与显式 bootstrap
- 已有最小链路 E2E：`task -> approval -> cron_upsert -> registry -> list`

### 仍存在的 P1
- **正式 E2E 证据已补齐**：`tests/test_openclaw_multi_agent_team_e2e.py` + `tests/tools/test_delegate.py` + `tests/agent/test_memory_provider.py` + `tests/test_hermes_team_registry_api.py` 已形成“team registry + delegate/subagent observability”验收证据
- **observer / peerPerspective / agentPeerMap 已补齐最小 Hermes-native 透传**：`delegate_task` 现会把 `parent_observer_session_id`、`peer_perspective`、`agent_peer_map` 透传到 `MemoryManager.on_delegation(...)`
- **workspace 级 agentPeerMap 已补齐最小 Hermes-native 持久化/恢复**：`HonchoSessionManager` 现会从 session metadata 读取 `workspaceAgentPeerMap`，并在 flush 时持续回写；observer query 会合并 workspace peer map 与当前 delegation peer map，但这仍只是最小 metadata persistence/query merge，不等于完整 canonical peer state
- 仍缺 **完整 Honcho-style observer hierarchy / workspace-level peer state / context peer semantics** 的实现说明或明确废弃说明
- capability matrix 与验收文档已补齐，但高级多智能体语义仍未完成闭环

### 仍存在的 P2
- 如需对齐 OpenClaw/Honcho 高级多智能体语义，需要新增：
  - parent observer hierarchy
  - peerPerspective 记忆读取语义
  - 完整 workspace-level canonical peer state（超出当前 `workspaceAgentPeerMap` session metadata 持久化/恢复）
  - 团队 setup 自动迁移/验收链路

## 4. 审计口径

建议统一使用以下表述：

> Hermes 已完成 OpenClaw 多智能体团队运行底座的吸收与切流，P0 范围内的 task / approval / registry / cron 已原生化并通过动态验收；delegate/subagent 骨架已具备但仅属部分吸收。OpenClaw/Honcho 历史高级多智能体语义（observer / peerPerspective / workspace-level canonical peer state / multi-agent setup 自动迁移）仍未完成对齐，因此暂不宣称全量吸收完成。

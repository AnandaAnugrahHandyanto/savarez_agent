# OpenClaw 多智能体团队吸收验收报告

> 结论先行：**Hermes 已完成 OpenClaw 多智能体团队的 Hermes-native 运行底座吸收与切流保护，但尚未达到“OpenClaw 全量多智能体团队能力 100% 吸收”状态。当前可判定为：P0 底座已落地并通过动态验收，P1/P2 仍有能力对齐与文档收口工作。**

## 1. 验收结论

- **总判断**：部分完成，已具备上线级 Hermes-native 团队底座
- **吸收完成度**：约 **70%~80%**
- **P0 结论**：**通过**
- **P1 结论**：**部分通过（最小透传已补齐，完整语义未闭环）**
- **风险等级**：中
- **切流结论**：**运行态已切到 Hermes 自有状态目录与注册表；OpenClaw 仅保留只读桥接/显式 bootstrap 用途，不参与默认写路径。**

## 2. 本次验收范围

围绕“是否吸收 OpenClaw 的多智能体团队”拆为 4 类能力：

1. **团队运行底座**
   - 任务存储
   - 审批存储
   - task/job/session/run registry
   - cron 编排
2. **切流与边界控制**
   - 默认是否仍写 OpenClaw 旧目录
   - legacy 读取是否只读
   - bootstrap 是否显式开关控制
3. **多智能体协同骨架**
   - subagent / delegate lineage
   - parent/child session 关联
   - delegation observation hooks
4. **OpenClaw 历史高级能力对齐**
   - multi-agent parent observer
   - peerPerspective
   - workspace `agentPeerMap`（Hermes 当前仅完成 `workspaceAgentPeerMap` session metadata persistence/query merge，不等于完整 canonical peer state）
   - multi-agent setup 自动迁移/自动验收

---

## 3. Capability Matrix

| 能力项 | OpenClaw/历史基准 | Hermes 当前状态 | 判断 | 证据 |
|---|---|---|---|---|
| 团队状态目录 | 旧运行态常见于 openclaw runtime/data/edict | 已切到 `HERMES_HOME/state/team` | **已吸收** | `hermes_team/paths.py` |
| 任务存储 | legacy tasks/archive | Hermes-native `TaskStore` | **已吸收** | `hermes_team/task_store.py`, `hermes_team/task_hook.py` |
| 审批存储 | legacy approvals / execution_control approvals | Hermes-native `ApprovalStore` + compat 读取 | **已吸收** | `hermes_team/approval_store.py`, `tests/test_hermes_approval_compat.py` |
| task/job/session/run 注册表 | legacy `task_run_session_registry.json` | Hermes-native registry store/api | **已吸收** | `hermes_team/registry_store.py`, `hermes_team/registry_api.py`, `tests/test_hermes_team_registry_api.py` |
| cron_upsert 调度 | 原有团队/任务调度能力 | Hermes-native `task_cron.py` | **已吸收** | `hermes_team/task_cron.py`, `tests/test_hermes_team_task_hook.py` |
| 不写 legacy 旧目录 | 用户要求避免污染 openclaw | 默认只写 Hermes state | **已吸收** | `tests/test_hermes_team_no_legacy_writes.py` |
| legacy 桥接模式 | 迁移期读取旧数据 | Read-only bridge + env flag bootstrap | **已吸收** | `hermes_team/source_bridge.py`, `tests/test_hermes_team_source_bridge.py` |
| bootstrap 默认关闭 | 避免误把 legacy 当运行时主存储 | 默认关闭，需显式 `HERMES_ENABLE_OPENCLAW_TEAM_BOOTSTRAP=1` | **已吸收** | `hermes_team/source_bridge.py` |
| delegate/subagent 能力 | OpenClaw 有多智能体层级与观察 | Hermes 有 `delegate_task`、child session lineage、memory delegation hooks | **部分吸收** | `delegate_task` 工具、`hermes_state.py`, `agent/memory_provider.py` |
| 父子 session 关联 | multi-agent hierarchy | 已有 `parent_session_id` 机制 | **部分吸收** | `hermes_state.py` |
| delegation 结果观测 | 父 agent 观测子 agent 返回 | 已有 `on_delegation(...)` | **部分吸收** | `agent/memory_provider.py`, `agent/memory_manager.py` |
| multi-agent parent observer（Honcho 语义） | openclaw-honcho 已完成项 | 已补 parent observer session 透传，但无层级 observer 编排 | **部分吸收** | `tools/delegate_tool.py`, `tests/tools/test_delegate.py`, `docs/honcho-integration-spec.md` |
| `peerPerspective` 记忆语义 | openclaw-honcho 已完成项 | 已补 delegation hook 元数据透传，并注入 Honcho search/context 查询提示；但仍未形成正式 peer context API semantics | **部分吸收** | `tools/delegate_tool.py`, `plugins/memory/honcho/__init__.py`, `plugins/memory/honcho/session.py`, `tests/tools/test_delegate.py`, `tests/agent/test_memory_provider.py`, `tests/honcho_plugin/test_session.py`, `docs/honcho-integration-spec.md` |
| workspace `agentPeerMap` | openclaw-honcho 已完成项 | 已补 delegation hook 元数据透传，并通过 Honcho session metadata `workspaceAgentPeerMap` 做 workspace 级持久化/恢复；observer query 会合并 runtime + workspace peer map，但 Hermes 当前仅完成最小 metadata persistence/query merge，不等于完整 workspace-level canonical peer state | **部分吸收（增强）** | `tools/delegate_tool.py`, `plugins/memory/honcho/__init__.py`, `plugins/memory/honcho/session.py`, `tests/tools/test_delegate.py`, `tests/agent/test_memory_provider.py`, `tests/honcho_plugin/test_session.py`, `docs/honcho-integration-spec.md` |
| multi-agent setup 自动迁移 | 官方迁移能力 | 文档仍列为 manual review | **未吸收** | `website/docs/reference/cli-commands.md` |
| OpenClaw 团队全量自动迁移 | 一键迁入全部团队协议/绑定 | 无充分证据 | **未吸收** | `docs/migration/openclaw.md`, `website/docs/reference/cli-commands.md` |

---

## 4. 关键证据

### 4.1 Hermes-native 团队写路径已落地
- `hermes_team/paths.py`
  - `get_team_state_dir()` → `HERMES_HOME/state/team`
  - 注释明确：所有 runtime team writes 必须落在这里

### 4.2 legacy 只读桥接已落地
- `hermes_team/source_bridge.py`
  - `LegacyOpenClawBridge` 文档说明：**Read-only adapter**
  - `bootstrap_team_state_from_legacy()` 默认拒绝运行
  - 必须显式设置环境变量：`HERMES_ENABLE_OPENCLAW_TEAM_BOOTSTRAP=1`

### 4.3 明确防止污染 OpenClaw
- `tests/test_hermes_team_no_legacy_writes.py`
  - 创建任务不改 legacy `tasks.json`
  - registry 更新不碰 legacy registry
  - cron_upsert 不碰 legacy tasks/registry

### 4.5 只读差异审计能力已补齐
- `hermes_team/source_bridge.py`
  - 新增 `audit_team_state_vs_legacy(workspace_root)`
  - 对比 legacy 与 Hermes 的：
    - task IDs
    - registry task IDs
    - approval task IDs
- `hermes_team/task_hook.py`
  - 新增 `audit_legacy_diff` 命令
  - 可直接输出只读 JSON 审计报告，不会写回 legacy
- `tests/test_hermes_team_audit_diff.py`
  - 覆盖 parity / missing diff / CLI output 三类场景

### 4.6 动态验收已通过
本次实际运行测试：

```bash
pytest -q \
  tests/test_hermes_team_registry_api.py \
  tests/test_openclaw_multi_agent_team_e2e.py \
  tests/test_hermes_team_audit_diff.py \
  tests/tools/test_delegate.py \
  tests/agent/test_memory_provider.py
```

结果：
- **175 passed, 10 warnings in 4.98s**

补充说明：
- `tests/test_openclaw_multi_agent_team_e2e.py` 覆盖最小团队链路：`task -> approval -> cron_upsert -> registry -> list`
- `tests/test_hermes_team_audit_diff.py` 覆盖 legacy vs Hermes team state 的只读差异审计与 CLI 输出
- `tests/tools/test_delegate.py` 新增验证：`delegate_task` 会把 `parent_observer_session_id`、`peer_perspective`、`agent_peer_map` 透传到父代理 `on_delegation(...)`
- `tests/tools/test_delegate.py` 同时验证子代理构建、隔离、父子 session lineage、观测字段与工具追踪
- `tests/agent/test_memory_provider.py` 验证父代理 `on_delegation(...)` 钩子会保留 observer / peer kwargs
- `tests/honcho_plugin/test_session.py` 验证 Honcho `search_context` / `honcho_context` 会携带 delegation observer query hints，使 `peerPerspective` / `agentPeerMap` 从“只保留元数据”提升到“查询可见”
- `tests/test_hermes_team_registry_api.py` 验证 task/job/session/run registry 的绑定与状态同步

说明：
- P0 团队底座与边界控制能力已动态通过。
- P1 中“delegate/subagent + team registry 正式 E2E 证据”与“observer/peer metadata 最小透传”现已补齐到验收证据层；本批进一步补上 Honcho 查询侧 observer/peer hints，使 `peerPerspective` / `agentPeerMap` 不再只停留在存储保留层。但 Honcho 语义级 observer hierarchy / 正式 context peer semantics / workspace peer state 仍不能据此宣称完成吸收。

---

## 5. 为什么不能宣称“已完全吸收”

以下证据直接限制了“全量吸收”口径：

### 5.1 官方迁移文档仍保留 manual review 缺口
`website/docs/reference/cli-commands.md` 明确写到：

- **Archived for manual review:** `multi-agent setup`, `channel bindings`, `hooks/webhooks`, `IDENTITY.md`, `TOOLS.md`, `BOOTSTRAP.md` ...

这意味着：
- 官方并未声明 multi-agent setup 已被 Hermes 标准迁移链路完整覆盖。

### 5.2 Honcho 规范文件列出 OpenClaw 已有但 Hermes 侧未闭环验收的多智能体能力
`docs/honcho-integration-spec.md` 记载：

Already done in openclaw-honcho:
- `lastSavedIndex` dedup
- platform metadata stripping
- **multi-agent parent observer**
- `peerPerspective` on `context()`
- tiered tool surface
- workspace `agentPeerMap`（OpenClaw 侧完整能力；Hermes 当前仅部分吸收为 `workspaceAgentPeerMap` session metadata persistence/query merge）
- self-hosted Honcho

当前无法证明这些能力都已经以 Hermes-native 方式完整替代并经过团队验收。

---

## 6. 当前切流判断

### 可确认已切流
- 任务、审批、registry、cron 的**默认运行态写路径**已经切到 Hermes 自有目录。
- OpenClaw 旧目录不再是默认写目标。
- legacy 只作为**显式 bootstrap / 审计桥接**。

### 仍未完全切流
- OpenClaw 多智能体高级协同协议（尤其 Honcho/observer/peer 语义）尚未形成完整能力对照与端到端验收闭环。

---

## 7. P0 / P1 / P2 落地清单

### P0（已完成）
- [x] 建立 Hermes-native 团队状态目录
- [x] 建立 Hermes-native registry API
- [x] 建立 Hermes-native task hook / cron upsert
- [x] 建立 Hermes-native approval store 与兼容读取
- [x] legacy 只读桥接
- [x] 默认禁用 legacy bootstrap
- [x] 增加“不写 legacy”测试
- [x] 动态测试通过（35 passed）

### P1（当前状态）
- [x] 建立 **OpenClaw 团队能力 → Hermes 对应实现** 的正式映射表（`docs/architecture/openclaw-team-capability-matrix.md`）
- [x] 对 **delegate/subagent + task/approval/registry** 做端到端流程验收（`tests/test_openclaw_multi_agent_team_e2e.py` + `tests/tools/test_delegate.py` + `tests/agent/test_memory_provider.py`）
- [x] 明确 multi-agent parent observer / peerPerspective / agentPeerMap 的当前实现状态（最小元数据透传已补齐，完整语义仍未闭环）
- [x] 补充文档：哪些已吸收、哪些未吸收、哪些故意保留为只读桥接
- [x] 固化高级多智能体语义边界说明（`docs/architecture/openclaw-advanced-multi-agent-semantics.md`）

### P2（增强项 / 仍待处理）
- [x] 若需要兼容历史迁移，增加只读审计命令输出 legacy 与 Hermes 差异（`task_hook.py audit_legacy_diff` + `audit_team_state_vs_legacy(...)`）
- [x] 将 capability matrix 固化到 docs 或 runbook
- [x] 为“团队切流完成”增加单独 smoke test / CI job

---

## 8. 推荐口径（对内/对外统一说法）

建议统一表述为：

> Hermes 已完成 OpenClaw 多智能体团队的运行底座吸收与写路径切流；任务、审批、registry、cron 等 P0 能力已原生化并通过动态验收。OpenClaw 历史高级多智能体语义（如 observer / peer / setup 迁移）仍在能力对齐范围内，暂不宣称全量吸收完成。

---

## 9. 最终建议

### 现在可以说的
- **可以说：已完成 Hermes-native 团队底座吸收并切流成功。**

### 现在不能说的
- **不能说：OpenClaw 多智能体团队已 100% 完整吸收。**

### 下一步建议
1. 若后续要对齐 Honcho 语义，补 `observer hierarchy / peer context semantics / workspace canonical peer state beyond Honcho session metadata` 的产品取舍文档与实现方案
2. 对 `docs/migration/openclaw.md` 与 `website/docs/guides/migrate-from-openclaw.md` 做逐条对表，明确哪些团队语义永久归档、哪些准备 Hermes-native 吸收
3. 在完成上述高级语义闭环前，持续使用“P0 已吸收、整体部分吸收”的对外口径

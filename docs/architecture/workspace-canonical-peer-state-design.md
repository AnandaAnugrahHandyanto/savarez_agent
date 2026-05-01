# Workspace Canonical Peer State 设计边界

## 一句话结论
当前 Hermes 已完成 `workspaceAgentPeerMap` 基于 Honcho session metadata 的**最小持久化/恢复闭环**，足以支撑现阶段 delegation observer query 合并；但**不把这层 metadata 继续包装成“完整 workspace-level canonical peer state”**。后续若要扩展，应作为独立能力立项，而不是隐式扩大现有实现口径。

## 已落地事实
- delegation 完成后，父代理 memory hook 可接收 `peerPerspective` / `agentPeerMap` / `summary`
- `HonchoSessionManager` 会把 `workspaceAgentPeerMap` 写回到 session metadata，并在后续恢复
- observer query 会合并：
  - 当前 delegation peer map
  - 已持久化的 workspace peer map
- 现有实现目标是：让父代理在后续 Honcho context/tool 读取中保留最小 observer block / summary 语义

## 明确不宣称的内容
以下能力**不属于**当前实现合同：
1. 完整 Honcho-style observer hierarchy
2. `peerPerspective` 独立的正式 context query semantics
3. 独立于 Honcho session metadata 的 workspace canonical peer store
4. 跨 session / 跨 workspace 的团队拓扑治理与回放
5. multi-agent setup 自动重建或自动验收

## 为什么不直接升级为 canonical store
### 1. 当前需求只需要“最小可恢复 peer map”
目前已验证的闭环是 observer query 补全与父代理后续上下文可见性，不需要额外引入新的 team-state 存储层。

### 2. 过早抽象会放大口径风险
如果把 `workspaceAgentPeerMap` metadata 直接表述为 canonical store，文档与对外口径会误导为：
- 已具备完整 observer hierarchy
- 已具备可独立查询/治理的 workspace peer state
- 已完成 OpenClaw/Honcho 高级多智能体语义的等价替代

这些都不成立。

### 3. 新状态层会引入治理问题
若新增 `HERMES_HOME/state/team/...` 级别的 canonical peer store，需要同步定义：
- schema 与版本迁移
- flush / restore / conflict resolution
- session metadata 与 team store 的主从关系
- 验收、审计、回滚与兼容策略

在这些问题未定前，不应把现有 metadata persistence 继续外推。

## 推荐正式口径
> Hermes 已完成 `workspaceAgentPeerMap` 基于 Honcho session metadata 的最小持久化/恢复闭环，并在 observer query 中与当前 delegation peer map 合并；但这仍不等于完整的 workspace-level canonical peer state，也不代表 OpenClaw/Honcho 高级 observer 语义已全部吸收。

## 后续立项触发条件
只有在同时出现以下至少两项时，才建议单独立项 canonical peer state：
- 需要跨 session 追踪稳定团队拓扑
- 需要独立于 Honcho context 的 peer-state 查询接口
- 需要 observer hierarchy 的层级治理/回放
- 需要 multi-agent setup 自动验收依赖稳定 peer-state source of truth

## 若后续立项，最小设计问题清单
1. canonical peer state 的唯一主存储在哪里
2. session metadata 与 canonical store 谁是 source of truth
3. delegation runtime peer map 如何 merge / override persisted state
4. 何时 flush，何时裁剪，何时失效
5. 如何给出不会误导外部的验收口径

## 当前决策
- **保留现状**：继续使用 `workspaceAgentPeerMap` session metadata persistence 作为最小闭环
- **不扩张口径**：文档统一表述为“workspace-level canonical peer state beyond session metadata 仍未完成”
- **不新增存储实现**：本轮不引入新的 canonical team-state store

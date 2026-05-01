# Advanced Multi-Agent Semantics Boundary Note

> 结论先行：Hermes 已具备 **delegate/subagent + parent/child session lineage + delegation observer metadata 透传** 的最小可验收骨架，但没有实现 OpenClaw/Honcho 的完整高级多智能体语义闭环。本文用于明确哪些能力已吸收、哪些只是最小兼容、哪些仍明确未做。

## 1. 当前已具备的最小骨架

### 已实现
- `delegate_task` 子代理隔离执行
- `parent_session_id` 持久化父子 session lineage
- `MemoryManager.on_delegation(...)` 父代理委托结果回灌
- 最小 observer / peer 元数据透传：
  - `parent_observer_session_id`
  - `peer_perspective`
  - `agent_peer_map`

### 代码落点
- `tools/delegate_tool.py`
- `agent/memory_manager.py`
- `agent/memory_provider.py`
- `hermes_state.py`
- `tests/tools/test_delegate.py`
- `tests/agent/test_memory_provider.py`

## 3. 最小实现边界（本次正式口径）

### 3.1 `parent_observer_session_id`
- 语义：**父代理对本次 delegation observation 的来源 session 标识**
- 当前用途：仅作为父代理 memory/provider hook 的观测元数据
- 明确不代表：
  - 独立 observer 实体 ID
  - 多层 observer graph 节点 ID
  - 可单独恢复/回放的 observer runtime

### 3.2 `peer_perspective`
- 语义：**对子代理结果附带的 peer 视角标签/提示字符串**
- 当前用途：仅允许 provider 在 `on_delegation(...)` 中记录、索引或审计
- 明确不代表：
  - 正式的 `context()` 读取协议参数
  - 跨轮可复用的 peer-context contract
  - provider 必须支持的查询接口

### 3.3 `agent_peer_map`
- 语义：**本次 delegation observation 附带的 agent→peer 临时映射快照**
- 当前用途：仅作为父代理观测面的附加上下文
- 明确不代表：
  - workspace 级 canonical peer map store
  - 多轮共享协作状态
  - 团队 runtime 的正式依赖源

## 4. 当前明确未闭环的高级语义

### 4.1 Observer hierarchy

OpenClaw/Honcho 语义中的 observer hierarchy 不只是“父代理知道子代理 session id”。
它通常包含：
- 父 observer 对多个 child observer 的层级编排
- 跨 agent 层级的统一观测视图
- observer 自身的持续状态与回放语义

**Hermes 当前状态：**
- 仅透传 `parent_observer_session_id`
- 没有独立 observer graph / hierarchy store
- 没有多层 observer 编排器

**结论：** 部分吸收，不等于完整 observer hierarchy。

### 4.2 `peerPerspective` context semantics

OpenClaw/Honcho 的 `peerPerspective` 不是单纯的 metadata；其价值在于：
- context 读取阶段可按 peer 视角组织记忆/上下文
- agent 在调用 context() 时能看到来自指定 peer 的透视信息

**Hermes 当前状态：**
- `peer_perspective` 只在 delegation hook 中透传
- 未进入独立 context 读取协议
- 没有 provider 级 peer-context query contract

**结论：** 仅最小透传，未形成 context semantics。

### 4.3 Workspace-level canonical peer state boundary

OpenClaw/Honcho 的 `agentPeerMap` 更接近 workspace 级协同状态：
- agent 与 peer 身份映射可复用
- 多轮任务中可持续使用
- 可作为 observer / context / routing 的共享依赖

**Hermes 当前状态：**
- `agent_peer_map` 已通过 Honcho session metadata `workspaceAgentPeerMap` 做最小 workspace 级持久化/恢复
- observer query 会合并 runtime delegation peer map 与已恢复的 workspace peer map
- 但仍无 `HERMES_HOME/state/team/` 下的 canonical peer map store，也未成为团队 runtime 的正式依赖源

**结论：** 已完成最小持久化闭环，但仍不构成完整的 workspace-level canonical peer state。

## 5. 为什么当前不继续直接实现

当前任务目标是：
1. 完成 Hermes-native 团队底座吸收
2. 完成默认写路径切流
3. 保持不污染 openclaw
4. 给出可验收、可切流的最小闭环

如果直接把 Honcho 高级语义一次性搬进来，会引入：
- 新的 canonical state schema
- 新的上下文读取协议
- 新的 observer graph 生命周期管理
- 更高的迁移兼容复杂度

在没有明确产品边界前，贸然实现会增加协议债务。

## 4. 推荐后续实现顺序

### P1：只补边界，不扩协议
- 保持当前最小 metadata 透传
- 保持验收文档明确“不宣称完整 observer/peer 语义”
- 增加只读 audit/diagnostics 能力

### P2：若确认需要对齐 Honcho
建议按以下顺序推进：

1. **observer hierarchy state model**
   - 定义 canonical observer graph schema
   - 明确与 session lineage 的关系

2. **peer context query contract**
   - 定义 memory provider 如何按 peer 视角读取 context
   - 避免把临时 metadata 误当正式协议

3. **workspace agent peer map store**
   - 在 `HERMES_HOME/state/team/` 下定义 Hermes-native peer map store
   - 明确更新源、读取方、生命周期

4. **acceptance + migration**
   - 为上述 3 个能力分别补动态测试
   - 再决定是否进入自动迁移/切流口径

## 5. 当前正式口径

> Hermes 已完成 OpenClaw 多智能体团队运行底座的吸收与默认写路径切流；delegate/subagent 的最小观测骨架也已具备。OpenClaw/Honcho 的高级多智能体语义（observer hierarchy、peer context semantics、workspace-level canonical peer state beyond Honcho session metadata）仍未完成 Hermes-native 闭环，因此当前维持“P0 已吸收、整体部分吸收”的正式判断。

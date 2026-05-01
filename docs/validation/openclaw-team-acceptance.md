# OpenClaw 多智能体团队 P1 验收补充

## 范围

本补充验收只覆盖 P1 层面的两个问题：

1. Hermes 是否已经具备 **delegate/subagent 与团队状态底座之间的最小闭环骨架**
2. Hermes 是否已经吸收 **observer / peerPerspective / agentPeerMap / multi-agent setup** 这类 OpenClaw/Honcho 高级多智能体语义（其中 Hermes 对 `agentPeerMap` 当前仅完成 `workspaceAgentPeerMap` session metadata persistence/query merge，不等于完整 canonical peer state）

## 结论

- **delegate/subagent + parent/child session + delegation observation hook：部分吸收，已有骨架证据。**
- **observer / peerPerspective / agentPeerMap：已补齐 delegation metadata 透传、父代理观测面挂载，以及 Honcho memory provider 的最小 observer context 注入与记忆保留闭环；父代理收到 child 结果后，后续 Honcho context/tool 读取可继续保留 peerPerspective + agentPeerMap + summary。workspace 级 `agentPeerMap` 现已通过 `workspaceAgentPeerMap` 写回/恢复到 Honcho session metadata，并在 observer query 中与当前 delegation peer map 合并。Hermes 当前仅完成最小 metadata persistence/query merge，仍未形成完整 Honcho-style observer hierarchy / workspace-level canonical peer state。**
- **新增只读差异审计能力：已支持对比 legacy 与 Hermes team state，不写回 legacy。**
- **multi-agent setup 自动迁移：未吸收。**

## 代码证据

### 1. delegate/subagent 骨架已存在
- `tools/delegate_tool.py`
  - 子代理创建时明确设置：
    - `skip_memory=True`
    - `skip_context_files=True`
    - `parent_session_id=getattr(parent_agent, 'session_id', None)`
  - 说明 Hermes 已具备最小父子代理 lineage 与隔离执行模型。

### 2. 父代理可观测子代理结果
- `tools/delegate_tool.py`
  - 子代理完成后调用：`parent_agent._memory_manager.on_delegation(...)`
- `agent/memory_provider.py`
  - 定义 `on_delegation(task, result, child_session_id=...)`
- `agent/memory_manager.py`
  - 负责把 delegation observation 分发给 memory provider

### 3. parent/child session 已落库
- `run_agent.py`
  - `AIAgent(... parent_session_id=...)`
- `hermes_state.py`
  - `sessions` 表包含 `parent_session_id`
  - 提供 parent/child session chain 的持久化基础

### 4. Hermes 尚未具备 OpenClaw/Honcho 高级多智能体语义闭环
- `docs/honcho-integration-spec.md`
  - 已更新为：
    - Hermes 侧已补 `workspaceAgentPeerMap` session metadata 持久化/恢复
    - observer query 会合并 runtime delegation peer map 与 workspace peer map
  - 但文档仍保留：
    - `Multi-agent | Single-agent only`
    - OpenClaw/Honcho 已有：
      - `Multi-agent observer hierarchy`
      - `peerPerspective` on `context()`
      - workspace `agentPeerMap`（OpenClaw 已有完整能力；Hermes 当前仅部分吸收为 `workspaceAgentPeerMap` session metadata persistence/query merge）
- 说明当前闭环仍属“最小 Hermes-native 吸收”，不是完整 OpenClaw/Honcho 高级多智能体语义对齐。

### 5. 自动迁移仍保留 manual review
- `website/docs/reference/cli-commands.md`
  - 明确列出 archived/manual review：
    - `multi-agent setup`
    - `channel bindings`
    - `hooks/webhooks`
    - `IDENTITY.md`
    - `TOOLS.md`
    - `BOOTSTRAP.md`

## 验收口径

因此，P1 的正确结论应为：

> Hermes 已具备 delegate/subagent 的最小协同骨架，并能把子代理结果通过父子 session 与 delegation hook 纳入观测面；但这不等于已完整吸收 OpenClaw/Honcho 的高级多智能体团队语义。observer / peerPerspective / agentPeerMap / multi-agent setup 自动迁移目前仍未完成。

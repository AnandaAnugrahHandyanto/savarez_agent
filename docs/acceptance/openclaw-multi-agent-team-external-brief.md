# OpenClaw 多智能体团队吸收对外汇报稿

## 一句话结论
Hermes 已完成 OpenClaw 多智能体团队 **P0 运行底座** 的 Hermes-native 吸收与默认写路径切流；当前整体判断为 **部分吸收**，尚未达到 OpenClaw/Honcho 高级多智能体语义的 100% 对齐。

## 已完成范围
- 团队状态目录切到 `HERMES_HOME/state/team`
- task / approval / registry / cron 已形成 Hermes-native 运行底座
- OpenClaw legacy 目录不再作为默认写路径
- legacy 数据桥接仅保留为 **只读审计 / 显式 bootstrap**
- delegate/subagent 已具备最小骨架：隔离执行、parent/child session lineage、delegation observation hook
- 迁移链路已明确区分：**可直接导入的 team-adjacent 配置** 与 **archived/manual review 的团队语义**

## 当前进展
- 已完成 Hermes-native 最小 observer 语义闭环：delegation 完成后，父代理 memory hook 可保留 `peerPerspective` / `agentPeerMap` / `summary`，并在 Honcho 首轮 context 与后续工具读取中继续可见。
- 已补只读差异审计：可对比 legacy vs Hermes team state
- 官方迁移/FAQ/matrix 文档口径已对齐：不再暗示 OpenClaw 团队拓扑会被一键自动重建

## 当前不能宣称完成的范围
- 完整 observer hierarchy
- `peerPerspective` 的正式 context query semantics
- 完整 Honcho-style workspace-level canonical peer state（超出当前 `workspaceAgentPeerMap` session metadata 持久化/恢复）
- multi-agent setup 自动迁移 / 自动验收
- channel bindings / hooks-webhooks 的团队 wiring 自动迁移

## 迁移边界（对外必须统一）
### 当前会直接导入
- `AGENTS.md`
- agent defaults
- session reset policies
- 其他兼容的用户/配置数据（skills、memories、provider/platform config 等）

### 当前不会自动重建
- OpenClaw `multi-agent setup`
- legacy `channel bindings` / per-chat routing
- `hooks/webhooks` 团队 wiring
- OpenClaw/Honcho 高级团队语义（observer hierarchy / peerPerspective / workspace-level canonical peer state beyond `workspaceAgentPeerMap` session metadata）

### 当前正式口径
> Hermes has completed absorption of the OpenClaw team runtime foundation and moved default writes onto Hermes-native state. The migration command imports compatible user/config data, but advanced multi-agent setup and legacy team-binding semantics are still archived for manual review rather than claimed as fully auto-migrated.

## 动态验收结果
已执行 smoke 子集：

```bash
./scripts/openclaw_team_absorption_smoke.sh
```

结果：
- **175 passed, 10 warnings**

## 风险口径
- P0 已可作为 Hermes 自有团队底座运行
- 高级多智能体协议仍需单独立项，不宜对外宣称“全量吸收完成”
- 迁移命令当前更适合表述为：**导入兼容配置 + 归档复杂团队语义供人工复核**

## 统一对外表述
> Hermes 已完成 OpenClaw 多智能体团队运行底座的吸收与默认写路径切流；task / approval / registry / cron 已 Hermes-native 化并通过动态验收。迁移命令会导入兼容的用户/配置数据，但 multi-agent setup、channel bindings、hooks/webhooks 以及 observer / peerPerspective / agentPeerMap 等高级团队语义仍属 archived/manual review 或部分吸收，当前不宣称 100% 全量自动迁移完成。

## 对外答法边界
- 可以说：**Hermes 已完成 P0 团队底座吸收，并已切离 OpenClaw 默认写路径。**
- 可以说：**`hermes claw migrate` 会导入 team-adjacent 配置，如 `AGENTS.md`、agent defaults、session reset policies。**
- 不可以说：**Hermes 会一键重建 OpenClaw multi-agent setup、per-chat bindings 或 hooks/webhooks 团队 wiring。**
- 不可以说：**OpenClaw/Honcho 的 observer hierarchy、peerPerspective context semantics、完整 workspace-level canonical peer state 已 100% 自动迁入 Hermes。**

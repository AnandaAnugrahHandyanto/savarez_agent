# Hermes 官方 Skills 吸收盘查（截至当前运行态）

> 结论先行：Hermes 已经吸收了一批对自身最有价值、最容易工程化落地的官方 skills 模式；当前最值得继续吸收的，不是“把网站上的 skill 全量搬过来”，而是继续把 **可复用的产品级能力模式** 落到 Hermes 自有实现、测试和文档中。基于当前代码与文档证据，优先级最高的新增吸收机会仍集中在 **Honcho/openclaw 反哺能力** 与 **迁移兼容自动化**，而不是简单增加更多第三方任务型 skill。

## 1. 已落地吸收的高价值能力模式

### 1.1 多智能体团队底座（已吸收）
- Hermes-native team state 已独立落到 `HERMES_HOME/state/team`
- task / approval / registry / cron 已形成自有实现
- legacy OpenClaw 仅保留只读 bridge / bootstrap / audit 角色

关键证据：
- `hermes_team/paths.py`
- `hermes_team/task_store.py`
- `hermes_team/approval_store.py`
- `hermes_team/registry_store.py`
- `hermes_team/task_cron.py`
- `tests/test_openclaw_multi_agent_team_e2e.py`
- `tests/test_hermes_team_no_legacy_writes.py`

### 1.2 多智能体最小观测语义（部分吸收）
已把 OpenClaw/Honcho 中真正有价值的最小 delegation observer 元数据纳入 Hermes：
- `parent_observer_session_id`
- `peer_perspective`
- `agent_peer_map`

关键证据：
- `tools/delegate_tool.py`
- `tests/tools/test_delegate.py`
- `tests/agent/test_memory_provider.py`

### 1.3 只读差异审计/迁移验收能力（已吸收）
已新增 Hermes-native 审计链路，不改 OpenClaw 本体：
- `audit_team_state_vs_legacy(...)`
- `task_hook.py audit_legacy_diff`

关键证据：
- `hermes_team/source_bridge.py`
- `hermes_team/task_hook.py`
- `tests/test_hermes_team_audit_diff.py`

### 1.4 Honcho 工具分层与异步预取（已吸收）
Hermes 侧已具备官方 skills 文档值得保留的“能力模式”：
- 记忆工具分层：`honcho_profile` / `honcho_search` / `honcho_context` / `honcho_conclude`
- context/dialectic 预取与缓存
- write frequency 控制与异步 flush

关键证据：
- `plugins/memory/honcho/__init__.py`
- `plugins/memory/honcho/session.py`
- `tests/honcho_plugin/test_session.py`
- `tests/honcho_plugin/test_async_memory.py`

## 2. 当前最值得继续吸收的能力

这些不是“网站上随便挑几个 skill 搬过来”，而是结合官方 skill 思路后，对 Hermes 长期价值最高的能力空白。

### P1-1. Honcho message dedup（`lastSavedIndex` 等价能力）
当前 Honcho 写入主要依赖本地 `_synced` 标记和即时 flush。
这能工作，但没有形成 OpenClaw 风格的 **会话级已保存索引/幂等保护**。

为什么值得吸收：
- 重连 / retry / 并发 flush 场景下更稳
- 可把“本地消息状态”升级为“会话级同步水位”
- 属于低风险高收益工程增强

当前证据：
- `plugins/memory/honcho/session.py` 中 `_flush_session()` 以 `_synced` 为主
- 未见 `lastSavedIndex` 或等价 session metadata waterline

### P1-2. Platform metadata stripping
官方 spec 明确把它列为 openclaw-honcho 已有、Hermes 应吸收的项。
当前 Hermes 代码里已存在大量平台适配层，但未见 **统一的 Honcho 写入前平台元数据剥离层** 成为正式能力口径。

为什么值得吸收：
- 降低 Telegram / Feishu / Discord 噪声进入长期记忆
- 降低 provider 侧脏数据
- 能形成明确的消息归一化边界

### P1-3. Workspace 级 observer / peer state
目前只是 delegation 结果回灌时透传 metadata。
还没有：
- observer graph store
- workspace peer map canonical store
- peer context query contract

为什么值得吸收：
- 决定 Hermes 是否能从“最小兼容”升级到“真正闭环的高级多智能体语义”

### P1-4. Multi-agent setup 自动迁移
官方迁移文档仍把这类能力留在 manual review。
Hermes 现在已有 runtime team state 与 bridge/audit 基础，下一步最应该补的是：
- 只读发现 legacy 团队配置
- 转译到 Hermes-native state / docs / acceptance
- 自动生成验收报告

## 3. 当前不建议优先吸收的项

### P3-外围生态兼容项
- UI/identity migration
- logging migration
- skills registry config migration
- plugins migration
- memory backend(QMD) migration

理由：
- 不属于当前“团队底座吸收 + 迁移闭环”的主线路径
- 对当前 Hermes 的直接收益低于 dedup / metadata normalization / advanced team semantics

## 4. 现阶段正式判断

### 已经可以确认吸收的
- 多智能体团队运行底座
- 只读迁移桥接与差异审计
- delegate/subagent 最小 observer metadata 透传
- Honcho 的工具分层、异步预取、可控写频等高价值模式

### 仍应继续吸收的
- session-level message dedup / waterline（Hermes 已有最小 `lastSavedIndex` + `_synced` 实现，但尚缺 replay-safe 专项验收口径）
- platform metadata stripping
- observer hierarchy / peer context semantics / workspace-level canonical peer state beyond `workspaceAgentPeerMap` session metadata
- multi-agent setup 自动迁移

## 5. 推荐执行顺序

1. **P1：Honcho dedup + metadata normalization**
2. **P1：observer/peer/workspace state 的 Hermes-native schema 设计**
3. **P1：multi-agent setup 只读迁移器 + 验收产物生成**
4. **P2：再决定是否扩展更多外围 skill/插件迁移**

## 6. 当前口径

> Hermes 不需要把官方 skills 网站上的条目机械式照搬；真正值得吸收的是其中可沉淀为自有 runtime、memory、migration、acceptance 的工程能力模式。按当前代码证据，P0 团队底座、最小 delegation observability、Honcho 分层工具与异步预取已经吸收；接下来最值得继续吸收的是 Honcho dedup、平台元数据清洗、高级 observer/peer 语义，以及 multi-agent setup 自动迁移。

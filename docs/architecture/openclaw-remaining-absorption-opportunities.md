# OpenClaw 剩余可吸收能力审计

> 结论先行：在 OpenClaw 多智能体团队底座之外，Hermes 仍有一批 **可继续吸收但尚未闭环** 的能力。这些能力主要来自两类来源：
> 1. 官方迁移链路中被标记为 **manual review / archived** 的项
> 2. `docs/honcho-integration-spec.md` 中明确写出的 **openclaw-honcho 已有、Hermes should adopt** 的项

## 1. 剩余可吸收项总表

| 能力 | 来源 | 当前 Hermes 状态 | 吸收价值 | 优先级 |
|---|---|---|---|---|
| `lastSavedIndex` message dedup | `docs/honcho-integration-spec.md` | 已补 replay-safe 专项验收：覆盖重复 flush 不重放、reconnect 后只发增量、async retry 不重放成功批次；实现仍是 `lastSavedIndex` + `_synced` 双层水位线，而非额外去重存储 | 降低重复写入 Honcho / 防止重复同步 | P1 |
| platform metadata stripping | `docs/honcho-integration-spec.md` | 已有 Hermes-native 最小实现：`_sanitize_message_metadata()` 通过 allowlist 保留 `channel/delivery/platform/thread/tags/context/chat_type/kind/source/labels/safe` 等结构化字段，并显式剥离 `session_id/user_id/agent_id/trace_id/request_id/raw_event/attachments/file_path` 等敏感或平台噪声字段；但尚无独立专项验收文档 | 降低平台噪音、减少脏数据进入记忆层 | P1 |
| Multi-agent observer hierarchy | `docs/honcho-integration-spec.md` | 仅有 parent/child lineage + delegation metadata | 补齐真正团队层级观测闭环 | P1 |
| `peerPerspective` on `context()` | `docs/honcho-integration-spec.md` | 仅 metadata 透传，未进入 context 协议 | 补齐 peer 视角上下文检索能力 | P1 |
| Workspace-level canonical peer state beyond `workspaceAgentPeerMap` session metadata | `docs/honcho-integration-spec.md` | 已有 `workspaceAgentPeerMap` session metadata 持久化/恢复与 observer query merge，但没有独立 canonical store | 只有在需要跨 session 团队拓扑治理时才值得单独立项 | P1 |
| Tiered tool surface (fast/LLM) | `docs/honcho-integration-spec.md` | Hermes Honcho 侧已有 recall/context 路径，但未按 OpenClaw 风格固化为更明确分层审计口径 | 提升工具层分层清晰度与成本控制 | P2 |
| hooks/webhooks migration | `website/docs/reference/cli-commands.md` | 仍是 manual review | 减少迁移人工收口成本 | P2 |
| channel bindings migration | `website/docs/reference/cli-commands.md` | 仍是 manual review | 补齐多渠道团队运行迁移能力 | P2 |
| multi-agent setup migration | `website/docs/reference/cli-commands.md` | 明确未吸收 | 补齐团队初始化与验收自动化 | P1 |
| IDENTITY.md / TOOLS.md / BOOTSTRAP.md import strategy | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 统一工作区级 agent protocol 兼容策略 | P2 |
| Cron jobs migration | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 迁移后续运营/自动化连续性 | P2 |
| plugins migration | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 减少 OpenClaw 插件断档 | P3 |
| skills registry config migration | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 降低技能中心切换成本 | P3 |
| logging migration | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 保留历史排障/审计习惯 | P3 |
| UI/identity migration | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 界面/身份连续性 | P3 |
| memory backend (QMD) migration | `website/docs/reference/cli-commands.md` | 仍是 archived/manual review | 兼容旧记忆后端生态 | P3 |

## 2. 我们已经确认可直接继续吸收的高价值项

### P1-1. `lastSavedIndex` message dedup
- 价值：避免重复把同一批消息写入 Honcho 或其他远端记忆层。
- 当前证据：
  - `plugins/memory/honcho/session.py` 在 `get_or_create(...)` 时会从 Honcho session metadata 读取 `lastSavedIndex`，异常值会归一化为当前 message count
  - `_flush_session(...)` 会从 `last_saved_index` 开始截取候选消息，只同步未标记 `_synced` 的消息
  - flush 成功后会回写 `lastSavedIndex` / `messageCount` 到 Honcho session metadata
  - 已补 replay-safe 专项测试：
    - `tests/honcho_plugin/test_async_memory.py::TestLastSavedIndexWaterline::test_repeated_flush_does_not_resend_same_batch`
    - `tests/honcho_plugin/test_session.py::TestManagerHonchoMetadata::test_get_or_create_session_reconnect_uses_last_saved_index_for_incremental_flush`
    - `tests/honcho_plugin/test_async_memory.py::TestAsyncWriterRetry::test_async_retry_keeps_successful_batches_from_replaying`
- 边界判断：
  - Hermes 已具备 **最小 `lastSavedIndex` + `_synced` 双保险去重水位线**
  - 现已具备 replay-safe 的定向验收证据，但仍不应夸大为额外的 canonical dedup store
- 关键落点：
  - `plugins/memory/honcho/session.py`
  - `tests/honcho_plugin/test_session.py`
  - `tests/honcho_plugin/test_async_memory.py`

### P1-2. platform metadata stripping
- 价值：把 Telegram / Feishu / Discord 等平台噪声字段从记忆写入路径剥离，减少污染长期记忆。
- 当前证据：
  - `plugins/memory/honcho/session.py` 中 `_sanitize_message_metadata()` 统一清洗消息 metadata
  - `_SENSITIVE_MESSAGE_KEYS` 会显式剥离 `session_id`、`user_id`、`agent_id`、`trace_id`、`request_id`、`raw_event`、`attachments`、`attachment`、`file_path`、`filepath`、`path` 等敏感/平台噪声字段
  - `_STRUCTURED_METADATA_KEYS` / `_MESSAGE_METADATA_ALLOWLIST` 仅保留 `channel`、`delivery`、`platform`、`thread`、`tags`、`context`、`chat_type`、`kind`、`source`、`labels`、`safe`、`workspaceAgentPeerMap` 等结构化安全字段
  - `HonchoSession.add_message(...)` 只透传上述结构化字段；`get_or_create(...)` 读取 Honcho session metadata 后也会再次走同一清洗链路
- 边界判断：
  - Hermes 已经具备 **统一 metadata allowlist + sensitive key stripping** 的最小实现
  - 当前缺口不是“完全没有实现”，而是“尚无独立专项验收与对外验收文档口径”
- 适合 Hermes-native 落点：
  - 已落在进入 Honcho 写入前的 message normalization 层
  - 若后续补强，应优先增加专项测试/验收文档，而不是重造第二套 stripping 管线

### P1-3. observer hierarchy / peerPerspective / workspace-level canonical peer state
- 价值：这是多智能体团队“高级语义闭环”的核心，不补就一直只能叫“部分吸收”。
- 当前状态：
  - `parent_observer_session_id` / `peer_perspective` / `agent_peer_map` 已能透传到 `on_delegation(...)`
  - `workspaceAgentPeerMap` 已可写回/恢复到 Honcho session metadata，并在 observer query 中与 runtime delegation peer map 合并
  - 但没有 canonical observer graph / peerPerspective 独立 context 语义 / 独立于 session metadata 的 workspace canonical peer store
- 边界判断：
  - 当前已完成的是**最小 metadata persistence 闭环**
  - 当前未完成的是**完整 workspace-level canonical peer state**
- 若后续单独立项，才考虑 Hermes-native 落点：
  - `HERMES_HOME/state/team/observer_graph.json`
  - `HERMES_HOME/state/team/agent_peer_map.json`
  - memory provider 的 peer-context contract
- 设计边界见：`docs/architecture/workspace-canonical-peer-state-design.md`

### P1-4. multi-agent setup migration
- 价值：这是把“部分吸收”推进到“更完整团队吸收”的关键迁移能力。
- 当前状态：官方文档仍标记 manual review。
- 吸收方向：
  - 不直接改 OpenClaw
  - 在 Hermes migration pipeline 中增加只读发现 + Hermes-native bootstrap/import

## 3. 中优先级可吸收项

### P2-1. hooks/webhooks / channel bindings migration
- 原因：和团队运行密切相关，但不属于团队底座最小闭环。
- 吸收方式：
  - 做 Hermes-native 兼容导入层
  - 不把 OpenClaw binding/schema 原样搬过来

### P2-2. Cron jobs migration
- 原因：会影响迁移后自动化连续性。
- 当前 Hermes 已有 `cronjob` 能力，因此更适合做“迁移映射器”，而不是沿用 OpenClaw runtime 数据格式。

### P2-3. IDENTITY.md / TOOLS.md / BOOTSTRAP.md import strategy
- 原因：这些是 agent workspace protocol 文件，吸收价值在于兼容旧工作区约定。
- 边界：
  - 应转译为 Hermes-native identity/tool/bootstrap 约束
  - 不应继续污染 OpenClaw workspace 文件本体

## 4. 低优先级可吸收项

### P3
- plugins migration
- skills registry config migration
- logging migration
- UI/identity migration
- memory backend (QMD) migration

原因：这些更多是外围生态兼容，不是当前“团队吸收”主线的 blocking item。

## 5. 正式判断

当前还能继续吸收的能力，**有，而且不少**。
但如果按价值排序，最值得继续做的是：

1. `lastSavedIndex` message dedup
2. platform metadata stripping
3. observer hierarchy
4. `peerPerspective` context semantics
5. workspace-level canonical peer state beyond `workspaceAgentPeerMap` session metadata
6. multi-agent setup migration

其中 **3/4/5/6** 决定 Hermes 能否从“P0 已吸收、整体部分吸收”继续往上推；
而 **1/2** 是低风险高收益的工程性增强，适合优先落地。

## 6. 建议对外口径

> Hermes 在 OpenClaw 多智能体团队底座之外，仍有一批高价值能力可继续吸收，主要集中在消息去重、平台元数据清洗、多智能体 observer/peer 高级语义，以及 multi-agent setup 迁移自动化。当前这些能力尚未完成 Hermes-native 闭环，因此仍归类为后续吸收范围，而非已完成项；其中 `workspaceAgentPeerMap` 仅代表最小 metadata persistence，不能等同于完整 workspace-level canonical peer state。

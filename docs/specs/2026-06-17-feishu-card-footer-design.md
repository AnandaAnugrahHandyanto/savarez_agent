# 飞书卡片消息 + 状态栏 Footer 设计

**日期**: 2026-06-17
**作者**: 小晴初 + Claude
**状态**: 已确认，待实施
**分支**: `feat/feishu-card-footer`

---

## 1. 产品核心功能 + 核心目标

**产品功能**：Hermes 飞书 bot 的所有回复从纯文本升级为交互卡片。卡片底部显示运行时状态栏（模型、tokens、费用、耗时、git 分支），流式输出过程中实时提示当前工具调用状态。多个群聊并行开发时，每个群独立显示自己 session 的上下文。

**核心目标**：对齐 NanoClaw 飞书 bot 的卡片体验——用户在飞书群里能一眼看到 bot 当前在做什么、用的什么模型、花了多少 token/钱、在哪个分支上工作。

**驱动力**：Hermes 飞书 bot 刚接入，当前回复是纯文本，缺乏 NanoClaw 已有的可观测性（token 消耗、费用、git 上下文、工具调用过程可视化）。多群并行开发场景下，用户无法区分各群的工作状态。

## 2. 非目标

- ❌ 其他平台（Telegram/Discord/Slack）的卡片化——本次只改飞书
- ❌ 卡片交互按钮（点赞/反馈等）——只做展示型卡片
- ❌ 历史消息迁移——已发送的纯文本消息不追溯
- ❌ 自定义 footer 字段配置——先固定字段集，后续按需开放

## 3. 架构决策

### D1: 实现层级 — Adapter 层拦截

**选择**: 在 `FeishuAdapter` 内部完成卡片包装，上游（run.py、footer builder）无感知。

**理由**: 
- 卡片是飞书特有的消息格式，不应污染 gateway 的平台无关抽象
- 复用现有 send/retry/fallback 路径
- 其他平台不受影响

### D2: 卡片生命周期 — 单卡片全程复用

**选择**: 收到消息后立即创建一张 ACK 卡片，后续所有更新通过 `patch`（全量替换）同一张卡片。

**理由**: 
- NanoClaw 验证过的成熟模式
- 用户体验：一条消息始终在一个位置，不会刷屏
- 飞书 `im.message.patch` API 支持全量替换卡片内容

### D3: 表格渲染 — 飞书原生 table 组件

**选择**: 检测 markdown 表格，解析为飞书卡片 `table` 元素。

**理由**: 
- 飞书卡片 markdown 元素不支持表格（渲染空白）
- 原生 table 组件视觉效果好，支持表头+行列
- 非表格内容仍用 markdown 元素

### D4: 工具状态 — 瞬态 ephemeral patch

**选择**: 工具调用状态是瞬态的（不加入累积文本），下一个文本 chunk 到来时自然覆盖。ephemeral patch 失败静默丢弃。

**理由**:
- 工具状态是过程信息，不应残留在最终回复中
- 静默丢弃避免 retry 导致刷屏
- NanoClaw 同模式，已验证稳定

### D5: 卡片无 Header

**选择**: 不使用飞书卡片的彩色标题栏（header），只用 elements 区域。

**理由**: 视觉更轻量，跟普通消息差异小。

## 4. 卡片生命周期

| 阶段 | 卡片内容 | 操作 | 失败处理 |
|------|---------|------|---------|
| ACK | `⏳ 正在思考...` | `create`（reply 形式） | 创建失败 → 回退纯文本 |
| 流式文本 | 累积的回复文本 | `patch` 同一张卡片 | retry 3 次，仍失败 → 降级纯文本 |
| 工具调用 | `{累积文本}\n\n⏳ {工具名} · {语义}...` | `patch`，ephemeral | 失败静默丢弃 |
| 心跳 | `📝 生成中 · {N}s · {工具语义}` | `patch`，ephemeral（5s 无活动触发） | 失败静默丢弃 |
| 完成 | `{完整回复}\n\n---\n📊 {footer}\n✅ 回复完毕` | 最终 `patch` | retry → 降级纯文本 |
| 出错 | `❌ 处理出错，请重试` | 最终 `patch` | retry → 降级纯文本 |

### 降级路径

当卡片操作反复失败时：
1. 尝试 `sendMessage()` 以纯文本/post 格式发送原始内容（不含卡片格式）
2. 如果 patch 失败但 messageId 存在 → patch 一条 `⚠️ 卡片渲染失败` 占位
3. footer 指标追加在纯文本末尾（回退到现有 runtime_footer 行为）

## 5. 卡片 JSON 结构

### 普通回复（无表格）

```json
{
  "config": {"wide_screen_mode": true, "update_multi": true},
  "elements": [
    {"tag": "markdown", "content": "回复正文（markdown 渲染）"},
    {"tag": "hr"},
    {"tag": "note", "elements": [
      {"tag": "plain_text", "content": "📊 ↑48 | ↓11.1k | cache:3.4M | $2.95 | @nine:feat/xxx | ⏳34s | 🧠gpt-5.5"}
    ]},
    {"tag": "note", "elements": [
      {"tag": "plain_text", "content": "✅ 回复完毕"}
    ]}
  ]
}
```

### 含表格回复

```json
{
  "config": {"wide_screen_mode": true, "update_multi": true},
  "elements": [
    {"tag": "markdown", "content": "表格前的文字"},
    {"tag": "table", "columns": [
      {"name": "col1", "display_name": "列名1"},
      {"name": "col2", "display_name": "列名2"}
    ], "rows": [
      {"col1": "值1", "col2": "值2"}
    ]},
    {"tag": "markdown", "content": "表格后的文字"},
    {"tag": "hr"},
    {"tag": "note", "elements": [
      {"tag": "plain_text", "content": "📊 ↑48 | ↓11.1k | ..."}
    ]},
    {"tag": "note", "elements": [
      {"tag": "plain_text", "content": "✅ 回复完毕"}
    ]}
  ]
}
```

### 流式过程中（工具调用态）

```json
{
  "config": {"wide_screen_mode": true, "update_multi": true},
  "elements": [
    {"tag": "markdown", "content": "已累积的回复文本\n\n⏳ *Bash · 执行命令...*"}
  ]
}
```

### 心跳态

```json
{
  "config": {"wide_screen_mode": true, "update_multi": true},
  "elements": [
    {"tag": "markdown", "content": "📝 生成中 · 15s · Read · 阅读文件"}
  ]
}
```

## 6. Footer 状态栏

### 字段定义

| 字段 | 格式 | 数据源 | 条件 |
|------|------|--------|------|
| input tokens | `↑{N}` | `agent_result.input_tokens` | 始终显示 |
| output tokens | `↓{N}` | `agent_result.output_tokens` | 始终显示 |
| cache | `cache:{N}` | `session.cache_read_tokens` | 仅 >0 时显示 |
| cost | `${N}` | `session.estimated_cost_usd` | 始终显示，保留 4 位小数 |
| git context | `@{repo}:{branch}` | 从 session cwd 运行 git 命令 | 仅在 git 仓库内时显示 |
| elapsed | `⏳{N}s` | `time.time() - turn_start` | 始终显示 |
| model | `🧠{name}` | `agent_result.model`（去 vendor 前缀） | 始终显示 |

### Token 数值格式化

| 范围 | 格式 | 示例 |
|------|------|------|
| < 1000 | 原数 | `↑48` |
| 1000 ~ 999999 | x.xk | `↓11.1k` |
| ≥ 1000000 | x.xM | `cache:3.4M` |

### Git Context 检测

每轮回复结束时（非 gateway 启动时），从 session 的当前 cwd 执行：

```bash
git rev-parse --show-toplevel 2>/dev/null  # → repo 名（取 basename）
git branch --show-current 2>/dev/null      # → 分支名
```

- 在 git 仓库内：显示 `@nine:feat/xxx`
- 不在 git 仓库：不显示此字段
- git 命令超时（>1s）：不显示此字段

### Footer 完整示例

```
📊 ↑48 | ↓11.1k | cache:3.4M | $2.9475 | @nine:feat/feishu-card-footer | ⏳34s | 🧠gpt-5.5
```

无 cache 时：
```
📊 ↑1.2k | ↓5.6k | $0.0150 | @nine:main | ⏳12s | 🧠claude-opus-4
```

## 7. 工具语义映射

| 工具名 | 显示文本 |
|--------|---------|
| Read / read_file | `Read · 阅读文件` |
| Bash / terminal | `Bash · 执行命令` |
| Edit / edit_file | `Edit · 改代码` |
| Write / write_file | `Write · 写文件` |
| MultiEdit | `MultiEdit · 批量改代码` |
| Grep | `Grep · 搜索代码` |
| Glob | `Glob · 查找文件` |
| WebFetch / web_fetch | `WebFetch · 抓取网页` |
| WebSearch / web_search | `WebSearch · 搜索网络` |
| Task / Agent | `Agent · 派出子任务` |
| TodoWrite | `TodoWrite · 更新任务` |
| 未映射工具 | `{toolName}`（只显示原名） |

卡片中实际显示：`⏳ Bash · 执行命令...`

心跳中显示：`📝 生成中 · 15s · Read · 阅读文件`

## 8. 数据流

```
用户发消息
  → FeishuAdapter 收到
  → 立即 create ACK 卡片 → 返回 message_id
  → gateway _handle_message() → AIAgent 开始 turn
  → Agent 流式回调:
      text_chunk → patch(message_id, accumulated_text)
      tool_call  → patch(message_id, accumulated_text + "⏳ {tool}...", ephemeral=true)
      heartbeat  → patch(message_id, "📝 生成中 · {N}s · {tool}", ephemeral=true)
  → Agent turn 完成 → agent_result 含 tokens/cost/model/context
  → 检测 git context（从 session cwd）
  → 构造 footer 指标行
  → 构造最终卡片（正文 + hr + footer note + 完成标记 note）
  → 最终 patch(message_id, final_card)
```

## 9. 改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `gateway/platforms/feishu.py` | 修改 | send() 路径包装卡片；新增 create_card/patch_card 方法；表格解析；工具语义映射；ephemeral patch；降级路径 |
| `gateway/runtime_footer.py` | 修改 | 新增字段：tokens_in/out、cache、cost、elapsed、git_context；token 格式化函数 |
| `gateway/run.py` | 修改 | 传递完整 metrics 给 footer builder（tokens、cost、elapsed）；流式回调中 emit 工具状态 |
| `gateway/session.py` | 可能修改 | 如果需要 per-session cwd 跟踪（当前 cwd 是全局 env var） |

## 10. 兼容性

- **其他平台不受影响**：卡片包装只在 FeishuAdapter 内部，其他 adapter 的 send() 路径不变
- **runtime_footer 向后兼容**：新增字段在旧配置下不显示（数据缺失时跳过该字段）
- **config.yaml 无需改动**：卡片模式对飞书平台默认开启，不需要用户手动配置
- **降级安全**：任何卡片操作失败都能回退到纯文本，不会导致消息丢失

## 11. NanoClaw 参考

本设计参考了 NanoClaw 飞书 bot 的以下模块：

| NanoClaw 文件 | 对应功能 |
|---------------|---------|
| `src/channels/feishu.ts:createCard/updateCard` | 卡片创建与 patch |
| `src/channels/card-lifecycle.ts` | 状态机：CREATED→STREAMING→FINAL |
| `src/channels/card-renderer.ts` | retry/降级管线 |
| `src/index.ts:1452-1470` | 工具状态 ephemeral patch |
| `src/index.ts:2329-2381` | footer 指标行构造 |

Hermes 实现语言为 Python（asyncio），API 用 lark-oapi SDK，但生命周期和降级逻辑直接对齐 NanoClaw。

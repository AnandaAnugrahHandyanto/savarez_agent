# 多 Agent 协作模式管理系统｜项目主线进度表

## 项目目标

把飞书、Hermes agent、workflow profile、task_state、message_validator、message_renderer、outbound_log / real_sent、simulator、publisher、history_recorder、template_registry、Obsidian、MemOS、Codex 组合成一套可配置、可测试、可发布、可回滚、可追踪、可复盘、可复制的通用协作系统。

说明：

- 导演组只是第一个 workflow profile，不是专属逻辑。
- 后续需要可复制到招聘组、开发组、美术组、运营组等其他机器人团队。

## 当前阶段

当前主线处于：

- 第一阶段：已完成
- 第二阶段：已完成，并且已达到可封版、可进入第三阶段的状态
- 第三阶段：下一步准备开始
- 第四阶段：未开始
- 第五阶段：未开始

## 五个阶段进度

### 第一阶段：链路审计

- 当前状态：已完成
- 交付物：飞书入口、PM 路由、skill 注入、真实发送、task / relay / state 现状审计报告
- 已完成内容：
  - 找清飞书消息入口
  - 找清 PM / role routing 逻辑
  - 找清 skill 注入链路
  - 找清真实发送函数
  - 找清“分别发”与 tool log 暴露风险

### 第二阶段：最小工程闭环

- 当前状态：已完成
- 交付物：workflow 最小工程闭环、真实回流链路、二阶段测试、封版说明
- 已完成内容：
  - workflow 入口开关
  - `/n` 作为统一 workflow 启动入口
  - workflow_profile
  - dispatcher
  - task_state
  - outbound_log
  - real_sent / message_id
  - message_validator
  - message_renderer
  - cross_bot_relay 兼容修补
  - PM -> 执行者 -> 回 PM -> 下一棒 回流闭环
  - 群聊显示优化
  - reply template 配置化
  - 二阶段测试通过

### 第三阶段：测试发布闭环

- 当前状态：下一步开始
- 交付物：
  - simulator
  - publisher
  - rollback
  - 发布前测试闭环

### 第四阶段：历史记录与模板复刻

- 当前状态：未开始
- 交付物：
  - history_recorder
  - template_registry
  - 模板复制与复盘机制

### 第五阶段：HTML 可视化配置页

- 当前状态：未开始
- 交付物：
  - profile 管理后台
  - workflow 可视化配置页
  - 状态查看与维护入口

## 下一阶段要做什么

第三阶段聚焦“测试发布闭环”，优先顺序：

1. simulator
2. publisher
3. rollback
4. 发布前测试入口与验收规则

本阶段先不继续扩展新 profile，也不直接进入大型后台建设。

## 风险点

- message_renderer 需要继续确认是否完全隐藏底层命令和工具日志
- 多角色“分别发”需要继续在真实飞书群里验证独立 message event 的稳定性
- 二阶段虽然闭环已打通，但第三阶段前仍需保持发布与回滚路径清晰
- 普通聊天、`/jm` 队列、skill loader 的兼容性需要继续作为回归测试保留

## GitHub 管理方式

- GitHub 作为工程主账本，记录阶段进度、封版状态、问题与风险
- 分支名使用英文，便于 GitHub 与 git 操作
- 文档、Issue、Milestone、PR 标题与正文尽量使用中文，便于项目管理
- 阶段推进建议采用：
  - 一个阶段一个主线文档
  - 一个阶段一个封版说明
  - 风险项单独建 Issue
  - 阶段开始前先确认 Milestone 与 PR 描述

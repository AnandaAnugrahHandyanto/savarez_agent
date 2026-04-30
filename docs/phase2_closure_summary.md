# 第二阶段封版说明｜最小工程闭环

## 第二阶段目标

把 Hermes 飞书多 Agent 协作系统从“主要靠 skill / prompt 约束”推进到“具备最小工程闭环”，确保 workflow 能启动、派单、真实发送、记录状态、回流并继续下一棒。

## 已完成能力

- workflow 入口开关
- `/n` 统一 workflow 启动入口
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

## 测试结果

二阶段相关测试已通过，当前结论为：

- 第二阶段最终验收通过
- 可以进入第三阶段

## 当前分支

- 分支：`codex/workflow-phase2-closure-20260429`

## 当前状态

当前状态：

- 第二阶段已完成
- 已达到可封版、可进入第三阶段的状态

## 还未做的内容

第二阶段没有继续做以下后续能力：

- simulator
- publisher
- rollback
- history_recorder
- template_registry
- HTML 可视化配置页

这些内容属于第三阶段及之后的主线。

## 下一阶段入口

第三阶段入口建议聚焦：

1. 测试发布闭环
2. simulator
3. publisher
4. rollback

在进入第三阶段前，GitHub 需要先同步当前主线状态、阶段文档、风险 Issue 与阶段 Milestone。

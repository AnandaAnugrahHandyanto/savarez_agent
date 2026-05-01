# Claude Code 高价值能力吸收（Hermes-native）

## 结论
Hermes 不应照搬 Claude Code 的产品壳、命令名或 UI 组件，而应吸收其最有价值的底层原则：

1. 统一执行内核优先
2. 分层且可治理的 memory / transcript / resume 体系
3. 权限/危险操作前置为主干设计
4. 上下文压缩是正式治理流程，而不是简单截断
5. 多智能体/多后端能力应抽象成后端选择层，而不是环境技巧堆砌
6. 长会话与持久化要有清晰的治理边界和产品口径

## 本轮已落地的 Hermes-native 吸收结果
### 新技能
- `autonomous-fix-loop`
- `autonomous-debug-loop`
- `autonomous-doc-refresh`
- `autonomous-workflow-chains`

这些技能对应吸收了：
- 统一自治协议（Goal / Scope / Verify / Guard / Iterations）
- 一轮一改动 + 机械验证 + stop condition
- root-cause-first 调试循环
- 文档/验收/能力矩阵的自动刷新工作流
- 多阶段链式工作流模板

## Claude Code 分析中已明确内化为 Hermes 设计原则的点
### 1. 统一执行内核
后续涉及 CLI / gateway / cron / delegate / automation 的扩展时，优先复用同一执行语义，避免为入口复制实现。

### 2. Memory / transcript / resume 治理
后续继续按“可审计、可分层、可关闭、可压缩”的原则推进，而不是堆加隐式持久化行为。

### 3. 权限模型前置
后续新增高风险工具或自动化链路时，默认明确：
- 读写性质
- 破坏性
- 并发安全性
- 是否需要用户交互

### 4. 压缩治理是流程
后续若继续增强压缩链路，按“输入清洗 → 压缩 → hooks/校验 → summary”治理，而不是简单截断。

### 5. 多智能体后端抽象
后续增强多智能体协作时，区分：
- 子 agent 语义
- 运行后端
- 展示/可视化方式
- 本地/远程容器
而不是把环境技巧写死在任务逻辑里。

## 明确不吸收的内容
- Claude Code 专属 UI/TUI 组件壳
- 复杂 remote/bridge 产品壳本身
- 隐私规避/遥测规避类对抗式实现

## 吸收边界
本轮吸收以 Hermes-native 技能、工作流和架构原则为主，不复制 Claude Code 的命令名、品牌壳或专属交互形式。

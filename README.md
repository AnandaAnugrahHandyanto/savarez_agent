# Hermes Agent (Fork)

This is a **fork** of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).

## What is Hermes Agent?

Hermes Agent is an open-source AI agent framework built for autonomous task execution. It can:

- Execute code, browse the web, manage files, and interact with web services
- Use multiple AI models (compression + main) for efficient context management
- Run in CLI, web dashboard, or headless mode
- Support for GitHub, GitHub Actions, and various developer tools

## What's different in this fork?

This fork contains custom modifications focused on **improving CI reliability and tool-loop prevention**:

### Circuit Breaker Improvements
- **Lowered failure threshold**: From 5 to 3 consecutive failures before triggering circuit breaker
- **Compression model suggestions**: When a tool fails repeatedly, the compression model (if configured) provides a "fresh perspective" to break the loop
- **Generic fallback**: Even without a compression model, a simple hint is provided to stop retrying the same approach

### Test Fixes
- Fixed `test_minimax_provider.py` — missing `_fallback_chain` attribute in test stub
- Fixed `test_tips.py` — truncated Tip 105 to meet 150-character limit
- Fixed `test_concurrent_interrupt.py` — resolved `polling_tool` never running and signature mismatch

## Configuration

This fork inherits all configuration from the original repository. See the [original README](https://github.com/NousResearch/hermes-agent) for setup instructions.

## License

This fork is licensed under the same license as the original repository. See the [original LICENSE](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE) for details.

---

<details>
<summary>🇨🇳 <strong>中文版 — 点击展开</strong></summary>

这是一个 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的 fork 仓库。

## 什么是 Hermes Agent？

Hermes Agent 是一个开源 AI Agent 框架，支持自主任务执行。它可以：

- 执行代码、浏览网页、管理文件、与各种 Web 服务交互
- 使用多个 AI 模型（压缩模型 + 主模型）进行高效上下文管理
- 支持 CLI、Web 仪表盘和无头模式运行
- 支持 GitHub、GitHub Actions 和各种开发者工具

## 这个 fork 有什么改动？

这个 fork 专注于 **提高 CI 可靠性和防止工具调用循环**：

### 重试熔断机制改进
- **降低失败阈值**：连续失败从 5 次降低到 3 次就触发重试熔断
- **压缩模型建议**：当工具反复失败时，压缩模型（如果已配置）会提供一个"局外人视角"来打破循环
- **通用降级提示**：即使没有配置压缩模型，也会给出一个简单的提示来阻止重复尝试

### 测试修复
- 修复 `test_minimax_provider.py` — 测试存根缺少 `_fallback_chain` 属性
- 修复 `test_tips.py` — 截断 Tip 105 以满足 150 字符限制
- 修复 `test_concurrent_interrupt.py` — 解决 `polling_tool` 未执行和签名不匹配问题

## 配置

这个 fork 继承原仓库的所有配置。参见 [原仓库 README](https://github.com/NousResearch/hermes-agent) 获取安装说明。

## 许可证

本 fork 使用与原仓库相同的许可证。参见 [原 LICENSE](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE) 了解详情。

</details>

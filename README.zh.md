<h4 align="center">
  <a href="./README.md">English</a> | 中文
</h4>

<br />

# Hermes Agent（Fork）

这是一个 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的 fork 仓库。

---

## 什么是 Hermes Agent？

Hermes Agent 是一个开源 AI Agent 框架，支持自主任务执行。它可以：

- 执行代码、浏览网页、管理文件、与各种 Web 服务交互
- 使用多个 AI 模型（压缩模型 + 主模型）进行高效上下文管理
- 支持 CLI、Web 仪表盘和无头模式运行
- 支持 GitHub、GitHub Actions 和各种开发者工具

---

## 这个 Fork 有什么改动？

这个 fork 专注于 **提高 CI 可靠性和防止工具调用循环**：

### 重试熔断机制改进

- **压缩模型建议**：Hermes 可以配置一个专用模型用于上下文压缩。当工具反复失败时，我们利用这个压缩模型提供一个"局外人视角"来打破循环。你可以通过配置 `circuit_breaker.threshold` 来调整触发熔断的失败次数。
- **通用降级提示**：即使没有配置压缩模型，也会给出一个简单的提示来阻止重复尝试。

### 测试修复

- 修复了 CI 中的 3 个测试报错问题。

---

## 配置

这个 fork 继承原仓库的所有配置。参见 [原仓库 README](https://github.com/NousResearch/hermes-agent) 获取安装说明。

**语言配置**：在 `~/.hermes/config.yaml` 中设置 `approvals.language: zh` 可将 CLI 界面切换为中文。

---

## 许可证

本 fork 使用与原仓库相同的许可证。参见 [原 LICENSE](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE) 了解详情。

<h4 align="center">
  English | <a href="./README.zh.md">中文</a>
</h4>

<br />

# Hermes Agent (Fork)

This is a **fork** of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).

---

## What is Hermes Agent?

Hermes Agent is an open-source AI agent framework built for autonomous task execution. It can:

- Execute code, browse the web, manage files, and interact with web services
- Use multiple AI models (compression + main) for efficient context management
- Run in CLI, web dashboard, or headless mode
- Support for GitHub, GitHub Actions, and various developer tools

---

## What's Different in This Fork?

This fork contains custom modifications focused on **improving CI reliability and tool-loop prevention**:

### Circuit Breaker Improvements

- **Compression model suggestions**: Hermes allows configuring a dedicated model for context compression. When a tool fails repeatedly, we leverage this compression model to provide a "fresh perspective" to break the loop. You can adjust the failure count that triggers the circuit breaker via `circuit_breaker.threshold`.
- **Generic fallback**: Even without a compression model, a simple hint is provided to stop retrying the same approach.

### Test Fixes

- Fixed 3 test failures in CI.

---

## Configuration

This fork inherits all configuration from the original repository. See the [original README](https://github.com/NousResearch/hermes-agent) for setup instructions.

**Language**: Set `approvals.language: zh` in `~/.hermes/config.yaml` to switch the CLI interface to Chinese.

---

## License

This fork is licensed under the same license as the original repository. See the [original LICENSE](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE) for details.

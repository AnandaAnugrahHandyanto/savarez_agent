---
title: "Codex — 将编码任务委托给 OpenAI Codex CLI（功能开发、PR）"
sidebar_label: "Codex"
description: "将编码任务委托给 OpenAI Codex CLI（功能开发、PR）"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Codex

将编码任务委托给 OpenAI Codex CLI（功能开发、PR）。

## Skill 元数据

| | |
|---|---|
| 来源 | 内置（默认安装） |
| 路径 | `skills/autonomous-ai-agents/codex` |
| 版本 | `1.0.0` |
| 作者 | Hermes Agent |
| 许可证 | MIT |
| 平台 | linux, macos, windows |
| 标签 | `Coding-Agent`, `Codex`, `OpenAI`, `Code-Review`, `Refactoring` |
| 相关 skill | [`claude-code`](/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-claude-code), [`hermes-agent`](/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent) |

## 参考：完整 SKILL.md

:::info
以下是 Hermes 在触发此 skill 时加载的完整 skill 定义。这是 skill 激活时 agent 所看到的指令内容。
:::

# Codex CLI

通过 Hermes 终端将编码任务委托给 [Codex](https://github.com/openai/codex)。Codex 是 OpenAI 的自主编码 agent CLI。

## 使用场景

- 功能开发
- 重构
- PR 审查
- 批量问题修复

需要 codex CLI 和一个 git 仓库。

## 前置条件

- 已安装 Codex：`npm install -g @openai/codex`
- 已配置 OpenAI 认证：`OPENAI_API_KEY` 或通过 Codex CLI 登录流程获取的 Codex OAuth 凭证
- **必须在 git 仓库内运行** — Codex 拒绝在 git 仓库外运行
- 终端调用中使用 `pty=true` — Codex 是一个交互式终端应用

对于 Hermes 本身，`model.provider: openai-codex` 会在执行 `hermes auth add openai-codex` 后使用 `~/.hermes/auth.json` 中 Hermes 管理的 Codex OAuth。对于独立的 Codex CLI，有效的 CLI OAuth 会话可能存储在 `~/.codex/auth.json` 中；不要仅凭缺少 `OPENAI_API_KEY` 就认为 Codex 认证缺失。

## 单次任务

```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

用于临时工作（Codex 需要 git 仓库）：
```
terminal(command="cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'", pty=true)
```

## 后台模式（长时任务）

```
# Start in background with PTY
terminal(command="codex exec --full-auto 'Refactor the auth module'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")
```

## 关键标志

| 标志 | 效果 |
|------|--------|
| `exec "prompt"` | 单次执行，完成后退出 |
| `--full-auto` | 沙箱模式，自动批准工作区内的文件变更 |
| `--yolo` | 无沙箱，无需审批（最快，风险最高） |

## PR 审查

克隆到临时目录以安全审查：

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## 使用 Worktree 并行修复问题

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex --yolo exec 'Fix issue #78: <description>. Commit when done.'", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="codex --yolo exec 'Fix issue #99: <description>. Commit when done.'", workdir="/tmp/issue-99", background=true, pty=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd /tmp/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove /tmp/issue-78", workdir="~/project")
```

## 批量 PR 审查

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## 规则

1. **始终使用 `pty=true`** — Codex 是交互式终端应用，没有 PTY 会挂起
2. **需要 git 仓库** — Codex 不能在 git 目录外运行。临时工作请使用 `mktemp -d && git init`
3. **单次任务使用 `exec`** — `codex exec "prompt"` 运行后干净退出
4. **构建时使用 `--full-auto`** — 在沙箱内自动批准变更
5. **长时任务使用后台模式** — 使用 `background=true` 并通过 `process` 工具监控
6. **不要干预** — 使用 `poll`/`log` 监控，对长时运行任务保持耐心
7. **并行执行没问题** — 可同时运行多个 Codex 进程处理批量工作

## 调度模板 / 报告契约

规范 CX 调度模板：`skills/autonomous-ai-agents/codex/templates/default-dispatch.md`。

### 模板注入链路

每次委托 Codex 之前，编排器必须：

1. 调用 `skill_view(name="codex", file_path="templates/default-dispatch.md")` 加载模板。
2. 渲染占位符：`<ABS_REPORT_PATH>`、`<JOB_ID>`、`<TASK_CLASS>`、`<TURN_BUDGET>`。
3. 将渲染后的模板放到调度 prompt 的最前面，**位于**任务描述之前。
4. 然后在模板后面追加具体的任务指令。

### 报告路径规则

- `<ABS_REPORT_PATH>` 必须是目标仓库内的绝对路径。
- 回退路径：`<repo>/.hermes-artifacts/reviews/<JOB_ID>.md`。
- 先用 `mkdir -p` 创建父目录。
- 路径中禁止使用 `~`。
- 禁止将部分输出报告为 `completed`。

### 轮次预算基线

| 任务类型 | 范围 | 默认值 |
|---|---|---|
| `review` | 30–120 | 60 |
| `implementation` | 20–80 | 40 |
| `extract` | 1–10 | 5 |

- 默认情况下，`review` bucket 适用于代码审查（code review）、调试（debug）和重构（refactor）任务。
- 默认情况下，`implementation` bucket 适用于功能开发（features）、问题修复（fixes）、测试（tests）等代码变更任务。
- 默认情况下，`extract` bucket 适用于摘要（summarize）、模式提取（schema）和窄范围提取（narrow extraction）任务。
- Codex 没有统一的 `--max-turns` CLI 范式，因此预算契约需要通过注入的模板和调度 prompt 来承载。

### 结束状态契约

- `completed`：任务在预算内完成，报告已写入。
- `over_budget`：预算耗尽；报告必须列出已完成/未完成/下一步。
- `interrupted`：外部中断；报告必须记录检查点。
- `partial_output`：不完整结果；必须标注为 partial，不得报为 `completed`。

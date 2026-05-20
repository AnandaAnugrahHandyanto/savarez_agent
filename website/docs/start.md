---
slug: /start
sidebar_position: 1
title: "Start Here"
description: "The golden first-run path for Hermes Agent: install, configure, verify, and choose the next command-center workflow."
---

# Start Here

This is the shortest path from “Hermes is installed” to “Hermes is a working command center.”

Follow the checkpoints in order. Do not add gateway, cron, voice, MCP, or multi-agent workflows until the previous checkpoint passes.

## 0. Install

**Linux / macOS / WSL2 / Termux**

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc   # or source ~/.zshrc
```

**Native Windows PowerShell — early beta**

```powershell
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
```

If you need the full install matrix, see [Installation](./getting-started/installation.md).

## 1. Run the setup wizard

```bash
hermes setup
```

Minimum good outcome:

- A model provider is configured.
- `hermes doctor` has no blocking errors.
- Your shell can find the `hermes` command.

Verify:

```bash
hermes doctor
hermes status --all
```

If you already know which provider you want, use the focused model picker instead:

```bash
hermes model
```

## 2. Prove one normal chat works

Start Hermes:

```bash
hermes
# or: hermes --tui
```

Send a prompt that is easy to verify:

```text
Check my current directory and tell me what project this looks like.
```

Success means:

- Hermes replies without auth/model errors.
- It can use at least one local tool when useful.
- A second follow-up works in the same session.

If this does not work, stop here and fix the provider/config first. More features will only make the failure harder to understand.

## 3. Verify persistence

Exit the chat, then resume it:

```bash
hermes --continue
# or: hermes -c
```

Success means Hermes can recover the latest session. This is the foundation for longer-running work, messaging surfaces, and handoffs.

## 4. Choose your command-center path

Once chat + resume work, pick the path that matches what you want Hermes to become.

### A. Personal terminal agent

Use this when Hermes mostly works in your shell.

```bash
hermes tools
hermes config
hermes sessions browse
```

Read next:

- [CLI](./user-guide/cli.md)
- [TUI](./user-guide/tui.md)
- [Tools](./user-guide/features/tools.md)
- [Sessions](./user-guide/sessions.md)

### B. Always-on messaging assistant

Use this when you want Telegram, Discord, Slack, WhatsApp, Signal, or another platform.

```bash
hermes gateway setup
hermes gateway install
hermes gateway start
hermes gateway status
```

Read next:

- [Messaging Gateway](./user-guide/messaging/index.md)
- [Telegram](./user-guide/messaging/telegram.md)
- [Discord](./user-guide/messaging/discord.md)

### C. Automation and scheduled work

Use this when Hermes should run jobs without you present.

```bash
hermes cron create "every 1h"
hermes cron list
```

Read next:

- [Cron](./user-guide/features/cron.md)
- [Delegation](./user-guide/features/delegation.md)
- [Kanban](./user-guide/features/kanban.md)

### D. Project-aware coding agent

Use this when Hermes should work inside repos, remember procedures, and manage PRs.

```bash
cd /path/to/project
hermes --worktree
```

Read next:

- [Context Files](./user-guide/features/context-files.md)
- [Git Worktrees](./user-guide/git-worktrees.md)
- [Checkpoints and Rollback](./user-guide/checkpoints-and-rollback.md)
- [Developer Guide](./developer-guide/architecture.md)

### E. Extensible tool platform

Use this when you want MCP servers, plugins, custom skills, or custom tools.

```bash
hermes mcp list
hermes plugins list
hermes skills list
```

Read next:

- [MCP](./user-guide/features/mcp.md)
- [Plugins](./user-guide/features/plugins.md)
- [Skills](./user-guide/features/skills.md)
- [Adding Tools](./developer-guide/adding-tools.md)

## 5. First-run checklist

Before calling the setup “done,” all of these should pass:

```bash
hermes doctor
hermes status --all
hermes chat -q "Reply with the configured model/provider and one sentence confirming tools are available."
hermes --continue
```

Expected outcome:

- Provider configured.
- No blocking dependency errors.
- One-shot chat works.
- Interactive chat works.
- Resume works.

## If something fails

Use the narrowest fix first:

- Command missing: reopen your terminal, then check `which hermes`.
- Provider/auth failure: run `hermes model` again.
- Tool missing: run `hermes tools`, enable the toolset, then start a new session.
- Gateway silent: run `hermes gateway status` and inspect `~/.hermes/logs/gateway.log`.
- Sessions not resuming: check `hermes profile list` and `hermes sessions list`.

For deeper troubleshooting, see [FAQ & Troubleshooting](./reference/faq.md) and [Configuration](./user-guide/configuration.md).

## Machine-readable docs

Agents can ingest the docs directly:

- [`/llms.txt`](/llms.txt) — compact index.
- [`/llms-full.txt`](/llms-full.txt) — full docs corpus.

These files are regenerated during every docs build.

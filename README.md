<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

# Hermes Agent

Hermes Agent is an open source AI agent runtime and CLI from [Nous Research](https://nousresearch.com). It provides an interactive terminal agent, a messaging gateway, a tool execution system, persistent memory, skills, scheduled automations, and multiple deployment backends.

The project is packaged as the `hermes-agent` Python package and exposes these command-line entry points:

- `hermes`: main CLI, setup, chat, gateway, model, tools, cron, dashboard, and admin commands
- `hermes-agent`: lower-level agent runner
- `hermes-acp`: Agent Client Protocol server for editor integration

## Core Features

- Interactive CLI with streaming responses, slash commands, session history, model switching, tool approval, and resumable conversations.
- Multi-provider model support through Nous Portal, OpenRouter, Anthropic, OpenAI Codex, GitHub Copilot, Gemini, Bedrock, Ollama Cloud, Hugging Face, z.ai/GLM, Kimi/Moonshot, MiniMax, NVIDIA NIM, Xiaomi MiMo, Arcee, DeepSeek, Alibaba/Qwen, LM Studio, and custom OpenAI-compatible endpoints.
- Tool system for terminal commands, file operations, browser automation, web search, code execution, MCP servers, media handling, image/video generation, TTS/STT, memory, skills, todo/kanban workflows, and delegation.
- Terminal execution backends for local shell, Docker, SSH, Singularity/Apptainer, Modal, Daytona, and Vercel Sandbox.
- Messaging gateway for Telegram, Discord, Slack, WhatsApp, Signal, Email, Matrix, Mattermost, DingTalk, Feishu, WeCom, QQ, SMS, Home Assistant, webhooks, and an optional API server.
- Persistent context through local memory, session search, skill creation/installation, optional Honcho user modeling, and project context files.
- Cron scheduler for unattended jobs that can deliver results back through the CLI or messaging platforms.
- Browser dashboard, OpenAI-compatible proxy, ACP integration, LSP helpers, plugins, profiles, backups, checkpoints, and diagnostics.
- Research utilities for batch task execution, trajectory capture, and trajectory compression.

## Requirements

- Python 3.11 or newer
- `uv` for the recommended source/development workflow
- Node.js for browser tools, dashboard assets, and terminal UI assets
- Optional system tools depending on enabled features: Git, ripgrep, ffmpeg, Docker, SSH, Playwright/Chromium

The install scripts handle most prerequisites automatically on Linux, macOS, WSL2, Termux, and native Windows.

## Quick Install

### Linux, macOS, WSL2, and Termux

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Reload your shell, then start Hermes:

```bash
source ~/.bashrc  # or: source ~/.zshrc
hermes
```

Useful installer options:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --skip-setup
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --dir \"$HOME/src/hermes-agent\"
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --help
```

### Windows PowerShell

Native Windows support is available, but WSL2 remains the most exercised Windows path.

```powershell
irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1 | iex
```

The Windows installer installs Hermes under `%LOCALAPPDATA%\\hermes`, provisions Python/Node dependencies, and uses either an existing Git install or a bundled portable Git Bash.

### Docker

The repository includes a Dockerfile and Compose file for running the gateway and local dashboard with persistent state in `~/.hermes`.

```bash
cd hermes-agent
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d --build
```

The Compose dashboard binds to localhost by default. Use an SSH tunnel or authenticated reverse proxy for remote access.

## Configure Hermes

Run the guided setup first:

```bash
hermes setup
```

For manual setup, copy the environment template and add provider/tool keys:

```bash
cp .env.example ~/.hermes/.env
hermes config path
hermes config show
```

Common provider variables include:

- `OPENROUTER_API_KEY`
- `NOUS_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`
- `GITHUB_TOKEN`
- `HF_TOKEN`
- `NVIDIA_API_KEY`

Tool-specific variables such as `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `PARALLEL_API_KEY`, `FAL_KEY`, and messaging platform tokens are documented in `.env.example` and the generated config.

## Basic Usage

Start an interactive session:

```bash
hermes
```

Run a one-shot prompt:

```bash
hermes \"summarize this repository\"
hermes -m anthropic/claude-opus-4.6 \"write a release checklist\"
```

Select a model and provider:

```bash
hermes model
hermes config set model.provider openrouter
hermes config set model.default anthropic/claude-opus-4.6
```

Configure tools and execution:

```bash
hermes tools
hermes tools list
hermes config set terminal.backend docker
hermes config set terminal.cwd /workspace
```

Inspect and diagnose the install:

```bash
hermes status
hermes doctor
hermes logs
hermes version
hermes update
```

Useful in-session slash commands:

```text
/new
/reset
/model [provider:model]
/tools
/skills
/usage
/compress
/retry
/undo
```

## Messaging Gateway

The gateway lets you talk to the same Hermes runtime from messaging platforms.

```bash
hermes gateway setup
hermes gateway run
```

Service-style management commands:

```bash
hermes gateway install
hermes gateway start
hermes gateway status
hermes gateway restart
hermes gateway stop
```

Pairing and access control:

```bash
hermes pairing list
hermes pairing approve <code>
hermes pairing revoke <user>
```

Platform credentials and allowlists live in `~/.hermes/.env` and `~/.hermes/config.yaml`. Run `hermes gateway setup` whenever adding a new platform.

## Scheduling

Create and manage scheduled automations:

```bash
hermes cron create
hermes cron list
hermes cron status
hermes cron run <job-id>
hermes cron pause <job-id>
hermes cron resume <job-id>
hermes cron remove <job-id>
```

Cron jobs can use the same model, tools, memory, and delivery channels as normal Hermes sessions.

## Skills, Plugins, and Memory

Skills are reusable instructions and helper code that Hermes can call during conversations.

```bash
hermes skills browse
hermes skills search <query>
hermes skills install <skill>
hermes skills list
hermes skills update
```

Plugins can add CLI commands and runtime behavior:

```bash
hermes plugins list
hermes plugins install <source>
hermes plugins enable <name>
hermes plugins disable <name>
hermes plugins disable <name>
```

Memory controls:

```bash
hermes memory status
hermes memory setup
hermes memory off
hermes sessions browse
```

Optional Honcho integration:

```bash
hermes honcho setup
hermes honcho status
hermes honcho mode hybrid
```

## Dashboard, ACP, and Proxy

Start the local dashboard:

```bash
hermes dashboard
```

Run Hermes as an ACP server for compatible editor/client integrations:

```bash
hermes acp
```

Start the OpenAI-compatible proxy:

```bash
hermes proxy start
```

## Development

Clone and run the repository setup script:

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
./setup-hermes.sh
./hermes
```

Manual development setup:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e \".[all,dev]\"
```

Run tests and checks:

```bash
scripts/run_tests.sh
pytest
ty check
ruff check
```

Build dashboard assets when working on the web UI:

```bash
cd web
npm install
npm run build
```

## Project Layout

- `hermes_cli/`: CLI commands, setup, dashboard server, model/tool configuration, gateway commands, diagnostics
- `agent/`: agent loop, model adapters, context/memory handling, prompt construction, transports, pricing, routing
- `tools/`: tool implementations and terminal backends
- `gateway/`: messaging gateway, platform adapters, delivery, pairing, session handling
- `cron/`: scheduled job runner
- `acp_adapter/`: Agent Client Protocol server
- `providers/`: provider integrations
- `plugins/`, `skills/`, `optional-skills/`: extension systems and bundled capabilities
- `web/`: dashboard frontend
- `ui-tui/`: terminal UI assets
- `website/`: documentation site
- `tests/`: unit and integration tests

## Documentation

Documentation is published at [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/).

Important local files:

- `CONTRIBUTING.md`: contributor setup and project practices
- `SECURITY.md`: security policy
- `.env.example`: environment variables and provider keys
- `cli-config.yaml.example`: full configuration example
- `gateway/platforms/ADDING_A_PLATFORM.md`: guide for adding gateway platforms

## Migrating from OpenClaw

Hermes can import OpenClaw settings, memories, skills, command allowlists, messaging config, API keys, TTS assets, and workspace instructions.

```bash
hermes claw migrate --dry-run
hermes claw migrate
hermes claw migrate --preset user-data
hermes claw migrate --overwrite
```

The setup wizard also detects `~/.openclaw` and offers migration during first-time setup.

## License

MIT. See `LICENSE`.
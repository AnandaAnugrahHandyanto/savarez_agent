# Agent Command Hub

> This document describes the running Hermes Agent instance — its configuration, capabilities, source identity, and how to extend it.

---

## Deployment Identity

| Property         | Value |
|---|---|
| **Source Repo**  | `kiranvk-code/hermes-agent` (private) |
| **Upstream**     | `NousResearch/hermes-agent` |
| **Running Branch** | `running` — pinned to exact deployed commit |
| **Upstream Branch** | `upstream/main` — verbatim NousResearch main |
| **Current Commit** | *(see DEPLOYED_COMMIT below)* |
| **Deploy Path**  | `/root/.hermes/hermes-agent/` |
| **Binary Entry** | `/root/.local/bin/hermes` → `hermes-agent/venv/bin/hermes` |
| **Platform**     | Telegram (DM with pkd11) |

**DEPLOYED_COMMIT:** `86b45e935`
**DEPLOYED_VERSION:** `v2026.4.30-398-g86b45e93`
**DEPLOYED_DATE:** `2026-05-04`

---

## LLM Provider Configuration

### Primary: Bailian (Alibaba Cloud)
- **Provider:** `alibaba`
- **Default Model:** `qwen3.6-plus`
- **Base URL:** `https://coding-intl.dashscope.aliyuncs.com/v1`
- **Purpose:** Long-running sessions, general tasks

### Fallback: GitHub Copilot
- **Provider:** `copilot`
- **Fallback Model:** `claude-sonnet-4.6`
- **Base URL:** `https://api.business.githubcopilot.com` (set via `COPILOT_API_BASE_URL` in `.env`)
- **Purpose:** Strategic tasks, high-quality reasoning
- **Token Source:** Copilot Account Manager at `localhost:5111`
- **Rotation:** Every 5 min via `/root/.hermes/scripts/hermes-token-rotation.sh`

### Available Models (switch via `/model`)

**Copilot Models:**
- `copilot/claude-opus-4.6`, `copilot/claude-opus-4.7`
- `copilot/claude-sonnet-4.6`, `copilot/claude-sonnet-4.5`, `copilot/claude-sonnet-4`
- `copilot/claude-haiku-4.5`
- `copilot/gpt-5.5`, `copilot/gpt-5.4`, `copilot/gpt-5.4-mini`, `copilot/gpt-5.2-codex`, `copilot/gpt-5.3-codex`
- `copilot/gemini-3.1-pro-preview`
- `copilot/grok-code-fast-1`

**Bailian Models:**
- `alibaba/qwen3.6-plus`
- `alibaba/glm-5`
- `alibaba/kimi-k2.5`
- `alibaba/qwen3-coder-plus`
- `alibaba/qwen3-max`
- `alibaba/minimax-m2.5`

### Switching Models
- **Telegram:** Type `/model` for picker, or `/model copilot/claude-sonnet-4.6` for instant switch
- **CLI:** `hermes model` interactive picker
- **Fallback:** Automatic when primary fails (rate-limit, 5xx, connection errors)

---

## System Prompt Architecture

The agent's behavior is composed of layered prompts, assembled at runtime:

```
System Prompt = [Base system prompt]
              + [SOUL.md — personality/tone]
              + [Memory — persistent facts (user prefs, env, conventions)]
              + [Skills — procedural knowledge (task-specific instructions)]
              + [Conversation history — current session context]
```

### SOUL.md (`~/.hermes/SOUL.md`)
Defines the agent's personality and communication tone. Loaded fresh each message.

### Memory (`~/.hermes/memory/`)
Two stores:
- **user** — who the user is (preferences, habits, pet peeves)
- **memory** — agent's notes (environment facts, conventions, tool quirks)

### Skills (`~/.hermes/skills/`)
Procedural knowledge for recurring task types. Each skill has:
- `SKILL.md` — trigger conditions, numbered steps, pitfalls, verification
- Optional: `references/`, `templates/`, `scripts/`, `assets/`

---

## Tool Configuration

### Enabled Toolsets
- `hermes-cli` — full tool suite

### Core Tools
| Tool | Purpose |
|---|---|
| `terminal` | Shell execution (foreground/background/PTY) |
| `read_file` / `write_file` / `patch` | File operations |
| `search_files` | Grep/find replacement |
| `browser_*` | Browser automation |
| `web_*` | Web search and content extraction |
| `delegate_task` | Spawn subagents for parallel/isolated work |
| `execute_code` | Python sandbox with Hermes tool access |
| `memory` | Persistent memory read/write |
| `skill_manage` / `skill_view` | Skill lifecycle |
| `cronjob` | Scheduled task management |
| `send_message` | Cross-platform messaging |
| `session_search` | Cross-session recall |

### Tool Registry
All tools defined in `tools/registry.py` — schemas, handlers, dispatch.

---

## Current Configuration (`~/.hermes/config.yaml`)

### Model
- **Default:** `qwen3.6-plus`
- **Provider:** `alibaba`
- **Base URL:** `https://coding-intl.dashscope.aliyuncs.com/v1`
- **Fallback:** `copilot/claude-sonnet-4.6`

### Agent Settings
- **Max turns:** 60
- **Gateway timeout:** 1800s (30 min)
- **Reasoning effort:** medium
- **Verbose:** false

### Terminal
- **Backend:** local (VPS filesystem)
- **Timeout:** 180s
- **Persistent shell:** true

### Compression
- **Enabled:** true
- **Threshold:** 85% context usage
- **Target ratio:** 20%
- **Protect last N:** 20 messages

---

## Versioning Strategy

### Branch Model
```
upstream/main  ← clean mirror of NousResearch/hermes-agent main
running        ← pinned to exact deployed commit (+ custom scripts)
feature/*      ← extensions and customizations
```

### Update Flow
1. Fetch upstream: `git fetch origin`
2. Update upstream/main mirror: `git push personal refs/remotes/origin/main:refs/heads/upstream/main`
3. Reset running to latest: `git checkout running && git reset --hard origin/main`
4. Re-add custom scripts: `cp /root/.hermes/scripts/hermes-token-rotation.sh scripts/`
5. Add/update AGENT-HUB.md with new commit hash
6. Tag: `git tag deployed-YYYYMMDD-<sha7>`
7. Push: `git push personal running --tags --force`

### Important: Preserve Custom Scripts
Custom scripts in `/root/.hermes/scripts/` survive updates (outside git repo).
But they MUST be re-committed to the repo after each update:
```bash
cp /root/.hermes/scripts/hermes-token-rotation.sh /root/.hermes/hermes-agent/scripts/
git add scripts/hermes-token-rotation.sh
git commit -m "scripts: preserve hermes token rotation script"
git push personal running-local:refs/heads/running --force
```

### Adding Features
1. Branch off `running`: `git checkout -b feature/<name> running`
2. Make changes
3. Test locally
4. Merge to `running` when ready

---

## Token Rotation

### Script: `/root/.hermes/scripts/hermes-token-rotation.sh`
- Checks quota via Copilot Account Manager every 5 min
- Rotates token when exhausted or critical (<=5%)
- Updates `COPILOT_GITHUB_TOKEN` in `/root/.hermes/.env`
- Signals gateway USR1 for credential reload
- Telegram notifications on rotation
- Supports `--once`, `--status`, and daemon modes

### Cron Job
- **Job ID:** `0a1dc2ba0405`
- **Schedule:** Every 5 minutes
- **Name:** "Hermes Copilot Token Rotation"

### Copilot Account Manager
- **URL:** `http://localhost:5111`
- **Auth:** Basic (`759641:Kapuma@23`)
- **Accounts:** 34 GitHub accounts in rotation pool
- **API:** `GET /api/best-token?tool=hermes&reason=rotation-check`

---

## Project Structure

```
hermes-agent/
├── run_agent.py          # AIAgent class — core conversation loop
├── model_tools.py        # Tool orchestration & dispatch
├── toolsets.py           # Toolset definitions
├── cli.py                # HermesCLI — interactive CLI orchestrator
├── hermes_state.py       # SessionDB — SQLite session store (FTS5)
├── agent/                # Agent internals (prompts, compression, caching)
├── hermes_cli/           # CLI subcommands, setup, skin engine
├── tools/                # Tool implementations & registry
├── gateway/              # Messaging platform gateway
├── ui-tui/               # React TUI (Ink)
├── tui_gateway/          # Python JSON-RPC backend for TUI
├── acp_adapter/          # ACP server (VS Code / Zed integration)
├── cron/                 # Scheduler
├── scripts/              # Custom scripts (hermes-token-rotation.sh)
├── tests/                # Pytest suite (~3000 tests)
└── batch_runner.py       # Parallel batch processing
```

**Config files:**
- `~/.hermes/config.yaml` — settings
- `~/.hermes/.env` — API keys (includes `COPILOT_GITHUB_TOKEN`, `COPILOT_API_BASE_URL`)
- `~/.hermes/SOUL.md` — personality
- `~/.hermes/memory/` — persistent memory
- `~/.hermes/skills/` — procedural skills

---

## How to Extend This Agent

### 1. Modify behavior via SOUL.md
Edit `~/.hermes/SOUL.md` — changes apply immediately (loaded each message).

### 2. Switch models
Type `/model` in Telegram for interactive picker, or `/model provider/model-name` for instant switch.

### 3. Add/remove skills
- Create in `~/.hermes/skills/<name>/SKILL.md`
- Agent auto-discovers and loads on relevance

### 4. Update memory
Agent auto-saves durable facts via `memory` tool.

### 5. Patch source code
- Branch off `running`, modify Python source
- Restart gateway: `systemctl restart hermes-gateway`

### 6. Change model/provider
Edit `~/.hermes/config.yaml` under `model:` section, or use `/model` command.

---

## Self-Update Procedure

When the user requests "update yourself":

1. Run `hermes update --yes` — pulls latest upstream, restarts gateway
2. Verify: `hermes --version`, gateway PID, Telegram connected
3. Fetch upstream and push mirror: `git fetch origin && git push personal refs/remotes/origin/main:refs/heads/upstream/main`
4. Reset running: `git checkout running-local && git reset --hard origin/main`
5. Re-add custom scripts to repo
6. Update AGENT-HUB.md with new commit hash
7. Tag and push: `git tag deployed-$(date +%Y%m%d)-$(git rev-parse --short=7 HEAD) && git push personal running --tags --force`
8. Verify token rotation cron job is still active

---

*Last updated: 2026-05-04*

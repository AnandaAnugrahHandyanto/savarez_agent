# Nash-AI Phase 1: Local Docker Sandbox Setup

## What This Gets You

OpenClaw running in a Docker container on your Windows laptop with:
- **WebChat dashboard** at localhost:18789 — visual interface showing live agent activity
- **Shared workspace folder** — visible in Windows Explorer at `C:\Users\Mike\openclaw\workspace`
- **Agent sandbox** — isolated execution, can't touch your machine outside the workspace
- **Telegram/WhatsApp** — message your agent from your phone
- **OpenRouter free tier** — connected for LLM calls at zero cost while testing

Everything stays contained. If something goes wrong, `docker compose down` and it's gone.

---

## Prerequisites

1. **Docker Desktop for Windows** — download from docker.com/products/docker-desktop
   - During install, ensure WSL2 backend is selected (it's the default)
   - After install, open Docker Desktop, let it finish initialising
   - Verify: open PowerShell, run `docker --version` — should show a version number

2. **Git for Windows** — download from git-scm.com if not already installed

3. **An OpenRouter account** (free) — sign up at openrouter.ai
   - Get your API key from openrouter.ai/keys
   - Free tier gives you access to Gemma, Llama, Mistral at zero cost

4. **A Telegram account** (easiest messaging setup)
   - Open Telegram, message @BotFather
   - Send `/newbot`, follow prompts, get your bot token
   - Keep the token handy

---

## Step 1: Clone and Set Up OpenClaw

Open PowerShell (not as admin, just normal):

```powershell
# Navigate to your home directory
cd ~

# Clone OpenClaw
git clone https://github.com/openclaw/openclaw.git
cd openclaw

# Set the image to use (pre-built, faster than building locally)
$env:OPENCLAW_IMAGE = "ghcr.io/openclaw/openclaw:latest"

# Run the Docker setup script
# This will ask you configuration questions — see below for answers
bash scripts/docker/setup.sh
```

If `bash` doesn't work in PowerShell, open **Git Bash** (installed with Git for Windows) and run the same commands there.

---

## Step 2: Onboarding Wizard Answers

The setup script runs an interactive wizard. Here's what to choose:

| Question | Answer |
|---|---|
| Gateway mode | **local** |
| AI Provider | **OpenRouter** (or Anthropic if you want to use your Claude API key) |
| API Key | Paste your OpenRouter API key |
| Model | **google/gemma-2-27b-it:free** (or whatever free model looks best) |
| Enable Tailscale? | **No** (not needed for local testing) |
| Enable Agent Sandbox? | **Yes** (extra isolation for tool execution) |

---

## Step 3: Connect Telegram

After the gateway is running:

```powershell
# In the openclaw directory
docker compose run --rm openclaw-cli channels add --channel telegram --token "YOUR_BOT_TOKEN_HERE"
```

OpenClaw will send you a pairing message on Telegram. Approve it:

```powershell
docker compose run --rm openclaw-cli pairing approve telegram YOUR_PAIRING_CODE
```

Send "Hello" to your bot on Telegram. If it responds, you're live.

---

## Step 4: Open the WebChat Dashboard

Open your browser and go to:

```
http://127.0.0.1:18789/
```

You'll see the OpenClaw Control UI. Paste your gateway token (shown during setup, also in your `.env` file) into Settings.

This dashboard shows:
- Live conversation with the agent
- Tool calls being made (which skills are firing)
- Memory and session state
- Configuration options

---

## Step 5: Verify the Shared Workspace

The setup creates two folders on your machine:

- `~/.openclaw/` — config, memory, API keys (don't touch unless you know what you're doing)
- `~/openclaw/workspace/` — the agent's working directory

Open Windows Explorer and navigate to `C:\Users\Mike\openclaw\workspace`. This is the shared folder. When the agent creates files, they appear here instantly. When you put files here, the agent can see them.

**Test it:** Drop the `project-status.json` file into the workspace folder. Then message the agent: "Read the file project-status.json and summarise my projects." It should read the file and respond.

---

## Step 6: Install Core Skills

From the openclaw directory:

```powershell
# Bundled skills (already included, just verify they're active)
# shell, browser, file system, git — these ship with OpenClaw

# Install useful ClawHub skills
docker compose run --rm openclaw-cli skills install cairn-cli
docker compose run --rm openclaw-cli skills install ai-model-router
```

Restart the gateway to pick up new skills:

```powershell
docker compose restart
```

---

## Step 7: Add Your Project Context

Copy these files into `~/openclaw/workspace/`:

- `project-status.json` (your project states)
- `coordinator.py` (the daily briefing script)
- Any project README files or specs you want the agent to reference

Then message the agent:

> "Read project-status.json in your workspace. This is the state of all my current projects. Remember this context. From now on, when I ask about any project, reference this file for current status."

The agent will store this in its memory and reference it going forward.

---

## Step 8: Test Basic Capabilities

Try these messages to verify everything works:

1. **"What are my current projects and their priorities?"** — should read project-status.json and summarise
2. **"What's the highest priority task I should work on today?"** — should reason about priorities
3. **"Create a file called test.md in your workspace with a summary of Herald"** — verify file creation (check Windows Explorer)
4. **"Search the web for the latest OpenClaw skills for GitHub automation"** — verify web access
5. **"Run the command `date` in your shell"** — verify shell execution works

---

## Useful Docker Commands

Keep these handy:

```powershell
# Start OpenClaw (from the openclaw directory)
docker compose up -d

# Stop OpenClaw
docker compose down

# View live logs (see what it's doing in real-time)
docker compose logs -f

# Restart after changing config
docker compose restart

# Run CLI commands
docker compose run --rm openclaw-cli <command>

# Check container health
docker compose ps
```

---

## What You Can See and Control

| What | Where | How |
|---|---|---|
| Live conversation | WebChat at localhost:18789 | Browser tab |
| Agent's reasoning | WebChat debug panel | Browser tab |
| Files it creates | `C:\Users\Mike\openclaw\workspace\` | Windows Explorer |
| Skill activity | WebChat tool call panel | Browser tab |
| Logs | `docker compose logs -f` | PowerShell (or Docker Desktop UI) |
| Config | `C:\Users\Mike\.openclaw\` | Windows Explorer |
| Memory | `C:\Users\Mike\.openclaw\memory\` | Windows Explorer (Markdown files) |

Docker Desktop also has a visual UI — open it and click on your openclaw containers to see logs, resource usage, and container status without touching a terminal.

---

## Security Notes

- The agent can only access files inside `~/openclaw/workspace/` and `~/.openclaw/`
- With Agent Sandbox enabled, tool execution runs in additional isolated containers
- It cannot see your desktop, documents, browser data, or SSH keys
- If you want it to work on a project repo, copy or symlink the repo INTO the workspace folder
- The gateway binds to `127.0.0.1` only — not accessible from outside your machine
- To add more folders, edit docker-compose.yml to add volume mounts

---

## Troubleshooting

**"Cannot connect to Docker daemon"** — open Docker Desktop app first, wait for it to start

**Port 18789 already in use** — something else is using that port. Change it in docker-compose.yml

**Agent doesn't respond** — check `docker compose logs -f` for errors. Usually a missing or invalid API key

**Slow responses** — free OpenRouter models can be slow during peak times. This improves when you move to local Ollama on the VPS

**Can't find workspace folder** — check `~/openclaw/workspace/` (that's `C:\Users\Mike\openclaw\workspace\`)

---

## Next Step

Once this is working and you're comfortable with the basics, move to **Phase 2: Skills & Automation** to connect your projects and start automating real tasks.

# Nash-AI Phase 3: VPS Migration & Always-On Agent

## Prerequisites

Phase 2 complete — agent doing useful daily work locally, skills proven, Prism integrated, real tasks being automated, confidence that the €32/month VPS spend is justified.

---

## Goal

Migrate the proven local setup to the Hetzner VPS. Add a local LLM via Ollama. Make it always-on, accessible from anywhere via Telegram, running heartbeat tasks 24/7.

---

## 1. Upgrade the Hetzner VPS

### Current: CX42 — 8 vCPU, 16GB RAM, 160GB NVMe — €16.40/month

### Upgrade to: CX52 — 16 vCPU, 32GB RAM, 320GB NVMe — €32.40/month

This is a one-click operation in the Hetzner Cloud Console. No migration, no downtime beyond a reboot.

1. Log into cloud.hetzner.com
2. Select your server
3. Go to Rescale → select CX52
4. Confirm → server restarts with new specs

Verify after restart:
```bash
ssh mike@ide.nashsoftware.dev
free -h   # Should show ~31GB
nproc     # Should show 16
```

---

## 2. Install Docker on VPS

If not already installed:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect

# Verify
docker --version
docker compose version
```

---

## 3. Deploy OpenClaw

```bash
# Clone OpenClaw
cd /opt
git clone https://github.com/openclaw/openclaw.git
cd openclaw

# Use pre-built image (faster)
export OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:latest"

# Run setup
bash scripts/docker/setup.sh
```

During onboarding, configure the same way as local but with key differences:
- Gateway bind: **lan** (so Tailscale can reach it)
- Enable Agent Sandbox: **Yes**

---

## 4. Migrate Your Local Config

From your Windows machine:

```powershell
# Copy config (skills, memory, project files)
scp -r ~/openclaw/workspace/* mike@ide.nashsoftware.dev:/opt/openclaw/workspace/
scp -r ~/.openclaw/skills/* mike@ide.nashsoftware.dev:/root/.openclaw/skills/
scp ~/.openclaw/openclaw.json mike@ide.nashsoftware.dev:/root/.openclaw/openclaw.json
```

Edit the config on the VPS to update any localhost references to VPS paths. Restart:

```bash
cd /opt/openclaw
docker compose restart
```

Reconnect Telegram — you'll need to re-pair since the gateway token changed.

---

## 5. Install Ollama (Local LLM)

This is where the VPS becomes a self-contained AI brain.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
# Fast small model for quick tasks (fits easily in 32GB)
ollama pull gemma3:12b

# Medium model for reasoning (runs well on 32GB with room for other services)
ollama pull gemma3:27b

# Verify
ollama list
curl http://localhost:11434/api/generate -d '{"model":"gemma3:12b","prompt":"Hello","stream":false}'
```

### Memory budget on 32GB VPS:

| Service | RAM Usage |
|---|---|
| OS + system | ~1.5GB |
| Caddy + n8n + code-server | ~2GB |
| OpenClaw (Docker) | ~500MB |
| Ollama (gemma3:12b loaded) | ~10GB |
| Ollama (gemma3:27b loaded) | ~20GB |
| Headroom | ~6-8GB |

Run the 12B model as the always-loaded default. Load 27B on-demand for complex reasoning (Ollama manages this automatically — it unloads the 12B and loads 27B when requested, then swaps back).

---

## 6. Connect OpenClaw to Ollama

Configure OpenClaw to use local Ollama. In the Docker container, Ollama on the host is accessible at `host.docker.internal:11434` (Docker Desktop) or the host's Tailscale IP.

On Linux VPS, the simplest approach — add to docker-compose.yml:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Then configure OpenClaw's model provider:

```bash
docker compose run --rm openclaw-cli config set \
  --path "providers.ollama" \
  --value '{"type":"ollama","url":"http://host.docker.internal:11434","model":"gemma3:12b"}'
```

Or edit `~/.openclaw/openclaw.json` directly to add the Ollama provider.

---

## 7. Connect Prism as the Intelligence Router

With Prism running on the VPS alongside OpenClaw:

```
Incoming query from Mike (Telegram)
    │
    ▼
OpenClaw (agent reasoning, skill selection)
    │
    ▼
Prism Router (determines best model)
    ├── "What time is my meeting?" → Gemma 12B (local, instant, free)
    ├── "Summarise this PR and suggest improvements" → Gemma 27B (local, 0 cost)
    ├── "Draft a LinkedIn post about Herald launch" → Gemma 27B (local, 0 cost)
    ├── "Review this architecture doc in depth" → OpenRouter free tier (Gemma/Llama)
    └── "Deep analysis of ACR state machine design" → Claude Opus (via Conductor session)
```

90%+ of queries never leave your VPS. Claude is reserved for genuine frontier reasoning. Total API cost: nearly zero.

---

## 8. Enable Heartbeat Tasks

Configure scheduled autonomous tasks:

```json
// In openclaw.json or via CLI
{
  "heartbeat": {
    "tasks": [
      {
        "name": "morning-briefing",
        "schedule": "0 7 * * *",
        "skill": "nash-coordinator",
        "channel": "telegram"
      },
      {
        "name": "overnight-queue",
        "schedule": "0 23 * * *",
        "skill": "nash-overnight-queue",
        "channel": "telegram"
      },
      {
        "name": "auto-tests",
        "schedule": "0 2 * * *",
        "skill": "nash-auto-test",
        "channel": "telegram"
      },
      {
        "name": "weekly-retro",
        "schedule": "0 9 * * 1",
        "skill": "nash-coordinator",
        "action": "weekly_retrospective",
        "channel": "telegram"
      },
      {
        "name": "linkedin-draft",
        "schedule": "0 10 * * 3",
        "skill": "nash-linkedin",
        "channel": "telegram"
      }
    ]
  }
}
```

Your agent now works while you sleep.

---

## 9. Access From Anywhere

With Tailscale already set up:
- **Telegram** — message the bot from anywhere, it responds 24/7
- **WebChat** — access the dashboard at `http://your-tailscale-ip:18789` from laptop, phone, or any device on your Tailscale network
- **Workspace files** — accessible via code-server at ide.nashsoftware.dev (already set up)

---

## 10. Monitoring & Maintenance

```bash
# Check OpenClaw status
docker compose ps

# View live agent activity
docker compose logs -f

# Check Ollama model status
ollama list
curl http://localhost:11434/api/ps  # Currently loaded models

# Check VPS resource usage
htop
free -h
df -h

# Update OpenClaw
cd /opt/openclaw
git pull
docker compose pull
docker compose up -d
```

Set up a simple health check — add to your n8n instance:
- Cron trigger every 5 minutes
- HTTP request to `http://localhost:18789/healthz`
- If unhealthy → ntfy.sh notification

---

## What You Now Have

An always-on personal AI assistant that:

- Greets you every morning with a prioritised action plan
- Answers questions about any of your 6 projects instantly
- Runs automated tests on Optimal You every night
- Executes queued coding tasks while you sleep
- Drafts LinkedIn content weekly
- Routes 90% of queries through your own local LLM at zero cost
- Escalates to Claude Opus via your existing session for deep reasoning
- Is accessible from your phone, laptop, or any device via Telegram
- Manages and iterates on your own tools (Prism, ACR, Conductor) inside a sandboxed environment

Monthly cost: €32.40 (~£28). No API token costs for the vast majority of usage.

---

## Phase 4 and Beyond

Once Phase 3 is stable and the agent is reliably useful:

| Phase | What | When |
|---|---|---|
| 4a | Upgrade to 48GB VPS, run Gemma 4 31B locally | When revenue justifies €72/month |
| 4b | Herald integration — agent powers the AI briefing feature | When Herald ships |
| 4c | Voice interface — Whisper STT + Piper TTS on VPS | When you want to talk to it |
| 4d | ACR self-hosting — agent runs on ACR's own pipeline | When ACR core is built |
| 4e | Multi-agent — specialist sub-agents for coding, testing, comms | When single agent hits limits |
| 4f | Life dashboard — web UI consolidating all project/life data | When you want a visual command centre |
| 4g | Open source Nash-AI as an OpenClaw skill pack | When it's polished enough to share |

The end state: Nash-AI is the reference implementation that proves ACR works. ACR becomes the product. The personal assistant becomes the sales demo.

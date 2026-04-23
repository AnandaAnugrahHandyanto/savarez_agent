# Herald Coordinator - Setup Guide

## Quick Start (5 minutes)

```bash
# 1. Create the herald config directory
mkdir -p ~/.herald

# 2. Copy the project status file
cp project-status.json ~/.herald/project-status.json

# 3. Install dependencies
pip install anthropic requests python-dateutil

# 4. Set your API key
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# 5. Run it
python coordinator.py
```

That's it. You'll get a daily briefing printed to console and saved to `~/.herald/daily-briefing.md`.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (if using Claude) | - | Your Anthropic API key |
| `GITHUB_TOKEN` | No | - | GitHub PAT for repo activity data |
| `NTFY_TOPIC` | No | `mike-coordinator` | ntfy.sh topic for push notifications |
| `COORDINATOR_PROVIDER` | No | `anthropic` | `anthropic` or `ollama` |
| `COORDINATOR_MODEL` | No | `claude-haiku-4-5-20251001` | Model to use for briefing |
| `OLLAMA_URL` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3.2` | Ollama model name |
| `PROJECT_STATUS_PATH` | No | `~/.herald/project-status.json` | Path to status file |

### Editing Project Status

The coordinator reads `~/.herald/project-status.json` fresh on every run. Update it whenever project state changes:

- Changed a project's phase? Update `current_phase` and the relevant `phase_plan` entry's `status`.
- Hit a new blocker? Add it to `blockers`.
- Resolved a blocker? Remove it.
- Priorities shifted? Adjust `priority_score` (1-10, 10 being highest).
- Delegated something? Move it from `blockers` to `delegatable_tasks`.

The coordinator will adapt its recommendations based on whatever it finds.

## Daily Automation

### Option A: Cron (Linux/Mac)

```bash
# Run at 7am every day, send notification
crontab -e

# Add this line:
0 7 * * * cd /path/to/coordinator && /usr/bin/python3 coordinator.py --notify --quiet
```

### Option B: Task Scheduler (Windows)

```powershell
# Create a scheduled task that runs at 7am daily
schtasks /create /tn "Herald Coordinator" /tr "python C:\path\to\coordinator.py --notify --quiet" /sc daily /st 07:00
```

### Option C: n8n Workflow (Your VPS)

1. Create a new n8n workflow
2. Add a **Cron** trigger node: `0 7 * * *` (7am daily)
3. Add an **Execute Command** node:
   ```
   cd /opt/herald-coordinator && python3 coordinator.py --notify --dashboard --quiet
   ```
4. Optionally add a **Webhook** node to trigger on-demand from your iOS Shortcut

### Option D: iOS Shortcut (Fire-and-Forget)

Using your existing iOS Shortcut → n8n → VPS pipeline:

1. Create an iOS Shortcut called "Daily Briefing"
2. Action: **Get Contents of URL** → POST to your n8n webhook URL
3. n8n receives the webhook, runs the coordinator, sends result to ntfy.sh
4. You get the briefing as a push notification

This means you can also trigger a briefing on-demand by tapping the shortcut — not just on the morning schedule.

## Using with Local LLM (Ollama)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (13B recommended for quality briefings at 32GB RAM)
ollama pull llama3.2:13b

# Run coordinator with Ollama
python coordinator.py --provider ollama
```

The local option costs nothing and works offline. Quality is noticeably lower than Claude Haiku but still useful for daily coordination. Recommended for cost-conscious daily runs, with Claude API for weekly deep reviews.

## Dashboard

```bash
python coordinator.py --dashboard
# Opens ~/.herald/dashboard.html
```

The dashboard shows all projects as cards (sorted by priority), with status indicators, current phase, blocker count, and the full AI-generated briefing below. Dark theme, Herald aesthetic.

## Cost

Using Claude Haiku: approximately £0.005-0.01 per briefing (less than 1p).
Running daily for a month: approximately £0.15-0.30.
Using Ollama: £0.00 forever.

## Extending the Coordinator (Phase 2+)

The coordinator is designed to be the foundation for a more capable agent system:

### Near-term additions:
- **Google Calendar integration**: Add upcoming events to the briefing context
- **Gmail integration**: Add unread count and important sender summaries
- **Slack integration**: Add unread message counts per channel
- **VPS health check**: Ping your Hetzner VPS and report service status

### Medium-term (Phase 2: Tool User):
- **Claude Code dispatch**: Coordinator identifies delegatable tasks and queues them as Claude Code prompts on the VPS
- **GitHub automation**: Create issues, assign labels, close stale items
- **Status file auto-update**: Agent updates project-status.json based on observed changes

### Long-term (Phase 3+: Autonomous Worker):
- **Multi-agent coordination via ACR**: The coordinator becomes the orchestrator in the ACR pipeline
- **Automated testing**: Browser-Use/Playwright running test suites overnight
- **Automated content**: Draft LinkedIn posts, client updates, release notes
- **Life dashboard**: Full Herald integration with voice briefing

## File Structure

```
~/.herald/
├── project-status.json    # YOUR project states (edit this regularly)
├── daily-briefing.md      # Latest generated briefing
├── dashboard.html         # Latest generated dashboard
├── google_tokens.json     # Google OAuth tokens (Phase 2)
└── logs/
    └── 2026-04-09.md      # Archived briefings by date
```

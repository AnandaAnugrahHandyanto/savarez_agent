# Nash-AI Phase 1: Get OpenClaw Running Locally in Docker

## Context

I'm Mike Nash, a solo developer running 6 concurrent projects from my ASUS TUF F15 laptop (16GB DDR5, Windows). I need a personal AI assistant to coordinate my work, automate tasks, and eventually run 24/7 on my Hetzner VPS.

The plan is: prove the concept locally in Docker first, then migrate to VPS once it's working.

I have three reference documents attached that cover the full phased plan:
- **nash-ai-phase1-local-docker-setup.md** — step-by-step Docker setup guide
- **nash-ai-phase2-skills-and-automation.md** — skills, project integration, Prism/ACR sandbox
- **nash-ai-phase3-vps-migration.md** — VPS deployment with local LLM

I also have:
- **project-status.json** — the state of all 6 projects (Herald, Conductor, Optimal You, ACR, Prism, consultancy)
- **coordinator.py** — a daily briefing script that reads project state and generates prioritised action plans
- **NASH-AI-Virtual-Assistant-Setup.md** — full context dump covering vision, infrastructure, OpenClaw architecture, and skill designs

## What I Need You To Do

Walk me through getting OpenClaw running in Docker on my Windows laptop, step by step. I'm comfortable with code but I don't know Linux well, so keep commands clear and explain what they do.

### Specifically:

1. **Check prerequisites** — make sure I have Docker Desktop and Git installed. If not, guide me through installing them.

2. **Clone and set up OpenClaw** — follow the Phase 1 doc but adapt for any issues we hit. The Docker setup uses `bash scripts/docker/setup.sh` which may need Git Bash on Windows.

3. **Configure the LLM provider** — start with OpenRouter free tier (I'll create an account if I don't have one). We want zero cost while testing. Use a free model like Gemma or Llama.

4. **Connect Telegram** — walk me through creating a Telegram bot via BotFather and connecting it to OpenClaw. This is my primary mobile interface.

5. **Verify the WebChat dashboard** — make sure localhost:18789 loads and I can see live agent activity in my browser.

6. **Set up the shared workspace** — verify the `~/openclaw/workspace` folder is visible in Windows Explorer and that the agent can read/write files there.

7. **Load project context** — copy project-status.json into the workspace and verify the agent can read it and answer questions about my projects.

8. **Install the coordinator skill** — port the coordinator as an OpenClaw skill so I can message `/briefing` and get my daily action plan.

9. **Test basic capabilities** — run through these verification tests:
   - "What are my projects and priorities?" (reads project-status.json)
   - "Create a test file in the workspace" (file creation)
   - "What day is it and what should I focus on?" (reasoning)
   - `/briefing` command (coordinator skill)

10. **Troubleshoot** — if anything breaks (and it probably will), help me fix it. Check docker logs, config files, permissions, whatever's needed.

## Constraints

- Everything must run inside Docker — the agent cannot access my machine outside the workspace folder
- Zero API cost for now — use OpenRouter free tier or any free model provider
- I need to SEE what it's doing — WebChat dashboard must be accessible
- Don't skip steps or assume things work — verify each step before moving to the next
- If something doesn't work on Windows, find the workaround rather than saying "use Linux"

## When Phase 1 Is Done

I should be able to:
- Message my agent on Telegram and get intelligent responses about my projects
- See live activity in the WebChat dashboard at localhost:18789
- See files the agent creates appear in my Windows Explorer
- Run `/briefing` and get a prioritised daily action plan
- Feel confident that the sandbox is isolated and safe

Then we move to Phase 2: connecting my actual project repos and automating real tasks.

## Begin

Start by checking what I have installed (Docker, Git) and guide me from there.

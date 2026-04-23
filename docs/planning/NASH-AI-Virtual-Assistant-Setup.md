# Project NASH-AI: Personal Virtual Assistant
## Full Context Handoff for Claude

### What This Document Is

This is a comprehensive context dump for Claude (any session) to help Mike Nash build a personal AI virtual assistant that runs 24/7 on his Hetzner VPS. It captures the full vision, current infrastructure state, available tools, and phased build plan. Give this to any Claude session and it should be able to pick up and help immediately.

---

## 1. Who Is Mike

Mike Nash is the founder of Nash Software Services Ltd, a UK-based solo developer and fractional CTO. He runs 5+ concurrent products and a consultancy from Otley, West Yorkshire. He's stretched thin across multiple projects that are all at different stages of completion, and needs an AI assistant that can coordinate his work, take autonomous actions, and progressively reduce his bottleneck across everything.

**Current projects (priority order):**
1. **Nash Software Services** (consultancy) — immediate revenue, needs LinkedIn content and lead gen
2. **Herald** — novelty desktop app, full GTM plan and build spec complete, ready to build, near-term revenue
3. **Conductor** — Terminal Development Environment, publicly launched, needs stabilisation
4. **Optimal You** — fitness/recovery app, in personal testing phase, blocked by manual testing overhead
5. **ACR** — Agent Control Room, architecture complete, no code yet, long-term vision
6. **Prism** — 12-tier AI model router, design complete, waiting for a consumer

**Key pain points:**
- Context-switching between projects kills momentum
- Manual testing eats hours of low-value time
- Every project is blocked on Mike personally — he's the sole bottleneck
- Great at architecture and planning, needs to ship more
- Needs income flowing while building long-term products

---

## 2. The Vision

A personal AI assistant ("Nash-AI") running on Mike's Hetzner VPS that:

1. **Knows all projects** — reads project status files, GitHub repos, n8n workflow states
2. **Coordinates daily** — generates prioritised action plans each morning
3. **Takes actions autonomously** — runs scripts, creates GitHub issues, sends messages, triggers deployments
4. **Tests automatically** — runs Playwright/Browser-Use test suites overnight on Optimal You and other apps
5. **Manages communications** — drafts LinkedIn posts, client emails, Slack messages
6. **Routes intelligence** — uses Prism to send complex tasks to Claude (via session token or API) and routine tasks to local/cheap models
7. **Learns and adapts** — remembers what worked, what didn't, what Mike's priorities actually are vs what he says they are
8. **Is always on** — runs 24/7 on the VPS, accessible via WhatsApp/Telegram/Discord and a web dashboard

---

## 3. Current Infrastructure

### Hetzner VPS (existing)
- **Current spec:** 16GB RAM (considering upgrade to 32GB at €32.40/month vs current €16.40/month)
- **Domain:** ide.nashsoftware.dev
- **Running:** Caddy (reverse proxy), code-server (VS Code in browser), n8n (workflow automation), Tailscale (VPN mesh)
- **Access:** SSH, Tailscale, web via Caddy
- **OS:** Ubuntu (likely 22.04 or 24.04)

### Existing Tooling
- **n8n** — workflow automation, already running on VPS. Webhooks, scheduling, API calls
- **Claude Code** — used extensively with custom skills library, hooks, and automation
- **Conductor** — Mike's own TDE, running on VPS at ide.nashsoftware.dev
- **Tailscale** — mesh VPN connecting laptop ↔ VPS ↔ any future devices
- **ntfy.sh** — push notifications, used for fire-and-forget agent run completions
- **iOS Shortcuts** — mobile trigger pipeline: Shortcut → n8n webhook → VPS → Claude Code → ntfy.sh
- **GitHub** — repos under nash-software org
- **Skills library** — custom SKILL.md files for Claude Code (same pattern as OpenClaw skills)

### Mike's Laptop
- **ASUS TUF F15** — 16GB DDR5-4800 RAM (1 slot free, max 64GB), ~4GB VRAM
- **Constraint:** Can't run large local LLMs alongside dev workload at 16GB. RAM upgrade on hold due to DDR5 price spike (£195+ for 16GB, £270+ for 32GB)

---

## 4. The Agent Platform: OpenClaw

**Why OpenClaw:** It's the most capable open-source personal AI agent available right now. It runs locally (on VPS), has 100+ built-in skills, integrates with messaging platforms, supports a heartbeat scheduler for autonomous operation, uses a skill system identical to Mike's existing Claude Code skill pattern, and is model-agnostic (works with Claude, GPT, Gemini, local Ollama, or any OpenAI-compatible API).

**Key OpenClaw capabilities relevant to Mike:**
- **Multi-channel inbox** — WhatsApp, Telegram, Slack, Discord as interfaces
- **Shell command execution** — run scripts, git operations, deployments
- **Browser automation** — via built-in browser skill (Playwright under the hood)
- **File system access** — read/write project files, config, status docs
- **Cron/heartbeat** — autonomous scheduled tasks without prompting
- **Memory** — persistent context stored as local Markdown files
- **Skill extensibility** — custom skills in SKILL.md format (Mike already knows this pattern)

**Security considerations:**
- OpenClaw has had security issues (CVE-2026-25253). Mike's VPS is behind Tailscale which mitigates external exposure
- Skills from the community registry should be audited. Mike should write his own skills for sensitive operations
- The VPS is already a sandboxed environment separate from Mike's laptop

### Installation on VPS
```bash
# SSH into VPS
ssh mike@ide.nashsoftware.dev

# Install OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash

# Run onboarding
openclaw onboard --install-daemon

# Configure AI provider (Claude via session token, or API key, or Prism)
# Connect messaging channels (WhatsApp/Telegram)
# Install relevant skills
```

---

## 5. Intelligence Routing via Prism

Mike's Prism project is a 12-tier deterministic AI model router. It's nearly working. The idea is to connect OpenClaw → Prism → multiple LLM backends:

```
OpenClaw Agent
    │
    ▼
  Prism Router
    │
    ├── Tier 1: Local Ollama (3B model) — status checks, simple lookups
    ├── Tier 2: Free providers (Mistral, Gemini Flash) — routine tasks
    ├── Tier 3: Claude Haiku (API key) — coordination, drafting, summaries
    ├── Tier 4: Claude Sonnet (API key) — code generation, complex reasoning
    └── Tier 5: Claude Opus (session token via Conductor) — deep architecture, critical decisions
```

This means the agent uses the cheapest/fastest model capable of each task. Routine "what's the status of X" queries cost nothing. Complex "review this architecture and suggest improvements" queries route to Opus.

**Conductor integration:** Mike already has Conductor running on the VPS with a local session token for Claude. This gives him access to Claude (including Opus) for deep reasoning tasks without API costs. OpenClaw can route through Conductor for these premium queries.

**Implementation priority:** Get OpenClaw running with a single provider first (Claude API key on Haiku). Add Prism routing in Phase 2 once the basic agent is stable.

---

## 6. The Coordinator (Already Built)

A Phase 1 daily briefing system has already been built (coordinator.py). It:
- Reads project-status.json (all 6 projects with phases, blockers, delegatable tasks)
- Enriches with live GitHub data (PRs, commits, issues)
- Sends everything to Claude Haiku
- Outputs a prioritised daily action plan
- Can push to ntfy.sh and generate an HTML dashboard

**Files:** coordinator.py, project-status.json, coordinator-setup.md

This coordinator becomes an OpenClaw skill — it runs on the heartbeat scheduler every morning and sends the briefing to Mike via WhatsApp/Telegram.

---

## 7. Phased Build Plan

### Phase 1: Foundation (Day 1-2)
**Goal:** OpenClaw running on VPS, connected to WhatsApp/Telegram, basic skills working.

Tasks:
- [ ] Upgrade VPS to 32GB if budget allows (€32.40/month), otherwise stay at 16GB
- [ ] Install OpenClaw on VPS
- [ ] Configure Claude Haiku as primary LLM provider
- [ ] Connect WhatsApp or Telegram as primary messaging interface
- [ ] Install core skills: shell, browser, file system, git
- [ ] Port coordinator.py as an OpenClaw skill (daily briefing on heartbeat)
- [ ] Test: send a message via WhatsApp, get a response from the agent
- [ ] Test: trigger daily briefing manually, verify it arrives via message

### Phase 2: Project Awareness (Day 3-5)
**Goal:** Agent knows all projects, can answer questions about status, can take basic actions.

Tasks:
- [ ] Create project-context skills — one per project with SKILL.md containing: vision, current state, repo location, phase plan, key files
- [ ] Connect GitHub skills — agent can list PRs, issues, recent commits per repo
- [ ] Connect n8n skills — agent can trigger workflows, check status
- [ ] Create status-update skill — agent can update project-status.json based on observations
- [ ] Create git-operations skill — create branches, commit, push, open PRs
- [ ] Test: "What's the status of Conductor?" → agent checks GitHub and answers
- [ ] Test: "Create an issue on the Herald repo for X" → agent creates it

### Phase 3: Autonomous Actions (Week 2)
**Goal:** Agent does things without being asked. Overnight work queue.

Tasks:
- [ ] Create overnight-queue skill — Mike queues tasks in the evening, agent executes overnight on VPS
- [ ] Connect Claude Code as a tool — agent can dispatch Claude Code sessions for coding tasks
- [ ] Create auto-test skill — Playwright tests for Optimal You, runs nightly, reports results
- [ ] Create LinkedIn-draft skill — agent drafts LinkedIn posts based on project milestones
- [ ] Create email-draft skill — agent drafts client/collaborator emails
- [ ] Set up heartbeat tasks: morning briefing (7am), overnight queue (11pm), test runs (2am)
- [ ] Add Prism routing — connect Prism for intelligent model selection
- [ ] Test: queue "Write Conductor documentation for X" → wake up to completed draft

### Phase 4: Intelligence Layer (Week 3-4)
**Goal:** Agent becomes genuinely intelligent about priorities, patterns, and decisions.

Tasks:
- [ ] Create priority-engine skill — agent analyses all projects and recommends daily focus (not just summarise, actually reason about trade-offs)
- [ ] Add revenue-tracking — agent knows about consultancy pipeline, Herald sales, income targets
- [ ] Create blocker-detection — agent identifies when a project has been stalled for >N days and escalates
- [ ] Add retrospective skill — weekly summary of what was accomplished, what slipped, what to adjust
- [ ] Connect Optimal You data — agent knows fitness/recovery state and can factor energy levels into planning
- [ ] Route complex reasoning through Conductor/Opus — architecture reviews, strategic decisions
- [ ] Create life-dashboard — web dashboard on VPS showing all projects, priorities, revenue, health, agent activity

### Phase 5: Full Automation (Month 2+)
**Goal:** Agent manages significant portions of the workflow autonomously.

Tasks:
- [ ] Browser-Use integration — agent can navigate web UIs, fill forms, do manual testing tasks
- [ ] Smart home integration — if applicable, morning routines, lighting, etc.
- [ ] Voice interface — Whisper STT + TTS on laptop, talk to agent naturally
- [ ] Herald integration — clap twice, get briefed by the agent
- [ ] ACR integration — as ACR gets built, the agent becomes the first user of the orchestration pipeline
- [ ] Multi-agent routing — specialist sub-agents for coding, testing, comms, coordination
- [ ] Community skill contributions — share useful skills back to OpenClaw ecosystem

---

## 8. Key Skills to Build (Custom)

These are Mike-specific skills that don't exist in the OpenClaw registry:

### nash-coordinator
Runs the daily briefing system. Reads project-status.json, enriches with GitHub data, generates prioritised action plan.
```
Trigger: heartbeat (7:00 AM daily)
Input: project-status.json, GitHub API
Output: Prioritised briefing sent via messaging channel
```

### nash-project-status
Reads and updates the project status file. Agent can mark phases complete, add/remove blockers, adjust priorities.
```
Trigger: on-demand or after completing tasks
Input: project-status.json
Output: Updated project-status.json
```

### nash-overnight-queue
Manages a queue of tasks to execute while Mike sleeps. Tasks are added via message during the day, executed sequentially overnight.
```
Trigger: heartbeat (11:00 PM daily)
Input: ~/.nash-ai/overnight-queue.json
Output: Completed tasks, results sent via message in morning
```

### nash-claude-code-dispatch
Sends a task to Claude Code on the VPS. Wraps the task in a proper prompt with relevant context, monitors execution, reports results.
```
Trigger: on-demand or from overnight queue
Input: Task description + relevant project context
Output: Claude Code session result + any created files/PRs
```

### nash-auto-test
Runs Playwright test suites against Optimal You (and other apps). Screenshots failures, creates GitHub issues for bugs.
```
Trigger: heartbeat (2:00 AM daily) or on-demand
Input: Test scripts in ~/.nash-ai/tests/
Output: Test report, screenshots, GitHub issues for failures
```

### nash-linkedin-content
Drafts LinkedIn posts based on project milestones, lessons learned, or industry topics. Matches Mike's existing LinkedIn voice and style.
```
Trigger: on-demand or weekly heartbeat
Input: Recent project activity, milestone completions
Output: Draft post sent for review via message
```

### nash-revenue-tracker
Tracks income across consultancy and product sales. Compares against targets. Flags when income is below threshold.
```
Trigger: weekly heartbeat
Input: Gumroad API (Herald sales), manual invoice entries
Output: Revenue summary, comparison to targets
```

---

## 9. Configuration Files

### OpenClaw config (agent personality)
```yaml
# ~/.openclaw/config.yaml (conceptual)
agent:
  name: "Nash-AI"
  personality: "Direct, efficient, slightly dry humour. Knows Mike's tendency to over-plan and under-execute. Nudges toward shipping. Prioritises revenue-generating work when income is needed. Never sycophantic."
  
providers:
  primary: 
    type: anthropic
    model: claude-haiku-4-5-20251001
    api_key: ${ANTHROPIC_API_KEY}
  deep_reasoning:
    type: conductor  # Route through Conductor for Opus access
    endpoint: http://localhost:PORT
  local:
    type: ollama
    model: llama3.2:3b  # For status checks and simple lookups
    url: http://localhost:11434

heartbeat:
  morning_briefing: "0 7 * * *"    # 7am daily
  overnight_queue: "0 23 * * *"     # 11pm daily  
  auto_tests: "0 2 * * *"          # 2am daily
  weekly_retro: "0 9 * * 1"        # Monday 9am
  linkedin_draft: "0 10 * * 3"     # Wednesday 10am

channels:
  primary: whatsapp  # or telegram
  notifications: ntfy
```

### Project Status File Location
```
~/.nash-ai/project-status.json     # Master project state (already created)
~/.nash-ai/overnight-queue.json    # Overnight task queue
~/.nash-ai/tests/                  # Playwright test scripts
~/.nash-ai/skills/                 # Custom Nash-AI skills
~/.nash-ai/logs/                   # Daily briefings, test reports, activity logs
~/.nash-ai/dashboard/              # HTML dashboard files
```

---

## 10. VPS Upgrade Decision

### Current: CX42 (16GB RAM, 8 vCPU) — €16.40/month
- Runs: Caddy, code-server, n8n, Tailscale
- Adding: OpenClaw (Node.js process, ~200-500MB)
- Tight but workable if not running local LLM

### Upgrade: CX52 (32GB RAM, 16 vCPU) — €32.40/month
- Everything above plus:
- Can run Ollama with a 3B-7B model for cheap/fast queries
- More headroom for Claude Code sessions + OpenClaw simultaneously
- Better for overnight queue running multiple tasks in parallel

### Recommendation
Start with 16GB. OpenClaw + Claude API (no local LLM) runs fine on 16GB. If/when you add Ollama for local inference, upgrade to 32GB. Hetzner lets you scale up instantly via their API or dashboard, no migration needed — it's a button click.

---

## 11. Security Considerations

- **VPS is behind Tailscale** — not exposed to public internet except through Caddy-proxied services. This mitigates OpenClaw's known WebSocket hijacking vulnerability
- **OpenClaw WebChat port** should NOT be exposed publicly. Access only via Tailscale
- **Skills:** Write custom skills for sensitive operations. Don't install unvetted community skills
- **API keys:** Store in environment variables, not in config files. Use a .env file with restricted permissions
- **Session tokens:** Conductor session tokens should be rotated regularly
- **GitHub tokens:** Use fine-grained PATs with minimum required scopes
- **Destructive actions** (deployments, external emails, spending money) should require human confirmation via messaging channel before execution

---

## 12. Getting Started Checklist

Immediate actions (today):
- [ ] SSH into VPS, check current resource usage (htop, free -h)
- [ ] Install OpenClaw: `curl -fsSL https://openclaw.ai/install.sh | bash`
- [ ] Run onboarding: `openclaw onboard --install-daemon`
- [ ] Set ANTHROPIC_API_KEY in environment
- [ ] Connect WhatsApp or Telegram
- [ ] Send first message: "What can you do?"
- [ ] Upload project-status.json to ~/.nash-ai/
- [ ] Port coordinator.py as an OpenClaw skill
- [ ] Set up morning briefing on heartbeat (7am)
- [ ] Send Mike a "good morning" test briefing

Within this week:
- [ ] Create project-context skills for each of the 6 projects
- [ ] Connect GitHub integration
- [ ] Set up overnight queue
- [ ] Write first Playwright test for Optimal You
- [ ] Have the agent draft its first LinkedIn post for review

---

## 13. Reference Documents

These documents contain the detailed specifications for various components referenced above:

| Document | Contents |
|---|---|
| Herald-GTM-Plan-v2.docx | Marketing strategy, pricing, content calendar, financial model |
| Herald-Build-Spec.docx | Technical architecture, data models, APIs, clap detection, HUD system |
| Herald-Build-Spec-Addendum-Integrations.docx | OAuth flows, AI briefing layer, multi-provider LLM support |
| Herald-Project-Index.docx | Master document index, HUD prototype reference, build order |
| jarvis-hud-demo.jsx | Working React prototype of Herald HUD overlay |
| HERALD-BUILD-PROMPT.md | Claude Code prompt to build Herald from the specs |
| coordinator.py | Phase 1 daily briefing coordinator script |
| project-status.json | All 6 project states with phases, blockers, delegatable tasks |
| coordinator-setup.md | Setup guide for the coordinator (cron, n8n, iOS Shortcuts) |

---

## 14. The Meta-Goal

The assistant isn't just a tool — it's the proof of concept for ACR. By building Nash-AI as a personal agent first, Mike:

1. Solves his immediate coordination problem
2. Generates real-world requirements for ACR's agent orchestration pipeline  
3. Has a working demo for the consultancy ("I built an AI that manages my 5 concurrent products")
4. Learns what works and what doesn't before productising it
5. Can progressively migrate Nash-AI's architecture INTO ACR as ACR gets built

The end state: Nash-AI runs on ACR, ACR is the product, and the personal assistant becomes the reference implementation that sells the platform.

---

*Last updated: April 2026*
*Nash Software Services Ltd*

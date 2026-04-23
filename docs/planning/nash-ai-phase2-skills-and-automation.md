# Nash-AI Phase 2: Skills, Automation & Project Integration

## Prerequisites

Phase 1 complete — OpenClaw running in Docker, WebChat working, Telegram connected, workspace folder accessible, basic commands tested.

---

## Goal

Get the agent doing useful things with your actual projects. Connect Prism and ACR into the sandbox so the agent can test and iterate on them. Automate 2-3 real daily tasks. Prove this is worth the VPS investment.

---

## 1. Connect Your Project Repos

The agent needs access to your code. Rather than giving it your entire machine, mount specific repos into the workspace.

Edit `docker-compose.yml` in the openclaw directory. Find the volumes section and add your project repos:

```yaml
volumes:
  - ~/.openclaw:/home/node/.openclaw
  - ~/openclaw/workspace:/home/node/.openclaw/workspace
  # Add your project repos as read-write mounts:
  - C:/path/to/prism:/home/node/.openclaw/workspace/prism
  - C:/path/to/acr:/home/node/.openclaw/workspace/acr
  - C:/path/to/conductor:/home/node/.openclaw/workspace/conductor
  - C:/path/to/optimal-you:/home/node/.openclaw/workspace/optimal-you
  - C:/path/to/herald:/home/node/.openclaw/workspace/herald
```

Restart: `docker compose restart`

Now the agent can see and modify your project files directly. Changes it makes appear in your repos in real-time.

---

## 2. Prism Integration

This is the first real test — get Prism running inside the Docker environment so OpenClaw can use it for model routing.

### Step 1: Let the agent explore Prism

Message the agent:

> "Look at the prism directory in your workspace. Read the README and source code. Tell me what state it's in, what's working, what's broken, and what needs fixing."

The agent will read through the codebase and give you an honest assessment. This alone saves you an hour of context-switching back into the Prism codebase.

### Step 2: Let the agent fix issues

> "Based on your analysis of Prism, fix the top 3 issues you identified. Create a new branch called `fix/agent-fixes`, make the changes, and show me a summary of what you changed."

The agent runs git commands, edits files, and commits. You review the changes in Windows Explorer or your normal git workflow.

### Step 3: Connect Prism as OpenClaw's model router

Once Prism is working, configure OpenClaw to route through it:

> "Set up Prism to run as a local service inside this environment. Then configure yourself to use Prism as your model router instead of calling OpenRouter directly. Prism should route simple tasks to free models and complex tasks to Claude via my API key."

This is where it gets powerful — the agent is now using your own tool to optimise its own intelligence routing.

---

## 3. ACR Integration

ACR's architecture is done but has no code. The Docker sandbox is the perfect place to bootstrap it.

### Step 1: Context load

Copy the ACR architecture document into the workspace. Then:

> "Read the ACR architecture document. This is my Agent Control Room — a 17-state pipeline for orchestrating autonomous AI agents. I want you to scaffold the core implementation. Start with the state machine and SQLite/WAL layer. Create the project structure and initial code in the acr directory."

### Step 2: Iterative development

The agent scaffolds, you review, it iterates. All inside the sandbox. If it breaks something, the container is disposable. If it creates something good, the changes are in your mounted repo directory ready to commit.

> "Run the ACR tests. Fix any failures. Then implement the next component from the architecture doc."

This is the dream loop — the agent builds ACR, tests it, fixes issues, and advances the project while you focus on other things.

---

## 4. Daily Coordinator Skill

Port the coordinator as a proper OpenClaw skill.

Create this file in `~/openclaw/workspace/skills/nash-coordinator/SKILL.md`:

```markdown
---
name: nash-coordinator
description: Daily project coordinator for Mike Nash. Reads project status, analyses priorities, generates action plan.
triggers:
  - heartbeat: "0 7 * * *"
  - command: "/briefing"
  - keyword: "daily briefing"
---

# Nash Coordinator

You are Mike Nash's daily project coordinator. Your job is to read project-status.json from the workspace, analyse the state of all projects, and generate a prioritised daily action plan.

## When triggered (morning heartbeat or /briefing command):

1. Read `/workspace/project-status.json`
2. Check recent git activity in each project directory (if mounted)
3. Note the current day and time
4. Generate a briefing following this format:

### Briefing Format

Start with a 2-sentence overall assessment.

**Today's Top 3 Actions:**
- Specific, concrete, with time estimates and reasoning

**Delegate Tonight (Claude Code queue):**
- Tasks that can run autonomously overnight

**Honest Assessment:**
- What's going well, what's slipping, what Mike needs to hear

## Principles:
- Revenue-generating work takes priority when income is needed
- A project at 90% should be finished before starting something new
- Delegation to Claude Code is always preferred over Mike doing it manually
- Mike tends to over-plan and under-execute — nudge toward shipping
- Keep it under 500 words. Be direct, warm, actionable.
```

Install the skill:

```powershell
# Skills in the workspace/skills directory are auto-loaded
docker compose restart
```

Test it: message `/briefing` on Telegram. You should get your daily action plan.

---

## 5. Automated Testing Skill

Create `~/openclaw/workspace/skills/nash-auto-test/SKILL.md`:

```markdown
---
name: nash-auto-test
description: Automated testing for Optimal You and other Nash Software projects using the browser skill.
triggers:
  - command: "/test optimal-you"
  - command: "/test all"
---

# Nash Auto Test

Run automated tests against Nash Software projects using browser automation.

## When triggered with /test optimal-you:

1. Open the browser to the Optimal You URL (configured in project-status.json)
2. Navigate through the core user flows:
   - Login / registration
   - Create a new workout
   - Add exercises to workout
   - Open the body map, select joints
   - Save and review
3. Screenshot each step
4. Save screenshots to /workspace/test-results/YYYY-MM-DD/
5. Report results: what passed, what failed, with screenshots

## When triggered with /test all:

Run test suites for all projects that have defined test flows.

## Error handling:
- If a page doesn't load, screenshot and report as FAIL
- If an element isn't found, wait 5 seconds and retry once
- Log all errors with timestamps
```

Test it: `/test optimal-you` on Telegram. Watch the WebChat dashboard as it automates the browser.

---

## 6. LinkedIn Content Skill

Create `~/openclaw/workspace/skills/nash-linkedin/SKILL.md`:

```markdown
---
name: nash-linkedin
description: Draft LinkedIn posts for Mike Nash based on project milestones and industry topics.
triggers:
  - command: "/linkedin"
  - heartbeat: "0 10 * * 3"  # Wednesday 10am
---

# Nash LinkedIn Content

Draft LinkedIn posts for Mike Nash's professional profile.

## Mike's LinkedIn voice:
- Technical but accessible
- First-person, conversational
- Shares real experiences and lessons from building products
- Occasionally contrarian or provocative
- Always includes a practical takeaway
- Often references the indie hacker / solo developer journey
- UK-based perspective

## When triggered:

1. Check recent project activity (git commits, milestones, files in workspace)
2. Draft a LinkedIn post (150-250 words) about a recent achievement, lesson, or insight
3. Include a hook in the first line
4. End with a question or call to discussion
5. Suggest 3-5 relevant hashtags
6. Present the draft for Mike's review before posting

## Topic ideas to rotate:
- Project milestones (Herald launch, Conductor update, etc.)
- AI workflow optimisation lessons
- Indie developer / solo founder journey
- Technical insights (architecture decisions, tool choices)
- Fractional CTO observations
```

Test: `/linkedin` on Telegram. Review the draft, provide feedback, iterate.

---

## 7. Overnight Task Queue

Create `~/openclaw/workspace/skills/nash-overnight-queue/SKILL.md`:

```markdown
---
name: nash-overnight-queue
description: Queue tasks during the day that execute overnight via shell/Claude Code.
triggers:
  - command: "/queue"
  - command: "/queue-run"
  - command: "/queue-status"
---

# Nash Overnight Queue

Manage a queue of tasks to execute when Mike is away.

## /queue <task description>
Add a task to the overnight queue. Save to /workspace/overnight-queue.json.
Confirm addition and show current queue.

## /queue-status
Show all queued tasks with their status.

## /queue-run (triggered by heartbeat at 11pm, or manually)
Execute all queued tasks sequentially:
1. Read overnight-queue.json
2. For each task:
   - Set status to "running"
   - Execute the task (shell commands, file operations, code changes)
   - Capture output and any errors
   - Set status to "complete" or "failed"
3. Send summary to Mike via Telegram when all tasks complete

## Task types:
- "Write documentation for X" → create/edit markdown files
- "Fix issue X in project Y" → edit code, run tests
- "Set up Playwright tests for Z" → create test scripts
- "Review and summarise file X" → read and produce summary
- "Run the test suite for project Y" → execute tests, report results
```

Usage throughout the day:
- `/queue Write Conductor docs for the plugin system`
- `/queue Fix the Prism routing bug where free models timeout`
- `/queue Set up a basic Playwright test for OY login flow`

Before bed: `/queue-run` or let the 11pm heartbeat handle it.

---

## 8. Measuring Success (Is This Worth the VPS?)

After 1 week of Phase 2, evaluate:

| Metric | Target | How to measure |
|---|---|---|
| Time saved on context-switching | 30+ min/day | Agent provides project context instantly |
| Manual testing replaced | 1+ hour/day | Auto-test skill runs nightly |
| Tasks completed overnight | 3+ per week | Overnight queue delivers results |
| LinkedIn posts drafted | 1 per week | Agent drafts, you review and post |
| Projects advanced without Mike | 1+ per week | ACR scaffolded, Prism fixed, docs written |
| Daily briefing usefulness | Actionable every day | You actually follow the recommendations |

If these targets are hit, the 32GB VPS at €32/month is justified. The time saved alone is worth far more than €32.

---

## Next Step

Once Phase 2 is proven and you're confident in the agent's capabilities, move to **Phase 3: VPS Migration** — snapshot the Docker config, deploy to the 32GB Hetzner instance, add Ollama with a local model, and make it always-on.

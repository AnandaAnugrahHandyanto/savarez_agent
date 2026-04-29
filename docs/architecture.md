# Architecture — Integration Surfaces and Hook Points

<!-- provenance: written from first principles; integration patterns distilled from Motion-Granted-Production -->

This document describes where tanner-stack connects to external systems and where future components can plug in.

---

## Current Integration Surface

### Claude Code Harness

tanner-stack runs inside Claude Code's harness. The `.claude/` directory configures the agent:

| File | Purpose |
|------|---------|
| `.claude/settings.json` | Model selection, permission allowlist/denylist, pre/post-tool hooks |
| `.claude/launch.json` | Dev server launcher configurations |
| `.claude/commands/*.md` | Slash-command workflows invokable as `/command-name` |
| `.claude/rules/*.md` | Path-scoped standing constraints, loaded when the relevant files are touched |

**Hook points in `settings.json`:**
- `PostToolUse` — runs after every Edit/Write. Use for: type checking, linting, formatting.
- `PreToolUse` — runs before every Edit/Write. Use for: blocking protected paths, dead code guards.

### GitNexus MCP

GitNexus is a code-intelligence MCP that connects the agent to a symbol and execution flow graph. When indexed, it enables impact analysis, safe renames, and change detection.

**Connection:** GitNexus connects as an MCP server. Once connected, the `gitnexus_*` tools become available in-session. See CLAUDE.md → GitNexus section for the full mandate.

**Index name:** Set your index name in CLAUDE.md by replacing `YOUR_REPO_NAME` everywhere in the GitNexus section. Run `npx gitnexus analyze` to create or refresh the index.

**Impact on workflow:** The AGENTS.md mandates that `gitnexus_impact` runs before every symbol edit. This is the primary integration point between tanner-stack's rigor discipline and GitNexus.

---

## Future Hook Points

The following integration targets are documented here as hook points — not yet implemented, but designed for when they're adopted.

### Swarm Mode

**What it is:** A parallel agent coordination layer where multiple Claude Code agents work concurrently on non-overlapping file sets.

**Current state:** The architect sub-agent's preloaded `swarm` skill (with a structured command wrapper at `.claude/commands/swarm.md`) implements single-session swarm decomposition (spawn subagents from a main thread). Full multi-process swarm coordination is not implemented.

**Plug-in point:** Swarm mode would connect at the sub-agent-selection layer in AGENTS.md. A swarm-coordinator sub-agent would replace the current single-agent IMPLEMENT mode. The `swarm` skill's decomposition protocol would become the communication standard between agents.

**What's needed to implement:** A coordination bus (shared state or message queue), a work-claiming protocol to prevent overlap, and a synthesis step for the main thread.

### Hermes (Notification / Routing Agent)

**What it is:** A lightweight agent responsible for routing findings and alerts between the main coding agent and human operators — Slack messages, GitHub comments, issue creation.

**Plug-in point:** Hermes would operate as a separate MCP-connected agent. It would hook into session-end events (from `session-end` skill) and violation events (from `/zt`). The `AGENTS.md` parallel agent rules would govern its coordination with the main agent.

**What's needed to implement:** An MCP server with Slack/GitHub write access, a finding serialization format, and routing rules.

### Mythos (Long-Term Memory Layer)

**What it is:** A persistent memory system that survives across sessions — project decisions, resolved debates, accumulated LEARNINGS beyond what fits in LEARNINGS.md.

**Plug-in point:** Mythos would connect at session start (read) and session end (write). The `session-start` and `session-end` skills are the current hook points. The `LEARNINGS.md` discipline is the manual equivalent.

**What's needed to implement:** A vector store or structured knowledge base, a retrieval protocol (what to load given current task), and a write discipline (what's worth persisting).

### Arsenal (Tool Registry)

**What it is:** A registry of available tools, MCPs, and capabilities that the agent can dynamically discover and load based on task context.

**Plug-in point:** Arsenal would operate at the session initialization phase, before mode selection. It would read the current task context and load the appropriate tool set.

**What's needed to implement:** A tool manifest format, a context-matching algorithm, and dynamic MCP loading capability.

---

## Dependency Graph (Current)

```
CLAUDE.md ──────────────── loads at session start (always)
AGENTS.md ──────────────── loaded by session-start skill
LEARNINGS.md ───────────── referenced in CLAUDE.md
BACKLOG.md ─────────────── written to during sessions
.claude/rules/*.md ──────── loaded when touching relevant paths
.claude/commands/*.md ───── invoked via /command-name
.claude/settings.json ───── loaded by Claude Code harness
.claude/agents/*.md ─────── delegated to via Claude Code native sub-agent routing
personas/*.md ───────────── reference-doc mirror of sub-agents (non-operational)
skills/*/SKILL.md ───────── invoked via /skill-name
GitNexus MCP ────────────── optional, loaded when connected
```

---

## Configuration Slots

When adopting tanner-stack, fill in these slots:

| Location | Slot | What to put |
|----------|------|-------------|
| `CLAUDE.md` | `YOUR_REPO_NAME` (GitNexus section) | Your GitNexus index name |
| `CLAUDE.md` | Inviolable Rules | Your project's non-negotiable constraints |
| `CLAUDE.md` | Project section | Stack, deploy target, key config files |
| `CLAUDE.md` | Commands section | Your dev/build/test commands |
| `CLAUDE.md` | DO NOT Edit | Your dead code paths and read-only dirs |
| `.claude/settings.json` | PreToolUse hook pattern | Your dead code file patterns |
| `.claude/settings.json` | PostToolUse hook command | Your type checker or build command |
| `.claude/launch.json` | configurations | Your dev server(s) |
| `.claude/rules/` | Add rule files | One per major subsystem |

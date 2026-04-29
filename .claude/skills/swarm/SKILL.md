<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/swarm/SKILL.md
Original purpose: Deploy parallel-agent swarms for broad audits or multi-file investigations.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: swarm
description: Deploy a swarm of parallel agents on isolated subtasks across multiple files or areas. INVOKE ONLY FROM WITHIN the architect sub-agent — architect owns the swarm go/no-go decision. DO NOT auto-fire from main-session "parallel" or "bulk task" signals; those route to architect first, which invokes this skill internally when warranted. Preloaded in .claude/agents/architect.md.
disable-model-invocation: true
argument-hint: "[task description and target areas]"
effort: max
---

# SWARM — Parallel Agent Deployment

Deploy multiple agents working in parallel on isolated subtasks.

**Task**: $ARGUMENTS

## Protocol

### 1. Decompose
Break the task into independent, non-overlapping subtasks. Each must:
- Target different files or areas (no two agents editing the same file)
- Be self-contained
- Have a clear deliverable

### 2. Deploy
Launch all agents simultaneously using subagents. Each gets its own context.

### 3. Collect & Synthesize
When all report back:
- Deduplicate findings
- Check for contradictions
- Identify cross-cutting issues individuals missed
- Compile unified report

## Swarm Patterns

**Audit Swarm** — one agent per codebase zone:
```
Agent 1: Audit src/<zone-A>/
Agent 2: Audit src/<zone-B>/
Agent 3: Audit src/<zone-C>/
Agent 4: Audit src/<zone-D>/
```

**Investigation Swarm** — one issue from multiple angles:
```
Agent 1: Trace upstream from error
Agent 2: Trace downstream from error
Agent 3: Search for sibling pattern instances
Agent 4: Check DB/schema state
```

**Review Swarm** — one agent per changed file after implementation.

**Smoke-Test Swarm** — one agent per tier, environment, or variant.

## Rules
- No two agents edit the same file
- Each agent reports certainty levels
- Synthesis step is mandatory
- Sort findings by severity

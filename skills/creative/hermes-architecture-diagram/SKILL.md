---
name: hermes-architecture-diagram
description: "Use when generating or updating the Hermes Agent architecture diagram HTML visualization. Auto-detects the current install's environment and includes a mandatory Bar Raiser verification gate that ground-truths every claim against the live system before delivery."
version: 1.2.0
author: Keith Motte TopofMind.AI
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [architecture, diagram, visualization, hermes, svg, html]
    related_skills: [hermes-agent, architecture-diagram]
---

# Hermes Architecture Diagram

## Overview

Interactive HTML/SVG architecture diagram for Hermes Agent. Auto-discovers the current Hermes install's environment and produces an accurate visualization. Works on any Hermes install — macOS, Linux, Windows/WSL — with any terminal backend (local, modal, docker, ssh).

The template at `templates/hermes-agent-architecture.html` is a reference implementation. When generating a new diagram, **always discover the current environment first** and customize the template to match.

## When to Use

- User asks to generate, update, or regenerate the architecture diagram
- User asks "how does Hermes work" and wants a visual
- Architecture has changed (new tools, new backend, new provider) and diagram needs updating
- Onboarding someone who needs to understand the Hermes stack
- Sharing Hermes architecture with a team or in documentation

## Step 1: Discover the Current Environment

Run the discovery script bundled with this skill:

    bash scripts/discover-env.sh

This outputs key=value pairs for OS, USERNAME, HOSTNAME, MODEL, PROVIDER, BACKEND, and TTS. Use these values to customize the diagram. If the script is not available, manually collect: `uname -s`, `whoami`, `hostname`, and read the model/provider/backend from the Hermes config.

Collect these values:
- `OS_NAME`: macOS / Linux / Windows (WSL)
- `USERNAME`: system username
- `HOSTNAME`: machine hostname
- `TERMINAL_BACKEND`: local / modal / docker / ssh / etc.
- `CURRENT_MODEL`: e.g. claude-opus-4.6, gpt-4o, deepseek-chat
- `CURRENT_PROVIDER`: e.g. nous, openrouter, anthropic, openai

## Step 2: Determine Diagram Topology

The terminal backend drives the fundamental diagram structure:

### LOCAL backend (local, default)
**Two-zone topology: Host + Cloud**
- Everything runs on the host machine
- terminal/file/code tools execute directly on host OS
- Persistent filesystem across sessions
- Full localhost, SSH, Docker access
- Green "LOCAL EXECUTION" zone inside host boundary

### REMOTE backend (modal, docker, ssh, singularity, daytona, managed_modal)
**Three-zone topology: Host + Sandbox + Cloud**
- Host runs the agent process, config, memory, skills
- Sandbox runs terminal/file/code tools (ephemeral or remote)
- Orange "SANDBOX" zone below host boundary
- Warning callout: ephemeral FS, no host access (modal/docker)

| Backend | Sandbox Label | Ephemeral? | Can reach host? |
|---------|--------------|------------|-----------------|
| local | (no sandbox) | No | Yes — IS the host |
| modal | Modal Sandbox (Linux) | Yes | No |
| docker | Docker Container | Configurable | Via volumes only |
| ssh | Remote Host | No | No (separate machine) |
| singularity | Singularity Container | Yes | Partial |
| daytona | Daytona Workspace | No | No |

## Step 3: Customize Template Values

Replace these placeholders in the template with discovered values:

| Template Value | Replace With |
|---------------|-------------|
| "Keith's Mac" | `{USERNAME}'s {HOSTNAME}` or `{HOSTNAME} ({OS_NAME})` |
| "(macOS)" | `({OS_NAME})` |
| "jblaze" | `{USERNAME}` |
| "claude-opus-4.6" | `{CURRENT_MODEL}` |
| "Nous Portal" | `{CURRENT_PROVIDER}` (capitalize first letter) |
| "Terminal backend: Local (macOS)" | `Terminal backend: {TERMINAL_BACKEND} ({OS_NAME})` |
| "zsh/bash" | `zsh/bash` (macOS), `bash` (Linux), `PowerShell/bash` (Windows) |
| "brew, git, npm" | `brew, git, npm` (macOS), `apt, git, npm` (Linux), `choco, git, npm` (Windows) |

## Step 4: Adjust for Backend-Specific Components

### If LOCAL backend:
- Keep the green "LOCAL EXECUTION" zone
- Keep the "Full Power" benefits callout
- Tool Dispatch arrows go DOWN to local tools (green arrows, "direct call")
- No cross-boundary arrows needed

### If MODAL/DOCKER backend:
- Replace green local zone with orange sandbox zone
- Replace benefits callout with warning callout about ephemeral FS
- Add thick cross-boundary arrow from Tool Dispatch to Sandbox
- Add dashed return arrow for stdout/stderr/exit_code
- Change tool box labels to reflect sandbox environment

### If SSH backend:
- Replace local zone with remote host zone (different color)
- Files persist on the remote, not locally
- Note SSH connection in arrows

## Step 5: Bar Raiser — Truth Verification Gate

**MANDATORY.** No diagram ships without passing this gate. Inspired by Amazon's Bar Raiser process — an independent verification that every claim in the diagram is grounded in evidence, not hallucinated.

Every generated diagram must pass the Bar Raiser checklist. Failures must be fixed. Only a fully-passing diagram should be presented as complete.

### Running the Bar Raiser

Run the verification script bundled with this skill:

    bash scripts/bar-raiser.sh ~/hermes-agent-architecture.html

Pass the path to the generated diagram. The script automatically:
1. Checks username, OS, hostname against the diagram text
2. Reads Hermes config to verify model/provider/backend claims
3. Validates topology matches the backend (local=2 zones, remote=3 zones)
4. Confirms SVG, cards, footer, and legend are present
5. Outputs a PASS/FAIL score with a sign-off watermark

Exit code 0 = all checks passed. Non-zero = number of failures.

### Bar Raiser Checklist

Score each item. ALL must pass. Any failure = fix before delivery.

**Identity and Environment (hard facts):**
- Username in diagram matches actual system username
- Hostname in diagram matches actual hostname
- OS label matches actual OS (Darwin=macOS, Linux=Linux)
- Shell reference correct for the OS
- Package manager correct for the OS

**Hermes Configuration (config ground truth):**
- Model name matches what is configured
- Provider name matches what is configured
- Terminal backend matches what is configured
- TTS provider matches what is configured (if shown)

**Topology (structural correctness):**
- Number of zones correct for the backend (local=2, remote=3)
- If local: green LOCAL EXECUTION zone present, no sandbox zone
- If remote: sandbox zone present with correct backend label
- If remote: cross-boundary arrow present with correct API label
- If local: benefits callout present
- If remote: warning callout present

**Components (no phantom features):**
- Every tool shown in diagram is actually enabled
- No disabled or unavailable tools shown as available
- Cloud services shown match what is actually configured

**Data Flow (arrow correctness):**
- Arrows follow the actual execution path for this backend
- Tool dispatch arrows go to the right target
- LLM arrows point to the correct provider

**Visual Integrity:**
- No overlapping text or clipped labels
- All SVG elements render in a browser
- Footer text matches all verified facts
- Info cards match the diagram content

### Escalation Rule

If you cannot verify a claim (config not readable, CLI not in PATH), you MUST:

1. **Flag it** — add a visible "UNVERIFIED" annotation to that part of the diagram
2. **Ask the user** — request confirmation of the unverifiable value
3. **Never guess** — a blank or "unknown" is better than a hallucinated value

A diagram with an honest "unverified" label has more integrity than one with a plausible-looking lie.

### Sign-Off Watermark

After all checks pass, the bar-raiser script outputs an HTML comment to embed in the diagram source. This watermark proves the diagram was verified, not just generated. It includes the timestamp, OS, user, host, model, provider, backend, and topology.

## Architecture Zones

### Zone 1: Host Machine
Purple dashed boundary. Always present on every install.

Components:
- **User Interfaces** (cyan): Platforms, CLI/TUI, Schedulers
- **Input Processing** (emerald): Gateway Router, CLI Router, Cron Engine
- **Persistent State** (rose): Memory + Skills
- **Core Engine** (emerald): Prompt Builder, Agent Loop, Tool Dispatch
- **Local Execution** (green): Only if backend=local

### Zone 2: Cloud Services
Amber dashed boundary. Always present.

Components:
- **LLM Providers** (amber): Current provider + model highlighted
- **Subagents** (emerald): delegate_task()
- **Browser** (orange): Browserbase/Camofox
- **Web Tools** (orange): Firecrawl
- **Image Gen** (orange): FAL
- **MCP Servers** (gray): stdio/HTTP transport

### Zone 3: Sandbox (only if remote backend)
Orange dashed boundary. Only present when terminal backend is NOT local.

Components: terminal(), File Tools, execute_code() — all run in sandbox.

## Color Scheme

| Component Type | Color | Hex |
|---------------|-------|-----|
| User Interface | Cyan | #22d3ee |
| Core Engine | Emerald | #34d399 |
| LLM Provider | Amber | #fbbf24 |
| Tool Layer | Orange | #fb923c |
| Local Execution | Green | #4ade80 |
| Persistent State | Rose | #fb7185 |
| MCP/Neutral | Gray | #94a3b8 |
| Host Boundary | Violet | #a78bfa |
| Sandbox Boundary | Orange | #fb923c |
| Background | Slate | #020617 |

## Data Flow (Numbered Steps)

### Local backend (steps 1-6):
1. User input arrives (CLI, gateway, cron tick)
2. Routed to prompt builder — memory, skills, env hints injected
3. Full prompt to agent loop on host process
4. LLM API call to cloud provider — streams response back
5. Tool dispatch (local) — terminal/file/code run directly on host
6. Tool dispatch (cloud) — browser/web/image to cloud services

### Remote backend (steps 1-6):
1. User input arrives (CLI, gateway, cron tick)
2. Routed to prompt builder — memory, skills, env hints injected
3. Full prompt to agent loop on host process
4. LLM API call to cloud provider — streams response back
5. Tool dispatch — browser/web/image run in cloud
6. terminal/file/code sent to backend API, executed in sandbox, stdout returned

## Output Path

Default: `~/hermes-agent-architecture.html`

## Common Pitfalls

1. **Hardcoding user/machine names** — always discover from the environment, never assume specific values
2. **Wrong topology for the backend** — check terminal backend in config FIRST; local = 2 zones, remote = 3 zones
3. **Stale model/provider** — always read from config, do not assume any particular model or provider
4. **Forgetting to update the footer** when any value changes
5. **SVG viewBox too small** — remote-backend diagrams are taller (3 zones); increase height to about 1120
6. **Font not loading** — requires internet for Google Fonts (JetBrains Mono); falls back to monospace
7. **Not updating info cards** — cards at the bottom must match the diagram topology
8. **Assuming macOS tools** — use apt/yum on Linux, choco on Windows, brew on macOS
9. **Skipping the Bar Raiser** — NEVER deliver a diagram without running Step 5. A beautiful diagram with wrong facts is worse than no diagram at all.
10. **Guessing when verification fails** — if you cannot verify a value, flag it as UNVERIFIED. Never fill in plausible-looking guesses.

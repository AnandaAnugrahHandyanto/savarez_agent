---
name: advisor-tool
description: Give your executor model (Sonnet, Haiku) an intelligence boost by pairing it with Opus as a strategic advisor. Uses Anthropic's advisor tool beta to let a cheaper model consult a smarter one mid-conversation — better results at lower cost. Anthropic provider only.
version: 1.0.0
author: Hermes Agent (Nous Research)
license: MIT
metadata:
  hermes:
    tags: [Anthropic, Advisor, Opus, Sonnet, Strategy, Cost-Optimization]
    related_skills: [hermes-agent]
---

# Advisor Tool — Sonnet + Opus Pairing

The advisor tool lets a faster, cheaper executor model (like Claude Sonnet) consult a more capable advisor model (like Claude Opus) for strategic guidance during complex tasks. The executor handles all tool calls and generates output at its normal rate, but can "phone a friend" when it needs help with planning, architecture decisions, or tricky reasoning.

This is Anthropic's [advisor tool beta](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) — a server-side tool where the advisor inference happens on Anthropic's side. Hermes passes the tool definition through and handles the response blocks transparently. You don't need to change how you use Hermes — the executor decides when to consult the advisor on its own.

**Result:** Sonnet-speed execution with Opus-quality strategic thinking, at a fraction of the cost of running Opus for everything.

## When to Use

**Good fit:**
- Complex software development (multi-file changes, architecture decisions)
- Research and analysis tasks requiring careful reasoning
- Any workflow where you'd normally use Opus but want faster iteration
- Long sessions where cost adds up

**Skip it:**
- Simple queries (one-shot questions, quick lookups)
- Non-Anthropic providers (it silently does nothing)
- When you're already running Opus as your main model (advisor would be redundant)

## Prerequisites

- **Anthropic provider** — the advisor tool is Anthropic-only. It will not activate on OpenRouter, OpenAI, or any other provider, including third-party Anthropic proxies.
- **Anthropic API key** with access to both the executor and advisor models.

## Quick Reference

| Config key | Default | Description |
|------------|---------|-------------|
| `advisor.enabled` | `true` | Master toggle for the advisor tool |
| `advisor.model` | `claude-opus-4-6` | Advisor model ID — should be more capable than executor |
| `advisor.max_uses` | `0` | Max advisor calls per API request (0 = no limit) |
| `advisor.caching` | `false` | Cache advisor context across calls within a turn |
| `advisor.auto_effort` | `true` | Reduce executor's thinking budget when advisor handles strategic thinking |

| Slash command | Effect |
|---------------|--------|
| `/advisor` | Toggle on/off |
| `/advisor on` | Enable |
| `/advisor off` | Disable |
| `/advisor status` | Show current settings |

## Procedure

1. **Add the `advisor` section** to `~/.hermes/config.yaml`:

```yaml
advisor:
  enabled: true
  model: claude-opus-4-6
  max_uses: 0
  caching: false
  auto_effort: true
```

2. **Set your main model to a cheaper executor:**

```yaml
model:
  default: anthropic/claude-sonnet-4-6
  provider: anthropic
```

3. **Start a new session** — restart Hermes or use `/reset`.

4. **Work normally.** The executor calls the advisor autonomously. You'll see a brief "advisor" spinner when it consults Opus. No other workflow changes needed.

5. **Toggle mid-session** with `/advisor on` or `/advisor off`. Changes take effect on the next LLM call (no `/reset` needed).

## What You'll See

When the advisor is active, Hermes works exactly like normal — you won't see the advisor's raw output. What changes:

1. **During generation**, a brief "advisor" spinner appears when the executor consults Opus. This typically happens at the start of complex tasks (planning) and before final answers (verification).
2. **Better first attempts** — the executor makes fewer mistakes on architecture, edge cases, and multi-step reasoning because it got strategic guidance.
3. **Lower cost** — Sonnet + occasional Opus calls costs significantly less than running Opus for every turn.

The executor decides autonomously when to call the advisor. You can influence this through your system prompt or personality file — tell the agent to "consult the advisor before making architectural decisions" or "always check with the advisor before finalizing."

## Cost Model

Each advisor call is a separate inference billed at the advisor model's rates:

- **Executor tokens** — billed at Sonnet rates (your main model)
- **Advisor tokens** — billed at Opus rates, but only when consulted
- **Caching** — set `caching: true` if the executor makes 3+ advisor calls per turn to reduce repeated context costs

Typical usage: 1-3 advisor calls per complex task. The cost premium over pure Sonnet is modest compared to running pure Opus.

## Pitfalls

1. **Anthropic-only.** The advisor tool is completely ignored on non-Anthropic providers. If you switch providers mid-session (`/model`), the advisor silently deactivates. Switch back to Anthropic and `/reset` to re-enable.

2. **Third-party Anthropic endpoints don't work.** Proxies and gateways that forward to Anthropic (e.g., some OpenRouter Anthropic routes) do NOT support server-side tools. The advisor only activates on direct Anthropic API connections (`api.anthropic.com`).

3. **Model hierarchy matters.** The advisor model should be at least as capable as the executor. Pairing Opus executor with Sonnet advisor is backwards and wastes money. The typical pairing is Sonnet executor + Opus advisor.

4. **Not a replacement for good prompting.** The advisor improves strategic thinking, not tool use or domain knowledge. If the executor doesn't have the right tools or context, the advisor can't fix that.

5. **Beta feature.** The advisor tool uses Anthropic's `advisor-tool-2026-03-01` beta. The API may change. Hermes will track updates, but check [Anthropic's docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) for the latest.

## Verification

Confirm the advisor is working:

1. **Check status:** Run `/advisor status` in a session. You should see:
   ```
   Advisor: enabled | Model: claude-opus-4-6
   ```

2. **Watch for the spinner:** Send a complex task (e.g., "Design a concurrent worker pool with graceful shutdown in Go"). During generation, look for the "advisor" progress indicator — this confirms the executor is consulting Opus.

3. **Check token usage:** Run `/usage` after a turn. When the advisor was called, you'll see higher input token counts than a pure Sonnet turn — the advisor sub-inference consumes additional tokens at Opus rates.

4. **Multi-turn test:** Send a follow-up message in the same conversation. If it works without errors, the advisor blocks are round-tripping correctly through message history.

## How It Works (Technical)

For contributors and the curious:

1. Hermes injects an `advisor_20260301` tool definition into the Anthropic tools array alongside your regular tools.
2. The executor model sees the advisor as just another tool it can call. When it does, Anthropic runs a server-side inference with the advisor model.
3. The advisor's response comes back as `server_tool_use` + `advisor_tool_result` blocks in the stream. Hermes preserves these blocks in message history for conversation continuity.
4. The entire advisor exchange is transparent — Hermes doesn't dispatch it locally, just passes it through.

Implementation details and contributor pitfalls are documented in `AGENTS.md` under "Anthropic Advisor Tool." Key files: `agent/anthropic_adapter.py` (tool injection, response handling, message round-tripping), `run_agent.py` (config threading, streaming support), `hermes_cli/config.py` (defaults).

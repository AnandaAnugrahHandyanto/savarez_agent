# Hermes Agent - Claude Code Guide

This file is the Claude Code entry point for this repository. The canonical,
more complete agent/developer guide is `AGENTS.md`; use it as the source of
truth when details differ.

## Start Here

- Work from the current git branch unless the user asks you to switch.
- Prefer the repo's existing patterns and helper APIs over new abstractions.
- Do not revert unrelated user changes in the working tree.
- Keep edits scoped to the request and the affected subsystem.

## Environment

```bash
source .venv/bin/activate  # or: source venv/bin/activate
```

`scripts/run_tests.sh` is the required test wrapper. It probes `.venv`, `venv`,
and the shared Hermes checkout venv, then runs pytest with CI-like environment
settings.

## Test Commands

```bash
scripts/run_tests.sh
scripts/run_tests.sh tests/gateway/
scripts/run_tests.sh tests/tools/test_delegate.py::TestBlockedTools
.venv/bin/ruff check .
```

Do not call `pytest` directly unless there is no alternative; the wrapper
normalizes credentials, HOME, timezone, locale, and worker count.

## Important Project Invariants

- Profile-aware state paths must use `get_hermes_home()` from
  `hermes_constants`; user-facing path text should use `display_hermes_home()`.
- Tests must not write to a real `~/.hermes/`; use the existing fixtures and set
  `HERMES_HOME` when mocking home directories.
- Prompt caching must not be broken mid-conversation. Slash commands that alter
  tools, skills, memory, or system prompt state should defer invalidation unless
  an explicit `--now` flow exists.
- Built-in tools require both registration in `tools/*.py` and exposure through
  `toolsets.py`.
- Plugin capabilities should use generic plugin hooks/surfaces; do not hardcode
  plugin-specific logic into core files.

## High-Value Files

- `run_agent.py` - `AIAgent`, conversation loop, interrupts, compression.
- `model_tools.py` - tool discovery, schema filtering, function dispatch.
- `toolsets.py` - toolset definitions and platform bundles.
- `cli.py` - classic CLI and slash-command dispatch.
- `gateway/run.py` - messaging gateway runner.
- `hermes_cli/config.py` - default config and config migration.
- `tools/` - built-in tool implementations.
- `plugins/` - plugin systems and bundled plugins.
- `tests/` - pytest suite.

## MCP Server & Skills Integration

The Hermes MCP server (`mcp_serve.py`) runs as a stdio MCP server that Cursor
and Claude Code connect to automatically via `.cursor/mcp.json`. It provides
two tool surfaces:

### Messaging Tools (original, 10 tools)

Conversations, messages, events, approvals across connected platforms:
`conversations_list`, `conversation_get`, `messages_read`,
`attachments_fetch`, `events_poll`, `events_wait`, `messages_send`,
`channels_list`, `permissions_list_open`, `permissions_respond`

### Skills & Knowledge Tools (hermes_skills_mcp.py, 7 tools)

Read-only access to the custom Hermes agent fleet, skills, knowledge layer,
and persistent memory. **Use these tools to pull context before modifying
agent code, SOUL.md files, or pipeline logic.**

| Tool | Purpose | When to use |
|------|---------|-------------|
| `skills_list` | List all agent SOUL.md files and repo skills | Discovering what agents/skills exist |
| `skills_read` | Read a specific SOUL.md or skill document | Before modifying agent behavior or prompts |
| `agents_list` | List agents with registry data and optional heartbeat | Fleet health check, understanding agent roles |
| `agents_get` | Full agent detail: registry, SOUL.md, heartbeat, files | Deep-diving into a specific agent |
| `knowledge_read` | Read knowledge layer artifacts (latest_state, ledgers) | Understanding current production state |
| `learnings_read` | Read .learnings/ memory files (HOT/WARM/COLD tiers) | Checking what the fleet has learned |
| `artifacts_list` | Browse the artifacts/ directory tree | Discovering operational outputs |

**Key paths** (resolved via HERMES_HOME and HERMES_REPO):
- `agents/` - Custom agent directories, each with SOUL.md, HEARTBEAT.md
- `agents/AGENT_REGISTRY.json` - Authoritative agent fleet manifest
- `artifacts/ops/knowledge_layer/` - Knowledge layer state files
- `artifacts/ops/held_spec_ledger/` - Held specification tracking
- `.learnings/memory.md` - HOT-tier persistent memory (100-line cap)
- `skills/` - Upstream OpenClaw skill categories

**Example workflow** - before modifying the herald agent:
1. `skills_read(name="herald")` - read the SOUL.md
2. `agents_get(name="herald")` - check registry entry, heartbeat, files
3. `knowledge_read(artifact="latest_state")` - understand current state
4. Make your changes
5. Run focused tests

### Architecture Notes

- `hermes_skills_mcp.py` is a standalone module imported by `mcp_serve.py`
- All tools are read-only; no mutation of skills, registry, or artifacts
- Gracefully degrades: if `hermes_skills_mcp` import fails, the messaging
  tools still work (logged at DEBUG level)
- Path resolution uses HERMES_HOME/HERMES_REPO env vars, same as the rest
  of the codebase

## Recent CI/PR Notes

This branch contains audit fixes around:

- subagent blocked-tool enforcement,
- `AIAgent.close()` cleanup of shared terminal/background resources,
- Google Chat plugin platform registration and Pub/Sub handoff,
- setup-provider config resync,
- gateway runtime env reload authority,
- concurrent interrupt test scaffolding.

When touching these areas, rerun the focused tests listed in the PR body before
committing.

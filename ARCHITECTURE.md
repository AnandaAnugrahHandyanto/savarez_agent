# ARCHITECTURE.md

This document is the Rosetta AS-IS architecture summary for Hermes Agent. It captures the existing system; BMad TO-BE architecture for future work belongs in BMad planning artifacts.

## System overview

Hermes Agent is a multi-surface personal AI agent. The same agent core can run from the CLI, messaging gateway, TUI, desktop app, dashboard/API, scheduled cron jobs, and delegated subagents. Capabilities are extended primarily through tools, skills, plugins, MCP servers, and platform adapters rather than growing the core agent surface.

## Core runtime architecture

- `run_agent.py` owns the high-level conversation loop and model/tool execution orchestration.
- Provider adapters and chat completion helpers under `agent/` normalize model-provider differences.
- `model_tools.py`, `toolsets.py`, and `tools/registry.py` define available tool schemas and dispatch paths.
- Conversation/session state is persisted through `hermes_state.py` and profile-aware home-directory helpers in `hermes_constants.py`.
- Runtime logging is profile-aware through `hermes_logging.py`.

## Tool architecture

- Tool implementations live under `tools/`.
- Toolsets group tools so surfaces can enable a bounded capability set.
- New capabilities should prefer existing tools, CLI+skill flows, service-gated tools, plugins, or MCP servers before adding a core tool schema.
- Terminal/file/browser/web/memory/session/delegation/cron/messaging tool families are intentionally separate to keep dispatch and dependency boundaries clear.

## Gateway architecture

- `gateway/` runs the messaging gateway, session mapping, platform adapters, runtime footer, slash commands, and delivery helpers.
- `gateway/platforms/` contains platform-specific adapters. Each adapter handles platform events and maps them into the shared agent/session runtime.
- Gateway session identity includes platform/chat/thread context where supported, so threads/topics/channels can isolate conversations.

## CLI, TUI, desktop, and web surfaces

- `cli.py` and `hermes_cli/` implement interactive and command-based terminal UX.
- `tui_gateway/` exposes websocket/event transport for TUI clients.
- `apps/desktop/` is the Electron desktop client.
- `web/` and `website/` hold the dashboard and documentation/frontend workspaces.

## Scheduling and background work

- `cron/` implements scheduled jobs with persisted job definitions, agent-driven or script-only execution, and delivery to configured targets.
- Background processes are tracked by the terminal/process tools rather than being hidden shell jobs.
- Scheduled jobs should keep prompts self-contained because they run in fresh sessions.

## Skills, memory, and self-improvement

- In-repository skills live under `skills/`; optional skills under `optional-skills/`.
- User-local skills and persistent memories live under the profile-specific Hermes home, not the source repo.
- Skills are procedural memory; user facts/preferences belong in memory/fact stores.
- Session search uses persisted sessions to recover prior conversation context.

## Extension architecture

- Plugins live under `plugins/` or user plugin directories and should integrate through plugin surfaces instead of special-casing core code.
- MCP servers are preferred for structured niche capabilities that do not need to be core tools.
- Optional MCP catalog entries live under `optional-mcps/`.

## Architectural invariants

- Per-conversation prompt caching is sacred; avoid mid-conversation system/tool schema churn.
- Preserve strict user/assistant/tool message-role alternation.
- Keep the core model tool schema narrow.
- Preserve profile isolation; use profile-aware helpers instead of hardcoded paths.
- Tests must be hermetic and avoid mutating a real user Hermes home.
- Public Hermes Agent source should not embed private Artem/Enkidu policy unless the explicit goal is a general feature.

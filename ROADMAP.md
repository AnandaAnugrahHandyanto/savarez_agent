# Hermes Agent Roadmap

Hermes Agent is the self-improving AI agent built by Nous Research: a terminal-native, gateway-ready agent that learns reusable skills, remembers across sessions, and runs wherever the user wants to reach it.

This roadmap is a living planning document. It is intentionally directional rather than a release contract: priorities may shift based on user feedback, security requirements, model/provider changes, and contributor availability.

## Guiding Principles

- **Self-improvement first:** make memory, skills, session recall, and agent-authored procedures reliable enough to compound over time.
- **Runs anywhere:** keep Hermes useful on laptops, VPSes, containers, WSL, Termux, serverless sandboxes, and remote machines.
- **User-controlled autonomy:** powerful tools should be paired with transparent approval, auditability, recovery, and scoped permissions.
- **Provider-agnostic by default:** support many models and auth modes without locking users into one vendor.
- **Composable integrations:** platforms, tools, skills, MCP servers, profiles, plugins, and cron jobs should compose cleanly instead of becoming separate product silos.
- **Small core, lazy edges:** keep the default install lean; install optional dependencies only when a user enables that capability.

## Current Focus

These areas are active priorities for the near term.

### 1. Reliability and Quality Gates

- Keep the core test suite fast, deterministic, and representative of real gateway/CLI usage.
- Strengthen CI around dependency locking, Nix builds, Docker images, website deploys, and supply-chain checks.
- Continue exact-pinning and lazy-install policies to reduce the blast radius of compromised or broken packages.
- Improve typed error surfaces for provider auth, tool failures, cancelled MCP calls, and gateway delivery issues.
- Expand smoke tests for common install/update paths: curl installer, PowerShell installer, `hermes update`, Docker, Nix, and editable installs.

### 2. Gateway and Multi-Platform UX

- Make Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, Teams, Google Chat, Home Assistant, and other adapters feel consistent without hiding platform-specific capabilities.
- Improve gateway status, restart, pairing, `/sethome`, delivery targeting, and troubleshooting messages.
- Tighten group-chat behavior: interruptions, queued messages, per-user sessions, thread/topic routing, and consent-aware context handling.
- Add better observability for platform delivery failures, rate limits, missing permissions, and stale credentials.
- Document practical deployment recipes for always-on agents on low-cost VPSes and home servers.

### 3. Memory, Skills, and Session Recall

- Make skill creation and skill patching safer, more discoverable, and easier to review.
- Improve skill hub browsing, optional skill documentation, install/update flows, and platform-specific skill enablement.
- Continue refining memory guidance so durable preferences and environment facts are saved without polluting future sessions with stale task logs.
- Improve session search relevance, summarization quality, and scroll/browse workflows for long-running projects.
- Support stronger provenance for learned knowledge: where a memory/skill came from, when it was last validated, and how to remove or revise it.

### 4. Tools, MCP, and Plugin Ecosystem

- Keep built-in toolsets modular, checkable, and easy to enable/disable per platform.
- Expand native MCP ergonomics: server setup, auth, tool filtering, cancellation behavior, and diagnostics.
- Improve plugin authoring docs and examples for model providers, memory providers, context engines, platforms, and custom tools.
- Maintain clear boundaries between core dependencies, optional extras, lazy deps, skills, and plugins.
- Add more real-world examples for webhook subscriptions, GitHub automation, Google Workspace, Linear, Notion, Spotify, browser automation, and smart-home workflows.

### 5. Developer Experience

- Keep the CLI and TUI fast, predictable, and friendly for long agent sessions.
- Improve slash command discoverability, autocomplete, command aliases, and gateway/CLI parity.
- Make worktree mode, spawned agents, subagents, profiles, and Kanban-style orchestration easier to understand and debug.
- Strengthen contributor docs around architecture, testing, tools, gateway adapters, slash commands, and release workflows.
- Reduce footguns in local development: environment detection, venv selection, config isolation, prompt caching, and profile-aware paths.

## Roadmap by Horizon

### Near Term

- Harden install/update flows across Linux, macOS, WSL2, Termux, and native Windows beta.
- Improve gateway health checks and user-facing diagnostics for common Discord/Telegram/Slack failures.
- Polish `/tools`, `/skills`, `/model`, `/provider`, `/status`, `/platforms`, `/cron`, and `/profile` flows across CLI and gateway.
- Expand docs for MCP setup, voice mode, cron troubleshooting, profile distributions, and team assistants.
- Strengthen supply-chain CI and dependency review automation.
- Improve cancellation and timeout behavior for tools, MCP calls, subagents, and background processes.
- Add more targeted tests for gateway session concurrency, per-user group sessions, and interrupt handling.

### Medium Term

- Build a more coherent dashboard/TUI experience for monitoring sessions, tools, cron jobs, gateway state, logs, and profiles.
- Make profile distribution and team setup flows more robust, including version pinning and safer sharing of reusable agent configurations.
- Improve memory and skill review UX so users can approve, edit, merge, or reject learned knowledge.
- Add richer audit trails for autonomous actions: commands run, files edited, external APIs called, approvals granted, and deliveries sent.
- Improve multi-agent orchestration patterns: spawned Hermes processes, subagents, Kanban workers, worktrees, and long-running background missions.
- Deepen browser automation and computer-use workflows with better snapshots, screenshots, auth/session persistence, and failure recovery.
- Expand provider support while keeping auth errors, token refresh, credential pools, and fallback behavior understandable.

### Longer Term

- Make Hermes a durable personal/team agent runtime: portable profiles, reproducible environments, observable background jobs, and secure shared deployments.
- Provide first-class workflows for agent evaluation, trajectory export, batch runs, and training-data generation.
- Support richer policy controls for organizations: tool allowlists, approval rules, workspace boundaries, retention, and audit exports.
- Mature the plugin ecosystem so third-party integrations can be discovered, installed, configured, tested, and updated safely.
- Improve cross-device continuity: start in CLI, continue from Discord, receive cron results on mobile, and inspect state from a dashboard.
- Continue reducing the gap between “agent can do this once” and “agent can operate this reliably every day.”

## Feature Area Backlog

### Core Agent Runtime

- More resilient context compression and long-session recovery.
- Better model fallback and retry policies across providers.
- Clearer budget, token, cost, and iteration reporting.
- Safer parallel tool execution with predictable ordering and cancellation.
- Improved checkpointing, rollback, and filesystem recovery UX.

### CLI and TUI

- Faster startup and clearer health/status banners.
- Better multiline editing, history search, and slash-command help.
- More useful `/usage`, `/insights`, `/history`, `/sessions`, and `/logs` flows.
- TUI panels for tools, skills, MCP servers, cron jobs, and gateway status.

### Messaging Gateway

- More platform adapters and deeper platform-native affordances.
- Better support for threads, topics, mentions, attachments, voice notes, and media delivery.
- Clear operator guidance for bot permissions, intents, webhooks, and service restarts.
- Safer defaults for group chats, DMs, pairing, and command authorization.

### Skills and Memory

- Skill linting, validation, and compatibility checks.
- Better deduplication and consolidation of overlapping skills.
- Memory review queues and confidence/provenance metadata.
- Export/import workflows for user-created skills and selected memories.

### MCP and Tools

- Better MCP server lifecycle management and diagnostics.
- Tool permission scopes by platform, profile, and conversation.
- More examples for custom tool authoring and JSON schema design.
- Stronger handling of long-running tools, streaming output, and partial failures.

### Automation and Cron

- Cron templates for common workflows: briefings, backups, audits, reminders, inbox triage, and repository maintenance.
- More predictable delivery targeting and retry behavior.
- Better run history, logs, manual re-run, and failure inspection.
- Safer unattended maintenance patterns with non-interactive commands and scoped approvals.

### Packaging and Deployment

- Keep Docker, Nix, Python package, installer, and source checkout paths aligned.
- Continue native Windows hardening while keeping WSL2 the battle-tested path.
- Improve server deployment guides for systemd, reverse proxies, webhooks, and gateway services.
- Reduce dependency footprint and isolate optional integrations.

### Documentation and Examples

- Keep `llms.txt` and `llms-full.txt` accurate as machine-readable entry points.
- Add practical end-to-end guides for team bots, project automation, MCP integration, voice workflows, and plugin development.
- Add more troubleshooting pages for provider auth, platform permissions, dependency installation, and gateway delivery.
- Keep bundled and optional skill docs in sync with actual installed skills.

## Non-Goals

- Hermes should not become tied to a single model provider, IDE, messaging platform, or hosting environment.
- The core install should not eagerly include every optional dependency.
- Memory should not become a dumping ground for stale task history or one-off artifacts.
- Autonomy should not bypass user intent, workspace boundaries, or approval policy.
- Platform integrations should not require every user to run every platform dependency.

## How to Contribute

- Pick an issue or roadmap item with a clear user-facing outcome.
- Keep changes small, tested, and documented.
- Prefer exact dependency pins and update `uv.lock` when changing Python dependencies.
- Add or update docs when behavior changes.
- Run targeted tests for the area you changed, then the broader test suite before opening a PR.
- For new tools, plugins, commands, and gateway adapters, include diagnostics and failure messages — not just the happy path.

## Feedback

The roadmap should track what real users need from an always-on, self-improving agent. Please open issues, discussions, or pull requests with:

- Pain points from real Hermes usage.
- Missing integrations or platforms.
- Reliability failures and reproduction steps.
- Confusing docs or setup flows.
- Ideas that make Hermes safer, more autonomous, or easier to operate long-term.

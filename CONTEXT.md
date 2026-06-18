# CONTEXT.md

This document is the Rosetta AS-IS domain/context summary for Hermes Agent.

## Product purpose

Hermes Agent is an open-source, provider-agnostic AI agent framework by Nous Research. It gives users a persistent agent that can run from the terminal, messaging platforms, desktop, web surfaces, and scheduled automations while using real tools, memory, skills, and delegated subagents.

## User-facing capabilities

- Interactive CLI and TUI conversations.
- Messaging gateway for platforms such as Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, and Home Assistant.
- Desktop and web/dashboard surfaces.
- Tool use: terminal, files, web/search/browser, vision/media, memory, session search, cron, messaging, MCP, delegation, and more.
- Skills system for reusable procedures and self-improving workflows.
- Persistent memory and session search across conversations.
- Cron jobs for scheduled automations and reports.
- Multiple terminal/environment backends for local and remote execution.

## Primary stakeholders

- End users running Hermes as a personal assistant.
- Developers extending Hermes Agent source, plugins, skills, gateway adapters, or tooling.
- Maintainers reviewing contributions against the narrow-core / expansive-edge architecture.
- Agentic coding assistants operating inside the repository through AGENTS.md and skills.

## Contribution expectations

- Fix real bugs with evidence and tests.
- Expand product reach at the edges through adapters, providers, desktop/TUI/dashboard features, plugins, MCP servers, and skills.
- Avoid speculative infrastructure and new core model tools when existing tools, skills, plugins, or MCP can solve the problem.
- Preserve prompt caching, role alternation, profile isolation, and security boundaries.
- Avoid change-detector tests that merely freeze volatile data.
- Use E2E or integration validation where resolution chains, config propagation, security boundaries, remote backends, or file/network I/O are involved.

## Operational context

- Hermes is frequently installed under `$HERMES_HOME/hermes-agent`, commonly `~/.hermes/hermes-agent`, but source code must stay profile-safe and portable.
- Runtime configuration and secrets live in user profile homes, not in this public source tree.
- Development uses git worktrees for isolated source changes.
- Public upstream source changes should remain general-purpose; private deployment or automation policy belongs outside upstream Hermes Agent source.

## BMad/Rosetta boundary for this repo

- These root Rosetta docs describe current Hermes Agent AS-IS behavior.
- `_bmad-output/project-context.md` points BMad agents to these AS-IS docs and adds implementation rules.
- Future BMad PRDs, architectures, stories, and sprint artifacts should describe TO-BE work and must not overwrite these AS-IS docs.
- Hermes Agent framework/source changes require explicit source-route approval, worktree isolation, tests, and PR review in automated workflows.

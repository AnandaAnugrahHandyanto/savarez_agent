# CODEMAP.md

This document is the Rosetta AS-IS file and module map for Hermes Agent.

## Root entry points

- `run_agent.py` — core `AIAgent` conversation loop and high-level agent runtime.
- `model_tools.py` — tool orchestration, built-in discovery, and function-call dispatch.
- `toolsets.py` — toolset definitions and core tool registry boundaries.
- `cli.py` — interactive CLI orchestrator.
- `batch_runner.py` — parallel batch processing.
- `trajectory_compressor.py` — trajectory compression support.
- `hermes_constants.py` — profile-aware Hermes home path helpers.
- `hermes_state.py` — SQLite session store and session search persistence.
- `hermes_logging.py` — profile-aware logging setup.
- `hermes_time.py` — time utilities.
- `mcp_serve.py` — Hermes MCP server entry point.

## Python package directories

- `agent/` — provider adapters, chat completion helpers, memory/caching/compression internals, prompt/model plumbing, and agent runtime support.
- `tools/` — model tool implementations and support helpers: terminal, file, patch, web, browser, skills, memory, messaging, MCP, todo, vision, TTS, image/video generation, Home Assistant, and tool registry code.
- `tools/environments/` — terminal backend implementations for local, Docker, SSH, Modal, Daytona, Singularity, and related process management.
- `hermes_cli/` — CLI command surface, setup wizard, model/provider pickers, config commands, plugins, web/dashboard helpers, skins, and update flows.
- `gateway/` — messaging gateway runtime, sessions, adapters, formatting, delivery, slash commands, and platform integrations.
- `gateway/platforms/` — platform adapters for Discord, Telegram, Slack, WhatsApp, Signal, Matrix, Mattermost, Email, SMS, Home Assistant, DingTalk, Feishu, WeCom, API server, webhooks, and related services.
- `cron/` — scheduler models, execution engine, persistence, and cron CLI/runtime helpers.
- `plugins/` — bundled plugin infrastructure and plugin-provided capabilities.
- `providers/` — provider package surfaces and provider-specific helpers.
- `tui_gateway/` — websocket/event bridge for TUI frontends.
- `acp_adapter/` — Agent Client Protocol server/adapter entry points.

## Frontend, desktop, and docs directories

- `apps/desktop/` — Electron desktop application.
- `web/` — web UI/dashboard workspace.
- `ui-tui/` — OpenTUI/TUI frontend workspace and packages.
- `website/` — documentation website and skill/docs generation scripts.
- `docs/` — repository developer/user documentation that is not part of the website workspace.
- `assets/` — shared static assets.

## Extension and knowledge directories

- `skills/` — in-repository skills shipped with Hermes Agent.
- `optional-skills/` — optional skill bundles not always installed by default.
- `optional-mcps/` — catalog manifests for optional MCP servers.
- `plugins/` — plugin code and manifests; plugin capabilities should stay at the edge rather than expanding the core tool schema.

## Tests and CI support

- `tests/` — Python test suite, including agent, CLI, gateway, tools, cron, packaging, and platform tests.
- `scripts/` — maintenance, test, setup, install, and analysis scripts.
- `.github/` — GitHub Actions workflows and automation.
- `docker/`, `Dockerfile`, `compose*.yml` — container/runtime packaging.
- `nix/`, `flake.nix` — Nix packaging/devshell support.

## Generated or local-only paths

- `.worktrees/`, `.hermes/`, `.venv/`, `venv/`, `node_modules/`, test caches, build outputs, and runtime logs are ignored local state.
- BMad/Rosetta setup adds `_bmad/`, `_bmad-output/`, `.claude/skills/`, and root AS-IS docs. BMad TO-BE artifacts should remain distinct from this AS-IS map.

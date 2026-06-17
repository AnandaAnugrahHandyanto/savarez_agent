# TECHSTACK.md

This document is the Rosetta AS-IS technology inventory for Hermes Agent. It describes the current implementation so BMad planning artifacts can reason about future work without rewriting existing architecture.

## Runtime languages and package managers

- Python package: `hermes-agent`, version declared in `pyproject.toml`.
- Supported Python: `>=3.11,<3.14`.
- Python packaging/build: setuptools build backend, `uv`-based development workflow, `uv.lock` for deterministic dependency resolution.
- JavaScript/TypeScript package: root `package.json` with npm workspaces.
- Required Node: `>=20.0.0`.
- npm workspaces: `apps/*`, `ui-tui`, `ui-tui/packages/*`, `web`.
- Desktop app: Electron/TypeScript under `apps/desktop`.
- Web UI/docs frontends: Vite/React-style workspace code under `web`, `website`, and `ui-tui`.

## Python core dependencies

Core Python dependencies are exact-pinned in `pyproject.toml` where practical. Important runtime packages include:

- `openai` for OpenAI-compatible provider surfaces.
- `httpx`, `requests`, `tenacity` for HTTP and retry flows.
- `pydantic` for structured data models.
- `prompt_toolkit`, `rich`, `fire` for CLI/TUI presentation and commands.
- `pyyaml`, `ruamel.yaml` for config and YAML-preserving workflows.
- `croniter` for scheduled jobs.
- `fastapi`, `uvicorn`, `starlette` for API/dashboard surfaces.
- `psutil`, `ptyprocess`, `pywinpty`, `websockets`, `pathspec`, `Pillow` for runtime support features.

Optional extras in `pyproject.toml` gate provider, messaging, voice, MCP, dashboard, and platform-specific integrations.

## JavaScript dependencies

The root package is private and primarily coordinates workspaces. Root dependencies include `@streamdown/math` and `agent-browser`; workspace-level dependencies live in each workspace package.

## Test and quality tools

- Primary test wrapper: `scripts/run_tests.sh`.
- Pytest config: `pyproject.toml` `[tool.pytest.ini_options]`.
- Default pytest behavior excludes integration tests and applies timeout isolation.
- Type/lint tools in dev extra include `ty` and `ruff`.
- Node workspaces use npm scripts for install and audit paths.

## Runtime surfaces

- CLI and interactive TUI.
- Messaging gateway for Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, and other adapters.
- Desktop Electron app.
- Browser/web dashboard/API surfaces.
- Cron scheduler.
- Tool execution backends: local, Docker, SSH, Modal, Daytona, Singularity, and platform-specific PTY bridges.
- MCP client/server integration.
- Skills and memory systems.

## Development constraints

- Preserve prompt caching and stable system prompt prefixes across conversation lifetime.
- Preserve strict message role alternation in the agent loop.
- Keep core tool schemas narrow; prefer skills, plugins, MCP servers, or service-gated tools before adding core model tools.
- Use profile-safe Hermes paths such as `get_hermes_home()` instead of hardcoded `~/.hermes` in framework code.
- Tests must not touch a real user Hermes home; use temp `HERMES_HOME`/test isolation.

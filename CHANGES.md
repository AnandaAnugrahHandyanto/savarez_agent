# Thaumium — delta from upstream Hermes Agent

This is a private fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), MIT-licensed. This file tracks every intentional deviation from upstream so merges stay conflict-free and the fork's extent stays obvious to future maintainers.

## Code changes

### ✦ `tools/agent_context.py` (new, 80 lines)

Provides a `ContextVar`-based way for plugin-registered tool handlers to access the calling `AIAgent`. Built-in `delegate_task` has access to the caller via a hardcoded dispatch path; every other tool (including plugin tools) does not. This module fills that gap.

Exports:
- `get_current_agent() → AIAgent | None`
- `current_agent(agent)` — context manager that binds/unbinds the current agent

### ✦ `run_agent.py` (patched, 3 dispatch sites)

Each `handle_function_call(...)` call in `AIAgent` (one in `_invoke_tool`, two in the main loop's sequential dispatch paths) is wrapped with `with current_agent(self):` so plugin handlers can retrieve the caller.

Added one import at the top: `from tools.agent_context import current_agent`.

Strictly additive — no behavior change for existing tools, `delegate_task`'s hardcoded path is untouched, third-party callers of `handle_function_call` directly still work.

### ✦ `tests/tools/test_agent_context.py` (new, 58 lines)

5 contract tests: default-None, visible-in-context, reset-on-exit, reset-on-exception, nesting. All pass.

## Branding changes (surface-only)

- `README.md` — prepended a Thaumium header with MIT attribution + link to the upstream PR. Rest of the README is unchanged upstream text.
- `hermes_cli/gateway.py` — the startup banner line `⚕ Hermes Gateway Starting...` changed to `✦ Thaumium Starting...`.
- `web/index.html` — dashboard `<title>` changed from `Hermes Agent - Dashboard` to `Thaumium`.

## Upstream PR

The `tools/agent_context.py` + `run_agent.py` patch is proposed upstream as a strictly-additive extension:

**[NousResearch/hermes-agent#14677](https://github.com/NousResearch/hermes-agent/pull/14677)** — `feat(tools): expose current agent to plugin tool handlers via contextvar`

If upstream merges it, this fork can collapse — delete the three Thaumium code changes above, pull upstream main, keep only the branding changes (or drop those too if the fork is no longer useful).

## What is deliberately NOT changed

- Python package names (`hermes_cli`, `hermes_plugins`, etc.) — renaming would break every upstream merge
- Docker internal paths (`/opt/hermes`, `/opt/data`) — no user benefit, high merge-conflict cost
- Test files referencing `"hermes"` string literals — fixtures, leave untouched
- `package.json` name field (`hermes-agent`) — affects npm + Playwright paths, leave untouched
- CLI `argparse` prog name (`hermes`) — users invoke via Docker `gateway run`, prog is internal
- `LICENSE` file — MIT, Nous's copyright notice stays exactly as-is (required by MIT)

## Upstream tracking

```sh
# fetch upstream
git fetch upstream

# see what's new since our fork point
git log HEAD..upstream/main --oneline

# merge upstream (resolve any conflicts in the 3 Thaumium files)
git merge upstream/main
```

A Claude Code Routine (configured separately) watches `NousResearch/hermes-agent` Releases + main-branch commits and pings Discord when upstream ships changes that touch our patched files.

# hermes-pincher-hooks for Goose

Project-scoped Goose Open Plugins hook extension that mirrors the repo's Claude Code hook posture for Pincher-first work.

## What it does

- Registers a Goose `PreToolUse` hook from `.agents/plugins/hermes-pincher-hooks/hooks/hooks.json`.
- Matches Goose's built-in developer tools: `developer__shell|developer__text_editor`.
- Runs `${PLUGIN_ROOT}/scripts/pincher-hook-check.sh`, which forwards Goose's hook payload to `pincher hook-check`.
- Records `last-event.log` beside the plugin for local debugging without making logging a blocker.

## Why this shape

Goose discovers project-scoped Open Plugins under `<project-root>/.agents/plugins/<name>/`. That keeps the extension local to this checkout, similar to how the repo-local `.claude/settings.json` wires Claude Code hooks for this project.

## Init / verification

From the repository root:

```bash
chmod +x .agents/plugins/hermes-pincher-hooks/scripts/pincher-hook-check.sh

goose session
```

On startup Goose should discover the plugin automatically. A developer tool call should trigger the `PreToolUse` hook and append the raw payload to:

```text
.agents/plugins/hermes-pincher-hooks/last-event.log
```

If Goose is installed outside the normal shell `PATH`, make sure the `pincher` binary is reachable from the environment that launches Goose.

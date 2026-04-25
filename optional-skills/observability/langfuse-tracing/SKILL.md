---
name: langfuse-tracing
description: Optional installer for persistent Langfuse tracing in Hermes. It installs and configures the external runtime plugin; traced sessions then auto-load the plugin through Hermes plugin discovery without adding skill text to prompt context.
version: 1.0.0
author: Nous Research
license: MIT
metadata:
  hermes:
    tags: [observability, tracing, langfuse, telemetry, hooks]
    category: observability
---

# Langfuse Tracing for Hermes

This is an optional skill, but it is not a runtime prompt skill.

Its job is to install, configure, verify, and update the persistent Langfuse tracing plugin for the active Hermes profile. Once installed, tracing is handled by Hermes plugin discovery and plugin hooks at session startup. Normal traced sessions should not load this skill into model context.

The intended lifecycle is:
- install this optional skill when you want Langfuse tracing support
- run the setup helper once to install and enable the plugin
- the runtime tracing code stays in the external plugin repo
- the helper installs the plugin into `$HERMES_HOME/plugins/langfuse_tracing/`
- new Hermes sessions auto-load the plugin through Hermes plugin discovery/hooks
- do not use `/skill langfuse-tracing` or `hermes -s langfuse-tracing` for normal traced sessions

This keeps Hermes core clean, keeps observability instructions out of model context, and makes tracing a persistent opt-in plugin capability rather than per-session prompt content.

## What this skill installs

The helper script can:
- install the `langfuse` Python package in the active Hermes environment if it is missing
- fetch the plugin from an external Git repo
- install the plugin into the active Hermes profile under `$HERMES_HOME/plugins/langfuse_tracing/`
- add Langfuse env vars to `$HERMES_HOME/.env` without silently overwriting existing values
- verify `hermes plugins list` discovers `langfuse_tracing`
- optionally check the Langfuse health endpoint

## Default external source

By default the installer pulls from:
- repo: `https://github.com/kshitijk4poor/hermes-langfuse-tracing.git`
- branch: `main`

The plugin repo can expose files in these layouts:
- `__init__.py` + `plugin.yaml` at repo root  (preferred for `hermes plugins install`)
- `langfuse_tracing/__init__.py` + `langfuse_tracing/plugin.yaml`  (older standalone layout)
- `.hermes/plugins/langfuse_tracing/...`  (legacy branch layout)

## Rules

1. Never enable tracing without explicit user consent.
2. Never overwrite existing Langfuse credentials silently.
3. Install into the active Hermes profile via `get_hermes_home()`, not a hardcoded `~/.hermes` path.
4. Keep the runtime tracing code in the external plugin repo, not inside Hermes core.

## One-command setup

```bash
source .venv/bin/activate
python optional-skills/observability/langfuse-tracing/scripts/setup_langfuse_env.py
```

Explicit values can be passed when they are not already present in the shell env or Hermes env file:

```bash
source .venv/bin/activate
python optional-skills/observability/langfuse-tracing/scripts/setup_langfuse_env.py \
  --public-key 'pk-lf-...' \
  --secret-key 'sk-lf-...' \
  --base-url 'http://localhost:3000' \
  --environment 'local' \
  --release 'local-skill'
```

If you want a different repo or branch:

```bash
source .venv/bin/activate
python optional-skills/observability/langfuse-tracing/scripts/setup_langfuse_env.py \
  --feature-repo 'https://github.com/kshitijk4poor/hermes-langfuse-tracing.git' \
  --feature-branch 'main' \
  --plugin-ref 'langfuse-plugin/main'
```

## Required credentials

The plugin needs these values available either in `$HERMES_HOME/.env`, the current shell environment, or explicit script args:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3000
```

Optional:

```bash
HERMES_LANGFUSE_ENV=local
HERMES_LANGFUSE_RELEASE=local-skill
HERMES_LANGFUSE_SAMPLE_RATE=1.0
HERMES_LANGFUSE_MAX_CHARS=12000
HERMES_LANGFUSE_DEBUG=true
```

## Verify

1. Restart Hermes after installation
2. Run `hermes plugins list`
3. Confirm `langfuse_tracing` is listed/enabled
4. Run a simple prompt in any new Hermes session
5. Confirm Langfuse shows a Hermes turn trace with nested LLM/tool spans

Do not load this skill for normal traced sessions. If the plugin is installed under `$HERMES_HOME/plugins/langfuse_tracing/` and `HERMES_LANGFUSE_ENABLED=true`, plugin discovery makes it active automatically on session start.

## Troubleshooting

### Plugin does not load

Check:

```bash
test -f "$HERMES_HOME/plugins/langfuse_tracing/plugin.yaml" && echo plugin-present
hermes plugins list
```

### Langfuse receives nothing

Check the required env vars in `$HERMES_HOME/.env` and verify the server is reachable at `LANGFUSE_BASE_URL`.

### Need to switch plugin source

Re-run the installer with `--feature-repo`, `--feature-branch`, and optionally `--plugin-ref`.

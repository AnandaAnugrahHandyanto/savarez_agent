---
name: langfuse-tracing
description: Enable Langfuse observability in Hermes — traces conversations, LLM calls, and tool usage. Langfuse tracing is bundled as a plugin; use this skill to look up setup steps or troubleshoot.
version: 1.0.0
author: Nous Research
license: MIT
metadata:
  hermes:
    tags: [observability, tracing, langfuse, telemetry]
    category: observability
---

# Langfuse Tracing for Hermes

Langfuse tracing is built into Hermes as a bundled plugin (`plugins/langfuse_tracing/`).
Use `hermes tools` to enable it — no external installer needed.

## Setup

```bash
hermes tools
# Navigate to "Langfuse Observability" → select Cloud or Self-Hosted → enter credentials
```

Or set env vars directly in `~/.hermes/.env`:

```bash
HERMES_LANGFUSE_ENABLED=true
HERMES_LANGFUSE_PUBLIC_KEY=pk-lf-...
HERMES_LANGFUSE_SECRET_KEY=sk-lf-...
HERMES_LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or your self-hosted URL
```

Then restart Hermes. Verify with `hermes plugins list` — `langfuse_tracing` should appear.

## Optional settings

```bash
HERMES_LANGFUSE_ENV=production          # environment tag
HERMES_LANGFUSE_RELEASE=v1.0.0         # release/version tag
HERMES_LANGFUSE_SAMPLE_RATE=0.5        # sample 50% of traces
HERMES_LANGFUSE_MAX_CHARS=12000        # max chars per field (default: 12000)
HERMES_LANGFUSE_DEBUG=true             # verbose plugin logging
```

## Troubleshooting

**Plugin not listed in `hermes plugins list`:**
Check that `plugins.enabled` in `~/.hermes/config.yaml` includes `langfuse_tracing`,
or run `hermes tools` and re-enable it.

**Traces not appearing in Langfuse:**
- Confirm `HERMES_LANGFUSE_ENABLED=true` is in `~/.hermes/.env`
- Confirm `HERMES_LANGFUSE_PUBLIC_KEY` and `HERMES_LANGFUSE_SECRET_KEY` are set
- Verify the server is reachable at `HERMES_LANGFUSE_BASE_URL`

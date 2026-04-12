# GBrain Quickstart for Hermes

## Install

```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc 2>/dev/null || true
bun add -g github:garrytan/gbrain
gbrain --version
```

## Initialize

Local embedded brain:
```bash
gbrain init
gbrain doctor --json
gbrain stats
```

Remote / larger setup:
```bash
gbrain init --supabase
```

## Import

```bash
gbrain import /path/to/markdown-repo --no-embed
gbrain stats
```

## Search and query

```bash
gbrain search "Pedro"
gbrain query "what are the most important themes across these notes?"
```

## Keep retrieval current

After editing brain markdown:
```bash
gbrain sync --no-pull --no-embed
```

When semantic retrieval needs refreshing:
```bash
gbrain embed --stale
```

## Health check

```bash
gbrain doctor --json
```

## X/Twitter capture on this machine

Prefer the local bird-smart flow over the official X API for common capture work:

```bash
python skills/note-taking/gbrain/scripts/capture_x_to_gbrain.py \
  --url "https://x.com/.../status/..." \
  --brain-repo /path/to/brain
```

This writes a markdown source note under `sources/social/x/` and raw JSON under
`.raw/social/x/`, ready for `gbrain sync --no-pull --no-embed`.

## Upstream docs worth reading

- README: https://github.com/garrytan/gbrain
- Skillpack: https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_SKILLPACK.md
- Recommended schema: https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_RECOMMENDED_SCHEMA.md
- Verification runbook: https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_VERIFY.md

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

## Upstream docs worth reading

- README: https://github.com/garrytan/gbrain
- Skillpack: https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_SKILLPACK.md
- Recommended schema: https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_RECOMMENDED_SCHEMA.md
- Verification runbook: https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_VERIFY.md

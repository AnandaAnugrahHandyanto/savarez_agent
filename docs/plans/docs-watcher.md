# Docs and User Stories watcher (M6)

> Script: `scripts/hermes_docs_watcher.py` — **no-agent**, network fetch of public URLs only.

## Sources (verified roadmap)

| Key | URL |
|-----|-----|
| sitemap | `https://hermes-agent.nousresearch.com/docs/sitemap.xml` |
| llms index | `https://hermes-agent.nousresearch.com/docs/llms.txt` |
| llms full | `https://hermes-agent.nousresearch.com/docs/llms-full.txt` |
| user stories | `raw.githubusercontent.com/.../website/src/data/userStories.json` |

User Stories are **not** inferred from `llms-full`.

## Watermark

`~/.hermes/profiles/auto-coder/docs-watcher-watermark.json`

## Usage

```bash
python scripts/hermes_docs_watcher.py              # silent if unchanged
python scripts/hermes_docs_watcher.py --force-report # baseline/debug
python scripts/hermes_docs_watcher.py --receipt-dir /tmp/hermes-workflows/docs-refresh/<run-id>
```

## Gates

- **Cron registration:** approval-gated (not done in M6).
- **On change:** receipt + recommend bounded DWF docs refresh — no auto skill patch.
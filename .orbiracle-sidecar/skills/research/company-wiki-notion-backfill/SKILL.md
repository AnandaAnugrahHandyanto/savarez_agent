---
name: company-wiki-notion-backfill
description: Resumable Notion raw backfill into the canonical company-wiki, with checkpointed batch capture, background execution, and cron-safe refresh wiring.
---

# Company Wiki Notion Backfill

## Use when
- Notion workspace indexing times out with `/search` or long full-capture runs.
- You need to backfill Notion raw data in the background without restarting from zero.
- You want company-wiki refresh/cron to include Notion safely.

## Key idea
Do **not** rely on one giant synchronous Notion snapshot. Use a **checkpointed, batched, resumable** capture flow:
1. capture workspace catalog once
2. process pages in batches
3. process data sources in batches
4. persist progress in `workspace/company-wiki/raw/notion/checkpoint.json`
5. when complete, run canonical `company-wiki/refresh.py` so derived wiki pages include Notion

## Files involved
- `workspace/bin/company-wiki/notion_snapshot.py`
- `workspace/bin/company-wiki/notion_backfill.py`
- `workspace/bin/company-wiki/refresh.py`
- `workspace/bin/run_company_wiki_refresh.sh`
- `workspace/bin/install_company_wiki_refresh_cron.sh`
- checkpoint: `workspace/company-wiki/raw/notion/checkpoint.json`

## Required behavior
- `notion_snapshot.capture()` should support:
  - `force_catalog_refresh`
  - `page_batch_size`
  - `data_source_batch_size`
- Return status `partial` until all pages/data sources are processed.
- Persist `last_run_status`, `last_error`, `next_page_index`, `next_data_source_index`, and progress maps in the checkpoint.
- Keep raw payloads under `workspace/company-wiki/raw/notion/`.
- Keep derived pages summary-first; no raw body dumping into wiki pages.

## Background run pattern
Load env first so `NOTION_API_KEY` exists, then run the backfill wrapper in background:

```bash
set -euo pipefail
set -a
source "$HOME/.hermes/.env"
set +a
python3 workspace/bin/company-wiki/notion_backfill.py \
  --page-batch-size 10 \
  --data-source-batch-size 2 \
  --sleep-seconds 2 \
  --max-passes 500 \
  --stall-passes 8 \
  --slack-team moveis \
  --github-org orbisoptimus \
  --archive-mode incremental
```

Recommended Hermes background launch: redirect to a dated log file and watch for `"ok": true`, `"ok": false`, `stalled`, `incomplete_after_loop`.

## Cron wiring
`workspace/bin/run_company_wiki_refresh.sh` should:
1. source `~/.hermes/.env` if present
2. pass through:
   - `COMPANY_WIKI_NOTION_PAGE_BATCH_SIZE`
   - `COMPANY_WIKI_NOTION_DATA_SOURCE_BATCH_SIZE`
3. call `workspace/bin/company-wiki/refresh.py`

`workspace/bin/install_company_wiki_refresh_cron.sh` should rewrite the existing refresh entry, not merely skip insertion if an old one exists. Otherwise new Notion env vars will never land in crontab.

## Verification
1. Syntax check:
```bash
python3 -m py_compile \
  workspace/bin/company-wiki/notion_snapshot.py \
  workspace/bin/company-wiki/notion_backfill.py \
  workspace/bin/company-wiki/refresh.py
```
2. Confirm env:
```bash
set -a; source "$HOME/.hermes/.env"; set +a
python3 - <<'PY'
import os; print(bool(os.environ.get('NOTION_API_KEY')))
PY
```
3. Inspect checkpoint:
- `catalog_result_count`
- `page_progress_count`
- `data_source_progress_count`
- `next_page_index`
- `next_data_source_index`
- `last_run_status`
- `last_error`
- `complete`
4. Confirm new crontab line contains Notion batch env vars.

## Common pitfalls
- **504 on `/search`**: treat as transient; retry with longer backoff and continue using checkpointed flow.
- **`NOTION_API_KEY is missing` in checkpoint**: the shell that launched the process did not actually export env into Python; verify `source "$HOME/.hermes/.env"` is in the real execution path.
- **Cron entry unchanged after script edit**: installer must remove the old `run_company_wiki_refresh.sh` line before appending the new one.
- **Background process appears idle**: check the checkpoint and actual child python process, not just the wrapper shell.

## Outcome
The reusable target state is:
- raw Notion capture can run for a long time without restarting from zero
- progress is inspectable from checkpoint/manifests
- completion triggers canonical company-wiki rebuild
- hourly/periodic wiki refresh includes Notion safely instead of failing on a giant monolithic snapshot

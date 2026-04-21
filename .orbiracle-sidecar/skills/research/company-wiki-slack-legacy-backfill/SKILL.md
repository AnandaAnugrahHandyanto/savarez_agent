---
name: company-wiki-slack-legacy-backfill
description: Backfill all visible Slack public-channel history into company-wiki raw storage, monitor checkpoint progress, and rebuild history-backed wiki pages for legacy understanding.
triggers:
  - User wants all public Slack channels archived from the past as raw data
  - User wants Slack legacy/company history understood via company-wiki
  - Need backgroundable Slack public-channel backfill with resume support
---

# Company Wiki Slack Legacy Backfill

Use this when the goal is **raw history first, wiki synthesis second** for Slack public channels.

## Why this exists

`refresh.py --archive-mode archive` can capture historical public-channel history, but for full legacy reading you often need a wrapper that:
1. reruns archive passes until every visible public channel is complete
2. tracks progress via channel checkpoints
3. runs safely in the background
4. only after completion, rebuilds the wiki into history-backed summaries

## Canonical script

Primary wrapper:

```bash
python3 workspace/bin/company-wiki/slack_public_history_backfill.py \
  --slack-team moveis \
  --channel-limit 500 \
  --history-limit 200 \
  --history-max-messages 10000 \
  --chunk-size 100 \
  --sleep-seconds 2 \
  --max-passes 500 \
  --stall-passes 8
```

## What the wrapper does

1. Runs `workspace/bin/company-wiki/refresh.py` with:
   - `--archive-mode archive`
   - large public-channel limit
   - `conversations.history` page size 200
   - `--slack-history-max-messages 10000` so each channel paginates deeply instead of stopping after a shallow page
   - raw chunk size 100
2. Uses `workspace/company-wiki/raw/slack/channel-checkpoints/*.json` to track per-channel completion.
3. Repeats archive passes until every visible public channel has `archive_completed_at`.
4. Detects stall conditions and exits instead of looping forever.
5. Aggregates raw `channel_history_chunk` items from `workspace/company-wiki/raw/slack/items/`.
6. Rebuilds `workspace/company-wiki/` with history-backed summaries.

## Progress checks

### Check checkpoint totals

```bash
python3 - <<'PY'
import json
from pathlib import Path
root=Path('workspace/company-wiki/raw/slack/channel-checkpoints')
completed=pending=errors=0
for p in root.glob('*.json'):
    d=json.loads(p.read_text())
    if d.get('archive_completed_at'): completed += 1
    else: pending += 1
    if d.get('last_run_status') == 'error': errors += 1
print({'completed': completed, 'pending': pending, 'errors': errors, 'total': completed + pending})
PY
```

### Check that raw history chunks exist

Search for `payload_kind = channel_history_chunk` under:
- `workspace/company-wiki/raw/slack/items/`

### Check the process

Use the Hermes background-process tool if available, or shell `ps`/`pgrep` to confirm the wrapper and underlying `refresh.py` are still running.

## Expected outputs

### Raw storage
- `workspace/company-wiki/raw/slack/items/`
- `workspace/company-wiki/raw/slack/channel-checkpoints/`
- `workspace/company-wiki/raw/slack/runs/manifest-*.json`
- `workspace/company-wiki/raw/run-manifests/*.json`

### Derived wiki
After completion, expect history-backed pages in `workspace/company-wiki/`, including an overview topic like:
- `slack-public-channel-legacy-archive-overview`

Channel pages should become history-backed summaries instead of metadata-only bootstrap notes.

## Important findings from real use

- Existing archive state may already be partially complete. Inspect checkpoint counts before assuming a clean start.
- In this workspace, visible non-archived public-channel coverage was 100 channels at run time.
- `recent_public_channels.py` is only a **channel.updated heuristic**. It can return far fewer channels than the true visible public inventory and must not be mistaken for total accessible public-channel count.
- Before a serious legacy backfill, it is worth mass-joining all visible public channels once:

```bash
python3 workspace/bin/slack-org-wiki/join_public_channels.py --all-public --limit 1000
```

- Early progress may show up in checkpoint/manifests before log files visibly fill.
- `join_public_channels.py` may be invoked with a very large channel list; that is expected during archive passes.
- The right success criterion is **checkpoint completion (`pending=0`)**, not merely one successful refresh run.
- If a small number of channels stay pending for many passes while `history_ok_count` remains nonzero, the usual cause is shallow per-pass paging rather than auth failure; increase deep pagination per channel (`--slack-history-max-messages 10000`) instead of just rerunning the same shallow archive loop.
- Completion of raw archive checkpoints does not guarantee the wrapper fully succeeded. One real run finished all 100 channel checkpoints but then failed during wiki synthesis because `urlparse()` hit `ValueError: Invalid IPv6 URL` on malformed links inside archived messages/files.
- After checkpoint completion, verify the final wrapper output and derived build artifacts. If post-processing crashes on malformed URLs, switch aggregate-history domain extraction to safe parsing that skips invalid URLs, then rerun the wrapper once to finish the wiki build.

## Pitfalls

- Don’t mistake metadata bootstrap pages for full legacy coverage.
- Don’t stop after one `archive` pass if checkpoints still show pending channels.
- Don’t claim message-history-backed coverage unless raw `channel_history_chunk` items actually exist.
- Derived pages must stay summary-first; raw message bodies belong under `raw/`, not in wiki markdown.

## Verification checklist

- [ ] Background process started successfully
- [ ] Checkpoint totals discovered
- [ ] Pending count trends downward across passes
- [ ] No persistent `last_run_status=error` checkpoint failures
- [ ] Raw chunk items are present
- [ ] Final checkpoint state reaches `pending=0`
- [ ] Wiki rebuild finishes successfully
- [ ] History-backed overview page exists

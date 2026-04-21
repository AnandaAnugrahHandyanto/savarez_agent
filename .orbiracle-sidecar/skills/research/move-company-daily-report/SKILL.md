---
name: move-company-daily-report
description: Generate the Move company daily report from the canonical company-wiki with honest diff detection across Slack, Notion, GitHub, and Trello.
---

# Move Company Daily Report

## Use when
- A cron job or operator needs a concise Korean daily report for Move.
- The report should focus on Move's own operating surfaces, not Orbi community signal.
- The user wants actual diffs/events, not generic freshness summaries.

## Goal
Produce one Slack-ready internal brief that answers:
1. what changed recently across Slack / Notion / GitHub / Trello
2. what needs tracking today
3. where the blindspots are

## Required workflow

### 1) Run canonical refresh first
Always run:

```bash
set -euo pipefail
if [ -f "$HOME/.hermes/.env" ]; then
  set -a
  . "$HOME/.hermes/.env"
  set +a
fi
python3 workspace/bin/company-wiki/refresh.py --slack-team moveis --github-org orbisoptimus
```

Important repo-specific finding:
- In this environment the correct working directory is `$HOME/.zeroclaw`, not `~`.
- Do not hardcode `/root/.zeroclaw`; the runtime user here is `orbibot`, so `/root/.zeroclaw` can fail with permission denied.
- If you run from `~`, `python3 workspace/bin/company-wiki/refresh.py` will fail with file-not-found.

### 2) Verify success from canonical artifacts
Check all three:
- latest top-level run manifest under `workspace/company-wiki/raw/run-manifests/`
- `workspace/company-wiki/index.md`
- refresh stdout summary (`ok`, source manifests, build ok)

Minimum success criteria:
- top-level `ok: true`
- `build.ok: true`
- `index.md` built_at timestamp matches the latest refresh window

### 3) Read canonical derived pages
Inspect at minimum:
- `concepts/slack-history-capture-overview.md`
- `concepts/notion-workspace-overview.md`
- `concepts/github-org-overview-orbisoptimus.md`
- `concepts/trello-company-portfolio-overview.md`
- key Notion entity pages (`Action Items`, `Todo`, `Sentry issue`, `slow api`, `PRD`, `회의록`)
- Trello board entity pages for the main operating boards (`Dev`, `공지`)

Use these pages for executive framing, not for assuming that a new diff happened.

### 4) Compare latest vs previous top-level run manifest
Load the latest and immediately previous files under:
- `workspace/company-wiki/raw/run-manifests/*.json`

Use this comparison to answer whether each source actually changed or just refreshed.

Good signals:
- `generated_at`
- per-source manifest paths
- build timestamps
- `created_count` vs `deduped_count`
- Slack `latest_message_ts`
- GitHub repo payload diffs such as changed `pushedAt`
- Trello board `dateLastActivity`
- Notion query `fetched_at`

## Source-specific interpretation rules

### Slack
Do **not** overstate Slack coverage.

Required checks:
- read the latest Slack source manifest under `raw/slack/runs/manifest-*.json`
- inspect `history_channels[*].message_count`
- if a channel has `message_count=0`, treat it as freshness signal only
- only claim message-body evidence when a `channel_history_chunk` raw item exists and contains messages

Practical workflow:
1. compare latest and previous Slack manifest
2. identify channels where `message_count` or `latest_message_ts` changed
3. read the corresponding `raw/slack/items/<dedupe>.json` for actual message text

Observed pitfall:
- `history_ok_count=6` does **not** mean 6 channels had meaningful content captured.
- In one real run, 6 channels were joined successfully but only 1 channel had `message_count=1`; the other 5 had zero messages captured.

### GitHub
Do not stop at repo counts.

Workflow:
1. inspect latest and previous GitHub source manifests
2. open the raw `repo_list` items referenced by each manifest
3. diff repo-level fields, especially `pushedAt`
4. identify which repos actually moved in the comparison window

Observed pitfall:
- top-level concept pages summarize portfolio size and active-repo counts, but the real daily diff may be only one repo push.

### Trello
Treat Trello primarily as current-state board activity unless raw snapshots differ.

Workflow:
1. inspect latest and previous Trello source manifests
2. check `created_count` / `deduped_count`
3. read board entity pages for `dateLastActivity`, visible card count, visible member count
4. only call it a diff if the board snapshot or raw payload actually changed

Observed pitfall:
- a fresh Trello run with `created_count=0` can still look recent because board pages show recent `dateLastActivity`; that is activity state, not necessarily a new raw diff from the immediately previous run.

### Notion
Separate build freshness from content freshness.

Workflow:
1. read latest Notion manifest for workspace-scale counts
2. inspect raw `data_source_query` items for the tracked databases
3. use each query payload's `fetched_at` and row-level `last_edited_time` to judge freshness
4. if today's refresh rebuilt the wiki but the underlying query payloads are older, say so explicitly

Observed pitfall:
- Notion derived pages may show today's `updated` timestamp because the wiki rebuilt, while the underlying `data_source_query` snapshots can still be from the previous day.

## Report writing rules
- Default to Korean.
- Slack-ready: concise, exec-readable, no tool narration.
- Structure:
  1. 오늘 업데이트 상태
  2. 최근 diff / 이벤트 3~6개
  3. 오늘 트래킹 필요한 이벤트 2~5개
  4. 리스크 / 블라인드스팟 (only if notable)
- Distinguish verified facts from inference.
- Lead with implication, then data.

## What counts as a good “tracking item”
Choose items that leadership or operators should watch today, such as:
- release / app review submission / deployment follow-up
- the one repo that actually moved
- unresolved Action Items with stale or missing status
- backlog hygiene issues where a surface looks stale but is still treated as operational
- blindspots in Slack / Notion coverage that affect management confidence

## Verification checklist
- [ ] refresh executed from `~/.zeroclaw`
- [ ] latest manifest and `index.md` confirm success
- [ ] latest vs previous top-level run manifests compared
- [ ] Slack coverage stated honestly using `message_count`
- [ ] GitHub repo-level diff checked via raw repo payloads, not just summary page
- [ ] Notion freshness distinguished between rebuild time and raw query `fetched_at`
- [ ] Trello freshness distinguished from actual diff
- [ ] final output is one Slack-ready Korean message only

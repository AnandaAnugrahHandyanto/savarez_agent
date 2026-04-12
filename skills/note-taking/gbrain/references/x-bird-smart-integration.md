# X/Twitter into GBrain via bird-smart

This machine should prefer `bird-smart` over the official X API for common GBrain
capture flows.

## Why use bird-smart here

- Matches the user's existing X/Twitter workflow and credentials setup
- Avoids the official X API cost/setup burden for single-link and selective capture
- Preserves full threads and article-style posts better than naive single-post capture
- Can selectively pull replies when they add value

Installed paths on this machine:
- Wrapper: `/home/sparta/.local/bin/bird-smart`
- Script: `/home/sparta/.hermes/scripts/bird-smart.py`

Credential policy on this machine:
- default `bird` uses backup credentials
- use main credentials only when required for main-account-only surfaces

## Recommended architecture inside a private monorepo/workspace

Keep the brain repo and collector logic in your real workspace, not under `~/.hermes`.

Suggested layout:

```text
<workspace>/
├── brain/                         # markdown brain repo
│   ├── people/
│   ├── companies/
│   ├── concepts/
│   ├── meetings/
│   ├── ideas/
│   ├── inbox/
│   ├── sources/
│   │   └── social/
│   │       └── x/
│   └── .raw/
│       └── social/
│           └── x/
└── automation/
    └── x/
        ├── capture-x-to-gbrain.py
        └── state/
```

## Operating modes

### 1. Single-link capture

Use for a tweet/thread/article URL the user sends directly.

```bash
python skills/note-taking/gbrain/scripts/capture_x_to_gbrain.py \
  --url "https://x.com/.../status/..." \
  --brain-repo /path/to/brain
```

This should:
- run `bird-smart`
- store raw JSON under `.raw/social/x/`
- write a markdown source note under `sources/social/x/`
- optionally run `gbrain sync --no-pull --no-embed`

### 2. Selective enrichment/backfill

For account or search backfills:
- collect broad batches first with bird/user-tweets or other deterministic collectors
- only escalate individual high-value posts through `bird-smart`
- materialize only worth-keeping captures into the brain repo

### 3. Always-on pipeline

If you want recurring ingestion:
- use native cron/systemd, not Hermes cron, for deterministic polling
- write captures into the brain repo
- sync with `gbrain sync --no-pull --no-embed`
- run `gbrain embed --stale` in batch on a slower cadence

## Filing policy

For raw social captures:
- raw JSON goes under `.raw/social/x/`
- human/agent-readable markdown source docs go under `sources/social/x/`
- durable synthesis belongs on entity/concept pages, not only in the source note

## What to write into the markdown source doc

Minimum useful fields:
- canonical URL
- post ID
- author handle/name
- created timestamp
- classification from `bird-smart`
- fetched surfaces (`read`, `thread`, `replies`)
- concise summary of the post/thread
- notable replies only if they add signal
- path to the raw JSON sidecar

## When to use the official X API instead

Use the official API only if you explicitly need features bird cannot provide well,
for example:
- broad account-wide monitoring at a scale your local bird flow cannot handle
- specialized search windows / rate-limit semantics you specifically want
- collector logic tied to official API metadata such as deletion/engagement tracking across many accounts

For this user's default workflow, `bird-smart` should remain the first choice.

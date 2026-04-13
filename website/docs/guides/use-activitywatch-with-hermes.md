---
sidebar_position: 12
title: "Use ActivityWatch with Hermes"
description: "Use a local ActivityWatch server as a private telemetry source for Hermes reviews, project heat scans, and self-observation workflows."
---

# Use ActivityWatch with Hermes

ActivityWatch is a local, self-hosted activity tracker that records app, window, editor, browser, and AFK signals. Hermes can use that data as a **private telemetry source** to improve reviews and project awareness.

This guide shows how to:
- verify a local ActivityWatch server
- inspect available buckets
- summarize recent activity
- use it safely in Hermes review workflows

## Why use ActivityWatch with Hermes?

Hermes already reads:
- repo state (`git status`, modified files, docs)
- your private brain
- portfolio and review artifacts

ActivityWatch adds a different kind of signal:
- what actually had your attention
- which apps and windows dominated your time
- where perceived work and real work differ
- whether a project is "hot" in practice or only hot in your head

This is most useful for:
- daily project heat scans
- weekly portfolio reviews
- cleanup and context-switch analysis
- answering "what was I actually doing?"

## Prerequisites

- Hermes Agent installed and working
- ActivityWatch running locally
- `python3` and `curl` available

Default local endpoint:

```bash
http://127.0.0.1:5600/api/0/
```

## Step 1: verify the server

```bash
curl -s http://127.0.0.1:5600/api/0/info
```

Expected output is JSON with version and hostname.

If you get no response, make sure ActivityWatch is running.

## Step 2: inspect bucket types

List available buckets:

```bash
curl -s http://127.0.0.1:5600/api/0/buckets/
```

For a cleaner view:

```bash
python3 - <<'PY'
import urllib.request, json
u = 'http://127.0.0.1:5600/api/0/buckets/'
data = json.loads(urllib.request.urlopen(u, timeout=5).read().decode())
for bucket_id, meta in data.items():
    print(f"{bucket_id:45}  {meta.get('type')}")
PY
```

Common bucket types include:
- `currentwindow`
- `afkstatus`
- `app.editor.activity`
- `web.tab.current`
- `os.hid.input`

## Step 3: summarize recent activity

Do **not** ingest raw event streams into canon by default.
Summarize a bounded time window first.

Example: top app/window signals over the last 24 hours.

```bash
python3 - <<'PY'
import urllib.request, json, datetime as dt
from collections import Counter

BASE = 'http://127.0.0.1:5600/api/0'
now = dt.datetime.now(dt.timezone.utc)
start = (now - dt.timedelta(hours=24)).isoformat()
end = now.isoformat()

buckets = json.loads(urllib.request.urlopen(f'{BASE}/buckets/', timeout=5).read().decode())
window_buckets = [bid for bid, meta in buckets.items() if meta.get('type') == 'currentwindow']

counter = Counter()
for bid in window_buckets:
    url = f'{BASE}/buckets/{bid}/events?start={start}&end={end}'
    events = json.loads(urllib.request.urlopen(url, timeout=10).read().decode())
    for ev in events:
        data = ev.get('data') or {}
        app = data.get('app') or 'unknown'
        title = (data.get('title') or '')[:80]
        counter[(app, title)] += ev.get('duration', 0) or 0

for (app, title), secs in counter.most_common(20):
    print(f'{secs/3600:5.2f}h  {app:20}  {title}')
PY
```

## Step 4: use it in Hermes reviews

The best first wedge is **private review enrichment**, not public posting and not giant lifelog ingestion.

Examples:

### Daily heat scan
Ask Hermes to compare:
- repo activity
- project board priorities
- ActivityWatch attention signals

This can reveal:
- which project actually got attention
- what felt important but didn't get real time
- what generated git noise without real focus

### Weekly portfolio review
Ask Hermes:

```text
Use repo signals plus ActivityWatch data from the last 7 days.
Tell me whether my attention matched my Core Now projects,
where I context-switched too much, and what probably deserves cleanup or demotion.
```

### Context reconstruction
Ask Hermes:

```text
Use ActivityWatch and repo signals to reconstruct what I was probably working on yesterday.
Prefer concrete app/window/repo evidence over generic guesses.
```

## Safe usage rules

Treat ActivityWatch as:
- a **signal source**
- a **private telemetry layer**
- a **review input**

Do **not** treat it as:
- unquestionable truth
- a substitute for repo truth
- default public content input

## Recommended rollout path

Start simple:
1. Use ActivityWatch manually in review prompts
2. Add it to private heat/weekly workflows if it proves useful
3. Only then consider a reusable tool, skill, plugin, or MCP wrapper

That keeps the integration honest and avoids building a telemetry monster before proving the workflow.

## Optional skill

Hermes also ships an optional skill for this workflow style:

```bash
hermes skills install official/productivity/activitywatch
```

That skill focuses on:
- local HTTP API usage
- bucket inspection
- bounded summaries
- integrating ActivityWatch into Hermes' review workflows

## Relationship to OpenClaw

If you also use OpenClaw, the cleanest approach is:
- prove a Hermes review workflow first
- keep the logic small and local
- port or generalize only after the output is clearly useful

Do not try to unify everything at once.
A proven single-wedge workflow beats a grand integration that never stabilizes.

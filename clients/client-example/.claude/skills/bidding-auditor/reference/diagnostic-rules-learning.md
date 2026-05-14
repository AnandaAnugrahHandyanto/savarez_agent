# Module 3 — Learning Phase (BID-D10 → BID-D13)

Total module weight: 15 points. The Smart Bidding learning system (per /sops/Smart Bidding Mechanics Reference.md) takes ~14 days to stabilise after any strategy or target change. Mutations during learning compound the reset and reduce predictive accuracy.

Source of truth for last-change dates: `context/account-changelog.md`. Auditor: max 24h old. Optimizer: max 1h old (mandatory auto-pull).

## BID-D10 — Extended Learning (4 pts)

**Definition:** Strategy that has been in "Learning" status for >14 days.

**Detection:** Google Ads API does expose `bidding_strategy.system_status` in some surfaces; `campaign.serving_status` does not include learning explicitly. v1 surfaces this as INFO and asks the analyst to confirm via the Google Ads UI / Bid Strategies report. v1.1 wires up `system_status` parsing.

**Verdict:** INFO in v1.

## BID-D11 — Changes During Learning (4 pts)

**Definition:** Strategy or target changed within the learning window (<14 days), and a *second* change has been queued or applied within the same window.

**Logic:**

| Condition | Verdict |
|---|---|
| Both `daysSinceStrategy` and `daysSinceTarget` < 14d, with non-equal values | WARN |
| Otherwise | PASS |

**Routing:** Hard refuse on optimizer until the older of the two cleared 14d. Override: `--force-learning --override-reason="..."`.

## BID-D12 — Learning Data Exclusion (3 pts)

**Goal:** When tracking has had a recorded outage, a `bidding_data_exclusion` should cover the window so smart bidding doesn't learn from broken data.

**Logic:** v1 surfaces the exclusion list and asks the analyst to confirm vs `tracking-specialist` history. INFO-only.

## BID-D13 — Recent Strategy Change (4 pts)

**Definition:** Strategy changed within last 14 days.

**Logic:**

| Condition | Verdict |
|---|---|
| `daysSinceStrategy` < 14d | WARN |
| Otherwise | PASS |

**Routing:** Optimizer hard-refuses any new mutation on this campaign until the window clears. Surfacing this in the auditor lets the analyst stage the next change rather than fire it now.

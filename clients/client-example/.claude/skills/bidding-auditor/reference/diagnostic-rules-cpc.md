# Module 6 — CPC & Cost Health (BID-D22 → BID-D24)

Total module weight: 10 points. Symptom layer — these surface external pressure but rarely the root cause. Findings primarily route to the Comp layer of the cascade (`/competitive-analyst`).

## BID-D22 — CPC Spike (4 pts)

**Threshold:** `cpcSpikeThresholdPct` (default 25%).

**Logic:** Compute average CPC for last 14 days vs. prior 14 days. If `(recent - prior) / prior >= 25%` → WARN.

**Routing:** `/competitive-analyst` for auction context.

## BID-D23 — Rising CPC Trend (3 pts)

**Threshold:** `cpcRisingTrendPeriods` (default 3) consecutive 7-day periods.

**Logic:** Last N×7 daily rows split into N buckets; if each bucket's average CPC strictly exceeds the previous → WARN.

## BID-D24 — Bid Simulator Gap (3 pts)

**v1:** Heuristic in `lib.js → getOpportunityValue`. Uses `metrics.search_budget_lost_impression_share` to project incremental conversions if budget loosens, then compares projected CPA to break-even.

**Output:** Always emits an opportunity entry (cross-cutting) when the heuristic fires. Diagnostic verdict is INFO (not points-bearing as a "fail" — it's an opportunity, not a defect).

**v1.1:** Replace heuristic with `CampaignBidSimulatorService` for accurate projections (only valid on Target CPA / Target ROAS / Manual CPC campaigns).

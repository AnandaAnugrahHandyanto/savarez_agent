# Module 1 — Strategy Selection (BID-D01 → BID-D04)

Total module weight: 20 points. All four diagnostics run on every campaign type. The first three carry points; BID-D04 is INFO-only and exists for the auditor's reasoning.

## BID-D01 — Strategy Appropriateness (5 pts)

**Goal:** Confirm the bid strategy fits campaign maturity and goals.

**Inputs:** `campaigns-bidding-perf.csv` aggregate row + `Conversion Volume Thresholds Reference.md` thresholds for the campaign's channel + strategy.

**Logic:**

| Condition | Verdict |
|---|---|
| Smart bidding ≥ functional minimum for channel/strategy | PASS |
| Manual CPC on campaign producing ≥ `manualBiddingMaxConv` (default 100) conv/30d | WARN |
| Smart bidding below absolute minimum for channel | FAIL |
| All other configurations | PASS |

**Routing:** Findings flow to BID-E01 (Select bid strategy) via `/bidding-optimizer setup`.

## BID-D02 — Manual on High-Volume (5 pts)

**Goal:** Identify campaigns running Manual CPC that have crossed into smart-bidding-eligible volume.

**Threshold:** `manualBiddingMaxConv` (default 100 monthly conv).

**Logic:** Manual bidding + monthly conv ≥ threshold → FAIL. Otherwise PASS or SKIP (not manual).

**Routing:** Recommend a manual → smart bidding migration via the Google Ads UI Drafts & Experiments lifecycle (run a 50/50 experiment for 14–30 days, then promote if the treatment wins on the primary KPI).

## BID-D03 — Smart Bidding Without Data (10 pts)

**Goal:** Smart bidding cannot learn without enough conversions. Channel-aware thresholds.

**Threshold source:** `Conversion Volume Thresholds Reference.md`. Defaults:
- Search tCPA / MaxConv: absolute 15, functional 30, recommended 50
- Search tROAS / MaxConvValue: absolute 30, functional 50
- Shopping tROAS: absolute 30, functional 50
- PMax tCPA / tROAS (added on top of MaxConv*): absolute 15 / 30
- Display, Demand Gen: same as Search

**Logic:** Smart bidding + monthly conv < absolute → FAIL.

**Routing:** Vol-layer sub-cascade (see synthesis-playbook). Auditor presents an options menu rather than a single handoff: switch to MaxConv, broaden match types via /keyword-optimizer, raise budget via /budget-optimizer, or accept 30 more days at current trajectory.

## BID-D04 — Conversion Action Alignment (INFO)

**Goal:** Sanity check that the strategy is optimizing for the right actions.

This diagnostic is INFO-only because identifying the "right" actions requires unit-economics judgment that lives upstream. The auditor surfaces the configured `primaryConversionAction` and lets the analyst confirm.

---

## Channel-aware notes

- MaxConv-style strategies have no target → BID-D05/D06 SKIP for those campaigns.
- BID-D01 distribution rules hold regardless of channel; only the volume threshold lookup changes.
- BID-D03 is the most channel-sensitive — always read from the threshold reference.

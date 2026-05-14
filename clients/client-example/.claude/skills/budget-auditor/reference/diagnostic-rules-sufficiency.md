# Module 2 — Sufficiency (BUD-D05 → BUD-D08)

Total module weight: **15 points**. Two diagnostics carry points (BUD-D05 + BUD-D08); two are informational.

## BUD-D05 — Daily budget : tCPA ratio (6 pts)

**Goal:** Daily budgets below 2× target CPA starve smart bidding's daily decision space.

**Inputs:** `campaigns-budget-perf.csv`. Pull `campaign_budget.amount_micros` and the relevant target field (`campaign.target_cpa.target_cpa_micros` or `campaign.maximize_conversions.target_cpa_micros`).

**Logic:**
- Applies to Search + Shopping campaigns with a tCPA target.
- ratio = daily_budget / tCPA
- ratio < `budgetAudit.dailyBudgetToCpaRatio` (default 2.0) → flag.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** Tagged `blocking: ['bidding']`. Optimizer's `raise` subcommand sequences this fix BEFORE any budget-only mutation: budget rise alone won't help if tCPA is calibrated wrong. Hands off to `/bidding-specialist`.

**Channel-aware:**
- **PMax (conv-value driven):** SKIP — tCPA may not be primary lever; rely on volume floor (BUD-D08).
- **Manual CPC:** SKIP — no smart-bidding constraint.

## BUD-D06 — Exhaustion timing (3 pts) — analyzed in `analyze-pacing.js`

**Goal:** Daily budgets that exhaust before EOD lose late-day traffic.

**v1 heuristic:** Without hourly segmentation, flag campaigns where `cost_per_day >= 0.95 × daily_budget` on **≥ 50% of the last 14 days**.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** Optimizer's `raise` subcommand for the affected campaigns; or `/geo-schedule-auditor` if the cause turns out to be a daypart concentration.

**v1.1:** Replace heuristic with hourly segmentation when the row-count tradeoff is acceptable.

## BUD-D07 — 2× spending limit awareness (INFO)

**Goal:** Surface for the analyst that Google may spend up to 2× the daily budget on STANDARD-delivery budgets.

**Logic:** Count budgets with `delivery_method = STANDARD` (default) — informational only, never a verdict deduction.

**Routing:** Inform on the report. Used to set caller expectations for the `raise` plan.

## BUD-D08 — Smart-bidding minimum conv volume (6 pts)

**Goal:** Smart bidding can't optimize without enough conversions per channel.

**Inputs:** `campaigns-budget-perf.csv` aggregate row + threshold lookup table in `lib.js → getMinConvVolumeForSmartBidding`. Channel + strategy-aware.

**Logic:**
- Skip if strategy is not smart bidding.
- Normalize raw conversions in the audit window to monthly: `monthlyConv = conv * (30 / period)` when `period >= 30`.
- Threshold examples (defaults from /sops/Conversion Volume Thresholds Reference.md):
  - SEARCH tCPA / MaxConv: 30
  - SEARCH tROAS / MaxConvValue: 50
  - SHOPPING tROAS: 50
  - PMAX tCPA / tROAS: 30 / 50
  - DISPLAY / VIDEO / DEMAND_GEN tCPA: 30

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** Tagged `blocking: ['bidding']`. Sequenced before any raise — raising budget alone won't fix a learning-starved smart strategy. Hands off to `/bidding-specialist`.

---

## Source

- /sops/Budget Pacing Reference.md — daily limit, 2× rule
- /sops/Conversion Volume Thresholds Reference.md — channel-specific minimums
- /sops/Smart Bidding Mechanics Reference.md — learning-period constraints

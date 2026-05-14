# Module 1 — Limitation (BUD-D01 → BUD-D04)

Total module weight: **25 points**. Runs on every channel type. Profitable/unprofitable labels depend on `primaryKPI` + break-even — when those are missing the module still runs but the profitability-dependent diagnostics return INFO with a `business` blocking tag.

## BUD-D01 — Limited status (5 pts)

**Goal:** Detect campaigns showing budget-limited signal in the audit window.

**Inputs:** `campaigns-budget-perf.csv` aggregate row.

**Logic:**
- IS Lost (Budget) (`metrics.search_budget_lost_impression_share`) >= `budgetAudit.isLostBudgetThreshold` (default 10%) → flag.
- For non-Search/Shopping channels (PMax/Display/Video) where IS metrics are sparse, fall back to the explicit "Limited by budget" status if exposed in the API response (currently inferred from IS Lost (Budget) only).

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** Module 4 (Allocation) consumes the flagged set; the optimizer's `raise` subcommand reads it.

## BUD-D02 — IS Lost Budget severity (5 pts)

**Goal:** Bucket the severity of budget-loss across the account.

**Logic:**
- Heavy = IS Lost (Budget) ≥ 25%.
- 0 heavy → PASS
- 1–2 heavy → WARN
- ≥ 3 heavy → FAIL

**Routing:** Drives Module 1 score floor; opportunities engine consumes profitable-heavy intersection.

## BUD-D03 — Profitable + limited (10 pts) ⭐

**Goal:** Profitable campaigns that are budget-limited are the highest-leverage raise opportunity.

**Logic:**
- For each BUD-D01-flagged campaign, run `classifyProfitability(row, primaryKPI, breakEven)`.
- `state === 'profitable'` (margin > 0) → flag here AND emit a `profitable_limited_recovery` opportunity with a profit-projected dollar value.
- If `primaryKPI` or `breakEven` missing → finding returns INFO with `blocking: ['business']` and routes to `/strategy-specialist`.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN (action available — not a failure state because raising budget is a positive lever, not a defect to fix)

**Routing:** Opportunities surface to `/budget-optimizer raise`. Blocked when measurement layer is dirty (handoff to `/tracking-specialist`).

## BUD-D04 — Unprofitable + limited (5 pts)

**Goal:** Unprofitable campaigns that are still budget-limited represent active harm — they will absorb every additional dollar at a loss.

**Logic:**
- For each BUD-D01-flagged campaign, classify profitability.
- `state === 'unprofitable'` (margin < 0) → flag.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → FAIL

**Routing:** Optimizer's `reduce` subcommand reads this list. Never recommend a raise here — peer skills (`/keyword-auditor`, `/quality-score-auditor`, `/lp-auditor`, `/offer-auditor`) recover efficiency first.

---

## Channel-aware notes

- **PMax / Display:** IS metrics are partial — when `metrics.search_budget_lost_impression_share` is empty, treat BUD-D01 as INFO and rely on Module 3 exhaustion data for the same signal.
- **Shopping:** Behaves like Search for IS metrics; same thresholds apply.
- **Video / Demand Gen:** No IS metrics — both diagnostics SKIP; Module 4 (Allocation) carries the load instead.

---

## Source

- /sops/Budget Pacing Reference.md — daily limit / 2x rule
- /sops/Budget Allocation Mental Model.md — profitable+limited as the headline allocation move
- /sops/Bid Scaling Mental Model.md — PAR-zone framing for "scale" vs "hold"

# Module 3 — Monthly Pacing (BUD-D09 → BUD-D12)

Total module weight: **15 points**. Runs only when `budgetAudit.monthlyBudgetTotal` is set OR fallback mode is OFF. If `targetFallbackMode = "no_monthly_target"`, all four diagnostics return SKIP and the module's 15 points redistribute.

Engine: `analyze-pacing.js`. Produces `findings-pacing.json`, `opportunities-pacing.json`, and `pacing-projection.csv` (account-level series + projected daily run-rate to month end).

## BUD-D09 — MTD spend vs target (4 pts)

**Goal:** Detect daily-rate drift in either direction during the month.

**Logic:**
- `mtdSpend` = sum of `metrics.cost_micros` over current calendar month.
- `proportionalTarget` = `monthlyBudgetTotal × (daysElapsed / daysInMonth)`.
- `deviationPp` = `(mtdSpend − proportionalTarget) / monthlyBudgetTotal × 100`.

**Verdicts:**
- |deviationPp| ≤ `overspendAlertPp` (default 10) → PASS
- otherwise → WARN

## BUD-D10 — Overspend alert (4 pts)

**Goal:** Flag projection that exceeds the monthly budget.

**Logic:**
- `projectedMonth` = `(mtdSpend / monthRowsCount) × daysInMonth`.
- `deviationPct` = `(projectedMonth − monthlyTarget) / monthlyTarget × 100`.

**Verdicts:**
- ≤ `overspendAlertPp` → PASS
- > `overspendAlertPp` → WARN
- > `2 × overspendAlertPp` → FAIL

**Routing:** Opportunities engine emits a `pacing_throttle` recommendation routed to `/budget-optimizer reduce` or `/budget-optimizer pacing-adjust`.

## BUD-D11 — Underspend alert (4 pts)

**Goal:** Symmetric mirror of BUD-D10. Underspend is harmful especially in seasonality months.

**Logic:**
- Same projection math; flag when `deviationPct < −underspendAlertPp` (default 10).
- Severity escalates if `seasonalityProfile.isHighlight` for the current month.

**Routing:** Emits an `underspend_redeploy` opportunity routed to `/budget-optimizer reallocate` (deploy unspent dollars to winners) — not a raise of the monthly target.

## BUD-D12 — Seasonal adjustment awareness (3 pts)

**Goal:** Flag the analyst when next month is a designated highlight month and budgets haven't been ramped.

**Logic:**
- Read `budgetAudit.seasonalityProfile`.
- If `mode = highlight_months` and the **next month** is in `months[]`, return WARN with an opportunity to scale profitable campaigns preemptively.
- If currently IN a highlight month, return INFO with a banner advising widened pacing tolerance.
- If `mode = flat`, return INFO with no action.

---

## Skip behavior

- `monthlyBudgetTotal === null` AND `targetFallbackMode !== "no_monthly_target"` → entire module SKIPs with explicit "configure monthly target" message.
- `targetFallbackMode === "no_monthly_target"` → SKIP with banner "pacing intentionally disabled".

When SKIP, the 15 module points redistribute proportionally across the other 4 modules per the scoring model.

---

## Source

- /sops/Budget Pacing Reference.md — monthly budget mechanics
- /sops/Goals and KPIs Mental Model.md — seasonality framing

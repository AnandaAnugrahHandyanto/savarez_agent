# Module 4 — Allocation (BUD-D13 → BUD-D16)

Total module weight: **30 points** — the heaviest module because cross-campaign reallocation is the single highest-leverage budget decision and it drifts every month as performance shifts.

**Critical:** Group experiment-type rows under their base (via `lib.js → groupExperimentsWithBases`) before computing budget share. A base+experiment pair is one budget consumer, not two.

## BUD-D13 — Underfunded high performers (10 pts) ⭐

**Goal:** Profitable campaigns running below 5% share of total spend.

**Inputs:** Per-consumer spend share, profitability classification.

**Logic:**
- For each consumer, compute `sharePct = cost / totalSpend × 100`.
- If `state === 'profitable'` AND `sharePct < 5` AND `cost >= 10` (noise filter) → flag.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** Tagged `blocking: ['business']` when break-even missing. Otherwise routes to `/budget-optimizer reallocate` (lower X + raise Y).

## BUD-D14 — Overfunded underperformers (10 pts) ⭐

**Goal:** Unprofitable campaigns consuming ≥ 5% of total spend — the most harmful form of misallocation.

**Logic:**
- Mirror of BUD-D13; flag `state === 'unprofitable'` AND `sharePct >= 5`.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → FAIL

**Routing:** `/budget-optimizer reduce` first; downstream peer skills (`/keyword-auditor`, `/lp-auditor`, `/offer-auditor`) for efficiency recovery.

## BUD-D15 — Cross-campaign efficiency (5 pts)

**Goal:** Score the share of classified spend going to profitable campaigns.

**Logic:**
- Sum costs of profitable + unprofitable consumers (ignore unclassified).
- `profShare = profitableCost / (profitableCost + unprofitableCost)`.

**Verdicts:**
- profShare ≥ 0.7 → PASS
- 0.5 ≤ profShare < 0.7 → WARN
- < 0.5 → FAIL
- Insufficient classified spend OR break-even missing → INFO

## BUD-D16 — Zero-spend active campaigns (5 pts)

**Goal:** Enabled+SERVING campaigns that produced zero spend in the audit window — almost always policy/approval/targeting issues.

**Logic:**
- Consumer with `cost === 0` and at least one member row with `serving_status = SERVING`.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** `/account-auditor` and `/account-changelog` first; budget action is blocked until the structural cause is identified.

---

## Channel-aware notes

- **PMax:** Counts as a normal consumer; share of spend is comparable across channels.
- **Shopping with shared budget:** Use the experiment-grouping logic — each shared-budget pool is one consumer for allocation math; member campaigns inherit the share.
- **Display / Video:** Same logic. Cross-channel comparisons are valid because the question is "where do dollars go?" not "which channel wins?"

---

## Source

- /sops/Budget Allocation Mental Model.md — 4-step framework, MVB calculation
- /sops/Goals and KPIs Mental Model.md — profitability classification

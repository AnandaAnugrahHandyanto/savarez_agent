# Module 5 — Shared Budgets (BUD-D17 → BUD-D19)

Total module weight: **15 points**. SKIPs entirely if no shared budgets exist; weight redistributes proportionally to the other modules. Same N/A pattern as keyword-auditor's "no PMax campaigns" handling.

## BUD-D17 — Imbalance (5 pts)

**Goal:** Detect shared budgets where one campaign captures the lion's share of the pool.

**Logic:**
- For each shared budget (`campaign_budget.explicitly_shared = true`), find member campaigns and their costs.
- `dominanceShare = max(member_cost) / total_pool_cost`.
- > 0.7 → flag.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Experiment-aware:** When an experiment-type campaign joins the pool, flag the configuration explicitly — treating an A/B variant as a shared-budget peer can starve the base mid-test. Do NOT count it as a separate dominator; instead surface it as a "configuration risk" sub-finding inside BUD-D17.

## BUD-D18 — Different objectives (5 pts)

**Goal:** Shared budgets work best when members serve the same goal. Flag pools mixing channel types or strategy categories.

**Logic:**
- channelSet = unique `advertising_channel_type` across members.
- strategySet = unique `bidding_strategy_type` across members.
- Either set has size > 1 → flag.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

## BUD-D19 — Portfolio conflict (5 pts)

**Goal:** Shared budget + portfolio bid strategy on the same members is operationally fragile — two pooling layers that can fight each other when traffic shifts.

**Logic:**
- For each shared budget, identify members with a non-empty `campaign.bidding_strategy` (portfolio strategy resource name).
- ≥ 1 member uses a portfolio → flag.

**Verdicts:**
- 0 flagged → PASS
- ≥ 1 flagged → WARN

**Routing:** Tagged `blocking: ['bidding']`. Hands off to `/bidding-specialist` for portfolio strategy review before any budget-side mutation.

---

## SKIP rules

- No campaigns have `campaign_budget.explicitly_shared = true` → all three diagnostics SKIP, module returns N/A, weight redistributes.

---

## Source

- /sops/Budget Pacing Reference.md — individual vs shared budget mechanics
- /sops/Bid Strategy Selection Reference.md — portfolio bidding behavior

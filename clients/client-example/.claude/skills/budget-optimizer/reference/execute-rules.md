# Budget Optimizer — Execute Rules

Per-action recipes for how the SKILL generates `operations.json` from auditor findings.

Common envelope for every op:

```json
{
  "resource": "campaign_budget",
  "type": "update",
  "resource_name": "customers/{cid}/campaignBudgets/{bid}",
  "fields": { "amount_micros": 6500000 },
  "meta": {
    "mutation_type": "raise" | "reduce" | "reallocate" | "fix-shared" | "pacing-adjust",
    "target": "Campaign or shared budget name",
    "campaign_id": "1234567890",
    "channel_type": "SEARCH",
    "step_cap": { "from_micros": 5000000, "to_micros": 6500000, "multiplier": 1.3 },
    "cascade_clear": { "measurement": "pass", "business": "pass", "bidding": "pass", "efficiency": "pass", "conversion": "pass" },
    "tcpa": 60,                     // dollars; for Search/Shopping raise sanity
    "pmax_volume_floor": 50,        // dollars; for PMax raise sanity
    "confirmed": false,             // flips true after user types "confirm" on a soft-block
    "override_flags": [],
    "rationale": "BUD-D03 — profitable + IS-Lost(Budget) 28%; projected +$1,824/mo at $112 CPA (within $200 break-even)."
  }
}
```

## BUD-E01 / BUD-E07 — Raise

**Triggers:** BUD-D01–D03 + opportunity-mode `profitable_limited_recovery` or `winner_underfunded`.

**Recipe:**
1. From auditor findings, list candidate campaigns where `state === 'profitable'` AND `is_lost_budget >= isLostBudgetThreshold` (default 10%).
2. For each candidate, compute target `new_amount_micros = clamp(old × multiplier, min_floor, ...)`. Default `multiplier = 1.3`. If user requested a larger move, split into multiple ops (queued for separate sessions).
3. Hydrate `meta.tcpa` from `campaigns-budget-perf.csv` (Search/Shopping). Hydrate `meta.pmax_volume_floor` from `budgetAudit.pmaxVolumeFloor` (extension config; falls back to $50/day default).
4. Render the cascade: `cascade_clear.measurement` from any `tracking-specialist` finding overlapping the campaign; `cascade_clear.business` from `primaryKPI`/`breakEven` presence; `cascade_clear.bidding` from BUD-D05/D08/D19 overlap; `cascade_clear.efficiency` from any fresh search-term/QS/RSA finding; `cascade_clear.conversion` from any fresh LP/offer finding.
5. Surface the projected `+$/mo = (new − old) × 30.4` and the auditor's profit projection in the rationale string. Round to nearest dollar.
6. Show the user the full plan + cascade banner. If any layer is `recommended`/`soft-block`, prompt: "Override and proceed? Type 'confirm' with reason."
7. Write `created/budget-ops/operations-{date}-raise.json`.

## BUD-E04 — Reduce (and reduce side of reallocate)

**Triggers:** BUD-D04 (unprofitable + limited), BUD-D14 (overfunded underperformers), BUD-D10 (overspend pacing).

**Recipe:**
1. From findings, list candidate campaigns where `state === 'unprofitable'` AND share of spend is material (≥ 5%).
2. Compute `new_amount_micros = old × 0.7` by default (30% reduction; configurable). For reductions there is no step cap — bringing spend down is always safe relative to learning resets.
3. Set `mutation_type = "reduce"`. No tCPA / volume-floor sanity check (reductions don't need one).
4. Cascade: still requires M+B clear (don't change unprofitable without unit economics) but Eff/Conv soft blocks don't apply.
5. Show the plan; the dollar value is "freed budget" the user may then deploy via `reallocate` or leave unspent.

## BUD-E02 / BUD-E04 portfolio rebalance — Reallocate

**Triggers:** BUD-D11 underspend redeploy opportunity; BUD-D13 underfunded winners + BUD-D14 overfunded losers.

**Recipe:**
1. Build paired ops: a `reduce` leg on the loser + a `raise` leg on the winner. Net daily delta should be ≈ 0 (reallocation is internal).
2. Each leg gets its own `step_cap` and gates. The raise leg gets full raise sanity checks; the reduce leg has none.
3. The dry-run table groups them visually so the user sees "from X / to Y / +$net".
4. Order in the file: reduces before raises (mutate.js sorts this anyway).

## BUD-E05 — Fix shared

**Triggers:** BUD-D17 imbalance, BUD-D18 mixed objectives, BUD-D19 portfolio conflict.

**v1 limitation:** `explicitly_shared` is immutable in place. A "fix" usually means:
- **Imbalance fix:** raise the shared budget total, OR split into two budgets and update each campaign's `campaign.campaign_budget`. v1 supports the raise; the split is surfaced as a manual handoff to the Google Ads UI.
- **Mixed objectives:** split into per-objective budgets — manual handoff in v1.
- **Portfolio conflict:** route to `/bidding-specialist` to drop the portfolio, then optionally rebalance the shared budget here.

When v1 can act, the op is a simple `update` of `amount_micros` on the shared budget; otherwise the SKILL writes a markdown handoff file under `created/budget-ops/handoff-{date}-fix-shared.md` with paste-ready UI steps.

## BUD-E06 — Pacing-adjust

**Triggers:** BUD-D10 (overspend), BUD-D11 (underspend).

**Recipe:**
1. Compute the pacing delta needed to bring `projectedMonth` back inside `±overspendAlertPp` of `monthlyBudgetTotal`.
2. Apply that delta proportionally across `campaignTargets`-tagged campaigns (or evenly if no per-campaign targets are set), respecting "protect" priority (no reduction) and "scale" priority (preferred for raises).
3. Each adjusted budget gets its own op with `mutation_type = "pacing-adjust"`. Use the same 1.3× cap when raising.
4. Dry-run table shows total monthly impact at the bottom.

## BUD-E03 — Scale bids and budgets

**v1 boundary:** budget-side only. Target CPA/ROAS adjustments stay with `/bidding-specialist`. The SKILL emits the budget legs and writes a handoff file `created/budget-ops/handoff-{date}-scale.md` documenting the paired bid action with paste-ready `/bidding-optimizer scale` invocations.

## BUD-E08 — Monitoring alerts

**Deferred to v1.1.** Documented as a known gap. v1.1 will write `monitoring/budget-alerts.json` consumed by the future `/daily-monitor` orchestrator.

---

## Output paths

```
created/budget-ops/operations-{YYYY-MM-DD}-{subcommand}.json
created/budget-ops/handoff-{YYYY-MM-DD}-{subcommand}.md     (when manual handoff needed)
tmp/budget-optimizer/mutations-{ISO}.json                    (mutation history, post-live)
context/analysis/budget-changelog.md                         (append-only)
```

## Source

- /sops/Budget Allocation Mental Model.md — recipe basis
- /sops/SOP – Scale Bids and Budgets.md — phased scaling workflow
- /sops/Bid Targets Reference.md — break-even / target reasoning

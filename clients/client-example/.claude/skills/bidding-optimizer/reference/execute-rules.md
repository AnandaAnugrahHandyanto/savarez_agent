# Bidding Optimizer — Execute Rules per Subcommand

Each subcommand emits operations with shared `meta` shape:

```json
{
  "resource": "campaign | bidding_strategy | campaign_criterion | bidding_data_exclusion | conversion_value_rule | campaign_draft | campaign_experiment",
  "type": "create | update | remove",
  "resource_name": "customers/.../campaigns/...",
  "fields": { /* mutation payload */ },
  "meta": {
    "action_id": "BID-Exx",
    "target": "<campaign or portfolio name>",
    "campaign_id": "...",
    "is_portfolio": false,
    "strategy": "TARGET_CPA | TARGET_ROAS | ...",
    "field": "target_cpa.target_cpa_micros",
    "old_value": <current value, in API units>,
    "new_value": <new value, in API units>,
    "mutation_type": "strategy | target | modifier | exclusion | rule | other",
    "step_cap": { "from": <num>, "to": <num>, "pct": <num> },
    "cascade_clear": { "measurement": "pass", "business": "pass", "efficiency": "pass", "conversion": "pass" },
    "learning_gate": { "last_strategy_change": "...", "last_target_change": "...", "days_since_strategy": <n>, "days_since_target": <n> },
    "override_flags": [],
    "rationale": "Auditor finding + cascade outcome"
  }
}
```

---

## BID-E01 / BID-E02 — `setup`

**Goal:** Recommend a strategy and initial targets for a campaign.

**Modes:**
- Interactive: prompt the user through campaign type → conv volume estimate → primary KPI → posture, then recommend.
- Programmatic (`--output=json`): used by launchers. Returns:
  ```json
  { "recommendedStrategy": "TARGET_CPA", "initialTcpa": 60, "portfolioAssignment": null, "rationale": "..." }
  ```

**Decision tree:** see /sops/SOP – Select a Bidding Strategy.md and /sops/Bid Strategy Selection Reference.md.

**Output:** No mutations unless the user confirms — then route to `adjust-targets` or `migrate`.

## BID-E09 — `adjust-targets`

**Goal:** Move tCPA / tROAS by ≤ 20% (≤ 30% with `--aggressive`).

Operation:
- `resource: "campaign"` (or `bidding_strategy` for portfolio)
- `type: "update"`
- `fields: { target_cpa: { target_cpa_micros: <new_micros> } }` (or `target_roas: { target_roas: <new_ratio> }`)
- `meta.mutation_type: "target"`

The auditor passes the recommended new value, clamped to the step cap and cascade safety. Optimizer re-validates the gates.

## BID-E11 — `scale`

**Goal:** Coordinate target raise + budget raise (paired with `/budget-optimizer raise`).

Bidding side: target loosens by ≤ 20% (typically 10–15%) so smart bidding can spend the new budget.

`scale` always emits a follow-up note that the budget-optimizer must run *first* — opening up budget while target stays tight just spends more on the same auctions.

## BID-D17 fix — `fix-shared-portfolio`

**Goal:** Resolve shared-budget + portfolio-strategy conflict.

Two paths the user can pick:
- **Convert the budget to non-shared** (recommended in 80% of cases). Operations: `campaign_budget` update with `explicitly_shared: false` — but this affects the budget skill, so this subcommand emits the operation with `meta.handoff: "/budget-optimizer"` and refers the user to that skill.
- **Convert the portfolio to a single-campaign portfolio**. Operations on `bidding_strategy` are limited; effectively the resolution is to detach the campaign from the portfolio (`campaign.bidding_strategy = null`) and re-create inline targets. Surface this clearly — it's a learning-resetting move.

## BID-E07 — `remove-adjustments`

**Goal:** Strip ignored modifiers off smart-bidding campaigns; clean up stale modifiers on mCPC.

Operations:
- `campaign_criterion` update with `bid_modifier: 1.0` (returns the modifier to neutral)

Filters: only emit for `bid_modifier != 1.0` and `bid_modifier != 0.0` (0 is exclusion, never auto-removed).

## BID-E08 — `cpc-cap`

**Goal:** Add / remove / adjust CPC caps. Operations on `campaign` or `bidding_strategy` — `target_roas.cpc_bid_ceiling_micros` or `target_impression_share.cpc_bid_ceiling_micros`.

Defaults to **remove cap** for smart-bidding campaigns; explicit `--add=$X` for adding one.

## BID-E14 — `data-exclusion`

**Goal:** Cover a tracking outage so smart bidding doesn't learn broken data.

Operations:
- `bidding_data_exclusion` create with required fields `name`, `scope`, `start_date_time`, `end_date_time`, plus `campaigns` / `devices` / `advertising_channel_types` depending on scope.

Auto-name pattern: `"Tracking outage {YYYY-MM-DD} {scope}"` — generation phase fills this in so the user doesn't have to.

Scope: `CAMPAIGN` or `CHANNEL` per /sops/Data Exclusions Reference.md.

## BID-E13 — `schedule`

Manual CPC only. Operations on `campaign_criterion` (ad_schedule). Emit only when `meta.strategy === 'MANUAL_CPC'`.

## BID-E12 — `modifiers`

Manual CPC only. Same as above for device / location / audience modifiers.

## BID-E04 / BID-E03 — `value-bidding`

**Goal:** Set up value-based bidding (TARGET_ROAS / MAXIMIZE_CONVERSION_VALUE) or value-aware conversion-based bidding.

Operations:
- `conversion_value_rule` create / update / remove
- For setup: assist the user in switching campaign strategy (which goes through `migrate`).

Refuse if `valueRulesAllowed: false` in config.

## BID-E10 — `monitor`

**No mutations.** Reads /sops/Bid Strategy Health Checklist.md, walks the user through current vs target, learning state, recent changes. Output is a markdown summary, not a JSON ops file.

---

## Generation rules (all subcommands)

1. Always read fresh `context/account-changelog.md` (≤1h old). Stale → auto-pull via `/account-changelog`.
2. Always read fresh `context/google-ads/data/campaigns-bidding-perf.csv` (≤24h) — if missing or stale, run a scoped pull-all first.
3. Always populate `meta.cascade_clear`, `meta.learning_gate`, `meta.step_cap`, `meta.is_portfolio`. Missing fields → mutate.js refuses.
4. The user must explicitly approve the dry-run before live apply. Never chain `dry-run` → `live` automatically.
5. After live apply, mutate.js writes `tmp/bidding-optimizer/mutations-{ISO}.json` and appends `context/analysis/bidding-changelog.md`. Phase 4 of the optimizer SKILL.md reads these to compose the follow-up reminder.

# Bid Strategy Safety Rails — KW-E08

Detailed safety-rail checklist for campaign bid-strategy target updates. Loaded on demand by `execute-rules.md` when a KW-E08 operation is being generated. This is the long-form rail doc — keep SKILL.md and execute-rules.md thin by pushing all numeric thresholds and edge-case logic here.

Campaign bid-strategy mutations have a larger blast radius than any keyword-level change: a single target update retrains smart bidding across every keyword in the campaign, and a portfolio update cascades across every campaign linked to the portfolio. Every rail in this doc exists because skipping one historically caused a measurable account regression.

---

## Supported bid strategy types

| Type | API field (mutation) | Unit | Raise direction |
|---|---|---|---|
| `TARGET_CPA` | `target_cpa.target_cpa_micros` | micros (1_000_000 = $1) | raise = more expensive conversions allowed |
| `TARGET_ROAS` | `target_roas.target_roas` | decimal (1.5 = 150%) | lower = more volume, less efficient |
| `MAXIMIZE_CONVERSIONS` with target | `maximize_conversions.target_cpa_micros` | micros | raise = more volume |
| `MAXIMIZE_CONVERSION_VALUE` with target | `maximize_conversion_value.target_roas` | decimal | lower = more volume |

## Reading the bid-strategy CSV

`query.js` post-processes every GAQL field ending in `_micros`: it drops the suffix and divides the value by 1,000,000, writing a 2-decimal dollar string to the CSV. The CSV columns therefore **do not match** the API field names in the table above — that table describes the mutation payload, not the CSV.

When reading `context/google-ads/data/campaign-bid-strategy.csv` during Phase 1, use these column names:

| `campaign.bidding_strategy_type` | Current-target CSV column | CSV value | Convert for mutation |
|---|---|---|---|
| `TARGET_CPA` | `campaign.target_cpa.target_cpa` | dollars (e.g. `"53.00"`) | `parseFloat(v) * 1_000_000` → `target_cpa.target_cpa_micros` |
| `MAXIMIZE_CONVERSIONS` | `campaign.maximize_conversions.target_cpa` | dollars | `parseFloat(v) * 1_000_000` → `maximize_conversions.target_cpa_micros` |
| `TARGET_ROAS` | `campaign.target_roas.target_roas` | decimal (e.g. `"1.5"`) | use as-is → `target_roas.target_roas` |
| `MAXIMIZE_CONVERSION_VALUE` | `campaign.maximize_conversion_value.target_roas` | decimal | use as-is → `maximize_conversion_value.target_roas` |

Other relevant columns (also auto-converted by `query.js`):
- `campaign_budget.amount` — daily budget in dollars (not `amount_micros`)
- `metrics.cost` — 30-day spend in dollars (not `cost_micros`)
- `metrics.conversions`, `metrics.conversions_value` — unchanged

**Empty-column caveat:** `query.js` only emits columns that have at least one non-null row. A field queried for every row but empty in every row is silently dropped from the CSV header. This affects:
- `campaign.bidding_strategy` — portfolio resource name. Absent = no campaigns in the pull use a portfolio bid strategy (safe, proceed). Present but empty for a specific row = that campaign is not on a portfolio. Present and non-empty = portfolio — route through Rail 5.
- Strategy-specific target columns — e.g. `campaign.target_cpa.target_cpa` is absent if no campaign in the pull uses `TARGET_CPA`. When iterating, branch on `campaign.bidding_strategy_type` before attempting to read a target column.

**Unsupported** (abort and route to `/strategy-specialist`):
- `MANUAL_CPC` / `ENHANCED_CPC` — keyword-level bids, not campaign-level
- `MAXIMIZE_CLICKS` — no target to update
- `TARGET_IMPRESSION_SHARE` — visibility not conversion strategy
- `TARGET_SPEND` — deprecated, route to upgrade
- Any strategy where `target_cpa_micros` / `target_roas` is unset (pre-target phase of Max Conversions)

---

## Proposed-target computation

### tCPA raise (B1 throttling case)

```
proposed = min(current_target * 1.30, max_profitable_cpa)
```

- `max_profitable_cpa` comes from `context/business.md`. If missing → abort this operation, route user to `/strategy-specialist`.
- If `proposed <= current_target` → skip (no room to raise). This covers the case where `current_target` is already at or above `max_profitable_cpa`.
- Never emit a mutation that would push the target above `max_profitable_cpa`.

### tCPA lower (very rare — over-efficient but stalled on volume)

```
proposed = max(current_target * 0.85, floor_cpa)
```

- Floor CPA is hardcoded at half of current target in v1. Lowers bigger than -15% in one run shock smart bidding.
- Only emit if there is an explicit rationale. B1/T3 triggers never lower — they only raise.

### tROAS analogs

ROAS moves inversely:
- "Raise volume" → lower the ROAS target (e.g. 1.5 → 1.3 = more volume, less efficient)
- "Improve efficiency" → raise the ROAS target
- Same ±30% / ±15% per-run caps apply, but in the inverted direction.

---

## Rail 1 — Max change per run

| Direction | Cap | Reason |
|---|---|---|
| Raise tCPA | ≤ +30% | Smart bidding re-learns quickly to wider ceilings |
| Lower tCPA | ≤ -15% | Tightening shocks bidding, causes volume cliff |
| Lower tROAS (more volume) | ≤ -15% of current | Same bidding shock |
| Raise tROAS (more efficiency) | ≤ +30% of current | Same reasoning as tCPA raise |

Larger movements require multiple runs spaced ≥ 7 days apart so smart bidding has a full learning cycle between each step.

---

## Rail 2 — Learning period lockout

If the campaign entered its current bid strategy or target within the last 7 days → skip with rationale `in learning period — wait N more days`.

**How to check:**
1. Read `context/account-changelog.md`. Look for recent `BIDDING_STRATEGY` or `BIDDING_STRATEGY_TARGET` changes on this campaign.
2. If changelog unavailable or silent, fall back to `campaign.start_date`. If the campaign was created in the last 7 days, treat it as in learning period.
3. If neither source is available, emit the operation but include a warning in `meta.rationale`: "learning period check unavailable — verify manually before applying".

The keyword optimizer does not have a direct GAQL path to "when did the bid strategy last change" because the API does not expose it per campaign. The `change_event` resource has a 14-day window and requires a separate query — out of scope for v1.

---

## Rail 3 — Conversion floor

If the campaign has < 15 conversions in the trailing 30 days → skip and route to `/strategy-specialist`.

Google's own guidance is 15 conversions per month as the minimum for tCPA to work. Below this floor:
- Smart bidding cannot build a reliable model
- Any target raise will inflate CPA without unlocking volume
- The right fix is usually lowering the conversion bar (micro-conversions) or merging the campaign, not tuning the target

The floor is read from `config/ads-context.config.json` → `keywordOptimizer.conversionFloor` (default: 15). Override via config if the account uses a tighter or looser threshold.

---

## Rail 4 — Budget-cap joint constraint

**Definition:** A campaign is budget-capped when daily spend regularly hits ≥ 80% of daily budget.

Compute from the last 30 days of data in `campaign-bid-strategy.csv`:
```
avg_daily_spend = cost_micros / 30 / 1_000_000
budget          = campaign_budget.amount_micros / 1_000_000
spend_ratio     = avg_daily_spend / budget
is_budget_capped = spend_ratio >= 0.80
```

**Behavior:**
- If `is_budget_capped` is **true** → emit the operation anyway, but append to `meta.rationale`: `joint constraint — campaign is budget-capped (${spend_ratio}% of daily budget). Raising the bid ceiling alone will not unlock volume until budget is also raised.`
- If `is_budget_capped` is **false** → emit normally.

Unlike the other rails, this one doesn't block — it informs. The user may still want to raise the target to improve attribution even if volume won't increase. But they need to see the joint constraint upfront.

---

## Rail 5 — Portfolio linkage

`campaign.bidding_strategy` returns the resource name of a portfolio bid strategy if the campaign uses one (otherwise it's empty and the inline `campaign.target_cpa` fields are authoritative).

**Detection:**
```
if (row.campaign.bidding_strategy && row.campaign.bidding_strategy !== '')
    is_portfolio = true
```

**When portfolio detected:**
1. Pull the full list of campaigns sharing this portfolio (one extra GAQL query — `SELECT campaign.id, campaign.name FROM campaign WHERE campaign.bidding_strategy = '{portfolio_resource_name}'`).
2. Populate `meta.portfolio_shared_campaigns` with every campaign name except the target campaign.
3. Set `meta.is_portfolio: true`.
4. mutate.js will require `--confirm-portfolio` before applying any operation with `meta.is_portfolio === true`.
5. The dry-run table displays a prominent PORTFOLIO WARNING banner listing the shared-scope campaigns.

**Portfolio mutation target field:** For portfolio strategies, the actual mutation is on the `bidding_strategy` resource, not the `campaign` resource. **v1 blocks all portfolio mutations entirely** — it aborts with the shared-scope warning and routes the user to `/strategy-specialist` for manual portfolio review. A future v2 will add a `bidding_strategy` entity handler to mutate.js.

---

## Pre-flight checklist (enforce in order, abort on first fail)

1. **Bid strategy type supported?** If not → skip, route to `/strategy-specialist`.
2. **`max_profitable_cpa` available?** (tCPA) or **`min_profitable_roas` available?** (tROAS). If not → skip, route to `/strategy-specialist`.
3. **Fresh campaign state pulled?** Must be from this run's `campaign-bid-strategy.csv`, not cached. If missing → abort Phase 1 entirely.
4. **Proposed target within rail 1 bounds?** If not → clamp to rail bounds and proceed.
5. **Proposed target ≤ max_profitable_cpa?** (or inverse for tROAS). If not → clamp.
6. **Learning period clear?** (rail 2) If not → skip with "wait N days" rationale.
7. **Conversion floor cleared?** (rail 3) If not → skip, route to `/strategy-specialist`.
8. **Portfolio check.** (rail 5) If portfolio → abort with shared-scope route in v1.
9. **Budget-cap computed.** (rail 4) Never blocks — appended to rationale.
10. **Emit operation** with full meta populated.

---

## Rationale message templates

Use these templates for `meta.rationale` so the dry-run table is consistent across campaigns:

**B1 raise (standard):**
```
B1: current tCPA ${current} is ${ratio}x of max profitable CPA ${max}. Raising to ${proposed} (${pct}% change, within per-run cap). Expected to unlock ~${est_volume_pct}% more profitable volume within 7-14 days.
```

**T3 raise:**
```
T3: ${kw_count} OVER_TARGET keywords (${conv_share}% of campaign conversions) are profitable but above current tCPA ${current}. Raising to ${proposed} to capture their volume. Per-keyword performance preserved in audit report.
```

**Budget-capped append:**
```
NOTE: campaign is spending ${spend_pct}% of daily budget — raise budget in parallel to realize the volume uplift from this bid change.
```

**Learning period skip:**
```
SKIP: campaign entered current bid strategy ${N} days ago. Learning period requires 7 days. Re-run after ${M}.
```

**Conversion floor skip:**
```
SKIP: campaign has ${N} conversions in last 30 days (floor: 15). Smart bidding cannot learn at this volume. Route to /strategy-specialist for strategy review.
```

---

## What this rail doc does not cover

- **Bid strategy type changes** (e.g. Manual → tCPA, tCPA → tROAS). Strategy-type changes are strategic, not mechanical — always route to `/strategy-specialist`.
- **Budget mutations.** E08 never modifies `campaign_budget.amount_micros`. That's the budget-optimizer's surface area.
- **Portfolio creation or removal.** Only existing portfolios are detected for the shared-scope warning.
- **Keyword-level bid overrides.** Those are KW-E02 quadrant actions, not E08.
- **Cross-campaign experiments / drafts.** Out of scope — E08 operates on serving campaigns only.

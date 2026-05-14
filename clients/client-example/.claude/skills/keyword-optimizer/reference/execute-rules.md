# Execute Rules — Keyword Optimizer

Decision trees for each execute action. The keyword-optimizer reads the keyword-auditor's audit report and script outputs to build mutation operations.

**Input sources:**
- `context/analysis/keyword-audit.md` — audit findings with action routes
- `context/google-ads/data/keyword-flags.csv` — flagged keywords (villains, zombies, non-converting, etc.)
- `context/google-ads/data/keyword-overlaps.csv` — duplicates, match type conflicts, PMax overlap
- `context/google-ads/data/keyword-tiers.csv` — full tier classification with quadrants
- `config/ads-context.config.json` — thresholds and campaign targets

**Output:** `created/keyword-ops/operations-{YYYY-MM-DD}.json`

---

## Pre-Flight Checks

Phase-level pre-flight (audit freshness, fresh negative pulls, config load) is handled in `SKILL.md` Phase 0. The rules below assume those inputs are already on disk. Two rule-level checks to enforce here:

### 1. Map audit findings to actions
From `context/analysis/keyword-audit.md`, extract all findings with WARN or FAIL verdicts that have optimizer routes. Map each finding to an execute action (KW-E01 through KW-E08, excluding KW-E06 which is deferred).

### 2. Check shared negative keyword list capacity
- 5,000 items per shared list
- 20 shared lists per account
- If capacity is near limits, warn before generating operations that add shared negatives

---

## KW-E01: Pause Non-Converting Keywords

**Trigger:** KW-D07 FAIL — villains with zero conversions

**Criteria (all must be true):**
- `clicks >= minClicksForEval` (default: 100)
- `conversions == 0`
- `cost > nonConvertingSpendMultiplier * target_cpa` (default: 2.0x)

**Data source:** `keyword-flags.csv` where `flag_type = NON_CONVERTING`

**Mutation:**
```json
{
  "type": "update",
  "resource": "ad_group_criterion",
  "resource_name": "customers/{cid}/adGroupCriteria/{ag_id}~{criterion_id}",
  "fields": {
    "status": "PAUSED"
  },
  "meta": {
    "action_id": "KW-E01",
    "category": "pause_non_converting",
    "target": "{keyword_text} [{match_type}]",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "{clicks} clicks, 0 conversions, ${cost} spend ({multiplier}x target CPA ${target})"
  }
}
```

**Safety:** Only pause, never remove. User can re-enable in Google Ads UI.

---

## KW-E02: Apply Decision Matrix Quadrant Actions

**Trigger:** KW-D07 (villains), KW-D08 (low performers)

**Decision tree by quadrant:**

### Q2 Villains (high conversions, poor efficiency)
- **Action:** Guidance only. Do NOT generate a mutation.
- **Output:** Include in dry-run table as "INVESTIGATE" with rationale:
  > "High conversions but poor efficiency. Investigate Quality Score and landing page experience. Routes to QS specialist."

### Q4 Villains (low conversions, poor efficiency)
- **Action:** Pause. Same mutation as KW-E01.
- **Meta:** `action_id=KW-E02`, `category=quadrant_action`

### Low Performers (impressions > 0, clicks == 0)
- If keyword age > 60 days in evaluation period: **Pause**
- If keyword age <= 60 days: **Skip** — still in monitoring window
- **Meta:** `action_id=KW-E02`, `category=quadrant_action`

**Mutation (for pause actions):**
```json
{
  "type": "update",
  "resource": "ad_group_criterion",
  "resource_name": "customers/{cid}/adGroupCriteria/{ag_id}~{criterion_id}",
  "fields": {
    "status": "PAUSED"
  },
  "meta": {
    "action_id": "KW-E02",
    "category": "quadrant_action",
    "target": "{keyword_text} [{match_type}]",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "Q4 villain: {conversions} conv at ${cpa} CPA vs ${target} target"
  }
}
```

---

## KW-E03: Fix Match Type Misalignment

**Trigger:** KW-D02 (broad without smart bidding), KW-D03 (redundancy within ad group)

### D02 Fix: Broad to Phrase Conversion

Match type is **immutable** after creation. Must remove + recreate.

**Step 1 — Remove the broad match keyword:**
```json
{
  "type": "remove",
  "resource": "ad_group_criterion",
  "resource_name": "customers/{cid}/adGroupCriteria/{ag_id}~{criterion_id}",
  "meta": {
    "action_id": "KW-E03",
    "category": "match_type_fix",
    "from_match_type": "BROAD",
    "to_match_type": "PHRASE",
    "target": "{keyword_text} [BROAD] -> will recreate as PHRASE",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "Broad match on Manual CPC campaign — no smart bidding safety net"
  }
}
```

**Step 2 — Create the phrase match keyword:**
```json
{
  "type": "create",
  "resource": "ad_group_criterion",
  "fields": {
    "ad_group": "customers/{cid}/adGroups/{ag_id}",
    "keyword": {
      "text": "{keyword_text}",
      "match_type": "PHRASE"
    },
    "status": "ENABLED",
    "negative": false
  },
  "meta": {
    "action_id": "KW-E03",
    "category": "match_type_fix",
    "from_match_type": "BROAD",
    "to_match_type": "PHRASE",
    "target": "{keyword_text} [PHRASE] (replacement)",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "Replacing broad match with phrase match for Manual CPC campaign"
  }
}
```

**WARNING:** Match type change loses all keyword history (Quality Score, performance stats). The dry-run table must flag this prominently:
> "Match type changes (KW-E03) will lose keyword history. The new keyword starts fresh."

**Requires:** `--allow-remove` flag when running mutate.js.

### D03 Fix: Pause Redundant Match Type

When the same keyword exists in multiple match types within one ad group, pause the one that does not align with the campaign's bidding strategy:

- **Smart bidding campaign** (tCPA, tROAS, Max Conv with target, Max Conv Value with target): Keep BROAD, pause EXACT and PHRASE
- **Manual campaign** (Manual CPC, Max Clicks, Max Conv no target, Target IS): Keep EXACT or PHRASE (prefer EXACT if both exist), pause BROAD

**Mutation:** Same pause format as KW-E01 with `action_id=KW-E03`, `category=match_type_fix`.

---

## KW-E04: Resolve Keyword Duplicates

**Trigger:** KW-D10 (exact duplicates), KW-D13 (similar broad match variants)

**Data source:** `keyword-overlaps.csv` where `flag_type IN (DUPLICATE_KEYWORD)` and keyword-tiers.csv for D13

**Decision logic to pick the winner:**

1. **Higher conversions** — the location with more conversions wins
2. **Lower CPA** (if CPA mode) or **higher ROAS** (if ROAS mode) — if conversions are close
3. **Higher Quality Score** — tiebreaker
4. **More relevant ad group** — if all metrics are tied, Claude judges which ad group is semantically better aligned with the keyword

**Pause the losers:**
```json
{
  "type": "update",
  "resource": "ad_group_criterion",
  "resource_name": "customers/{cid}/adGroupCriteria/{ag_id}~{criterion_id}",
  "fields": {
    "status": "PAUSED"
  },
  "meta": {
    "action_id": "KW-E04",
    "category": "resolve_duplicate",
    "target": "{keyword_text} [{match_type}]",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "Duplicate of keyword in {winner_ad_group}. Winner: {conversions} conv, ${cpa} CPA, QS {qs}. Loser: {conversions} conv, ${cpa} CPA, QS {qs}"
  }
}
```

---

## KW-E05: Resolve Cannibalization (Cross-Negatives)

**Trigger:** KW-D11 FAIL — keywords in different ad groups competing for the same queries

**Action:** Add negative exact match keywords at the ad group level to route traffic to the intended ad group.

**Logic:**
- In ad group A: add negative exact for keyword B's terms (so B's queries go to B's ad group)
- In ad group B: add negative exact for keyword A's terms (so A's queries go to A's ad group)

**Pre-flight validation (critical):**
1. Check existing negatives (`negatives-adgroup-kw.csv`) to avoid duplicates. If the negative already exists, skip it.
2. Verify the negative does not conflict with an existing positive keyword in the same ad group. A negative exact for "crm software" in an ad group that has "crm software" as a positive keyword would block that keyword entirely.

**Scope:** Cross-negatives only. This skill does NOT move keywords between ad groups or create new ad groups. Structural reorganization is deferred to `keyword-restructurer`.

**Mutation:**
```json
{
  "type": "create",
  "resource": "ad_group_criterion",
  "fields": {
    "ad_group": "customers/{cid}/adGroups/{ag_id}",
    "keyword": {
      "text": "{keyword_text}",
      "match_type": "EXACT"
    },
    "status": "ENABLED",
    "negative": true
  },
  "meta": {
    "action_id": "KW-E05",
    "category": "cross_negative",
    "target": "{keyword_text} [EXACT] negative in AG '{ad_group_name}'",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "Route exact queries to AG '{winner_ag}' which has better QS ({winner_qs} vs {loser_qs})"
  }
}
```

---

## KW-E08: Campaign Bid-Strategy Target Review

**Trigger:** KW-B1 FAIL (tCPA throttling — ratio of current tCPA to max profitable CPA < 0.5) OR KW-T3 (OVER_TARGET keywords — profitable by max profitable CPA but above campaign tCPA).

**Scope:** Campaign-level bid strategy **targets only**. This action never changes bid strategy type (TARGET_CPA vs TARGET_ROAS vs Manual) — that is a `/strategy-specialist` decision. It never touches keyword-level bid overrides (those are KW-E02).

**Read `reference/bid-strategy-safety.md` before generating operations.** It holds the full safety-rail checklist (learning period, conversion floor, budget cap, portfolio linkage, max-change math). The rules below cover the trigger→mutation mapping; the safety file covers what must be true before a mutation is emitted.

### Supported bid strategies

| Bid strategy type | Target field | Target unit |
|---|---|---|
| `TARGET_CPA` | `target_cpa.target_cpa_micros` | micros ($) |
| `TARGET_ROAS` | `target_roas.target_roas` | decimal (1.5 = 150%) |
| `MAXIMIZE_CONVERSIONS` (with target) | `maximize_conversions.target_cpa_micros` | micros ($) |
| `MAXIMIZE_CONVERSION_VALUE` (with target) | `maximize_conversion_value.target_roas` | decimal |

Any other bid strategy type (Manual CPC, Enhanced CPC, Maximize Clicks, Target Impression Share, Target Spend) → **abort and route to `/strategy-specialist`**. mutate.js enforces this at the validation layer.

### Evidence requirements (pre-flight per campaign)

1. `context/business.md` must contain `max_profitable_cpa` (for tCPA) or `min_profitable_roas` (for tROAS). If missing → abort the campaign's operation and route to `/strategy-specialist`.
2. Fresh campaign state must be pulled from `reference/gaql/campaign-bid-strategy.gaql` (not cached — bid strategy changes invalidate cached context). Phase 0 in SKILL.md handles this.
3. The proposed target must satisfy: `old_target < new_target <= max_profitable_cpa` (for tCPA raises) or the inverse for tROAS.
4. The campaign must clear all safety rails in `bid-strategy-safety.md`. Any unchecked rail → skip the operation with the rail name as the rationale.

### Decision logic

**For B1 (tCPA throttling):**
- Compute proposed target: `min(current_target * 1.30, max_profitable_cpa)`
- If proposed ≤ current → skip (no room to raise)
- Otherwise emit operation with rationale explaining the throttle ratio

**For T3 (OVER_TARGET keywords):**
- Count the keywords in the campaign flagged as OVER_TARGET by the auditor (profitable by max profitable CPA, above the campaign tCPA)
- If they represent >20% of the campaign's conversions, raise target the same way as B1
- If they represent ≤20%, skip — the leak isn't large enough to justify a campaign-level change
- Per-keyword overrides are not in scope; only the campaign-level target

### Safety rails (enforced per operation)

- **Max raise per run:** ≤ +30% from current target in one pass. Larger changes require multiple runs ≥ 7 days apart.
- **Max lower per run:** ≤ -15%. Drops shock smart bidding more than raises.
- **Learning period:** If the campaign entered its current bid strategy or target within the last 7 days → skip with rationale "in learning period — wait N more days". Check `context/account-changelog.md` (or skip if unavailable and warn).
- **Conversion floor:** If campaign has < 15 conversions in trailing 30 days → skip and route to `/strategy-specialist`. Smart bidding cannot learn effectively below this floor.
- **Budget cap:** If daily spend < 80% of daily budget (budget-capped would be >100%), a target raise alone will not unlock volume. Emit the operation anyway but flag the joint budget+bid constraint in the rationale.
- **Portfolio linkage:** If `campaign.bidding_strategy` resolves to a portfolio bid strategy, set `meta.is_portfolio: true` and populate `meta.portfolio_shared_campaigns` with every campaign linked to that portfolio. mutate.js will then require `--confirm-portfolio` before applying. The dry-run table shows the shared-scope warning.

### Mutation shape

```json
{
  "type": "update",
  "resource": "campaign",
  "resource_name": "customers/{cid}/campaigns/{campaign_id}",
  "fields": {
    "target_cpa": { "target_cpa_micros": 68900000 }
  },
  "meta": {
    "action_id": "KW-E08",
    "category": "bid_strategy_target_raise",
    "target": "{campaign_name}",
    "campaign": "{campaign_name}",
    "ad_group": null,
    "bid_strategy_type": "TARGET_CPA",
    "bid_strategy_field": "target_cpa.target_cpa_micros",
    "old_value": 53000000,
    "new_value": 68900000,
    "is_portfolio": false,
    "portfolio_shared_campaigns": [],
    "conversions_last_30d": 42,
    "rationale": "B1: current tCPA $53.00 is 0.27x of max profitable CPA $200.00. Raising to $68.90 (+30% cap). Expected to unlock ~40% more profitable volume within 7-14 days."
  }
}
```

**Field structure by bid strategy type:**

- `TARGET_CPA`: `fields: { target_cpa: { target_cpa_micros: N } }`
- `TARGET_ROAS`: `fields: { target_roas: { target_roas: 1.5 } }`
- `MAXIMIZE_CONVERSIONS` with target: `fields: { maximize_conversions: { target_cpa_micros: N } }`
- `MAXIMIZE_CONVERSION_VALUE` with target: `fields: { maximize_conversion_value: { target_roas: 1.5 } }`

mutate.js flattens nested keys into the Google Ads API `update_mask` automatically.

### Safety — what this action does NOT do

- Never creates a new campaign
- Never changes the bid strategy type (e.g. Manual → tCPA)
- Never removes a campaign
- Never touches keyword-level bid overrides
- Never raises a target above `max_profitable_cpa` from `business.md`
- Never applies to Manual CPC / Enhanced CPC / Max Clicks / Target Impression Share / Target Spend campaigns

---

## KW-E07: Clean Up Zombie Keywords

**Trigger:** KW-D08 FAIL — keywords with 0 impressions in the full evaluation period

**Data source:** `keyword-flags.csv` where `flag_type = ZOMBIE`

**Exception:** Skip if the keyword was recently created (within the evaluation period). Check `keyword-tiers.csv` for any flags about new keywords, or check the keyword's creation date if available from the structural CSV.

**Mutation:**
```json
{
  "type": "update",
  "resource": "ad_group_criterion",
  "resource_name": "customers/{cid}/adGroupCriteria/{ag_id}~{criterion_id}",
  "fields": {
    "status": "PAUSED"
  },
  "meta": {
    "action_id": "KW-E07",
    "category": "clean_zombie",
    "target": "{keyword_text} [{match_type}]",
    "campaign": "{campaign_name}",
    "ad_group": "{ad_group_name}",
    "rationale": "0 impressions in {period}-day evaluation period. Pausing to reduce clutter."
  }
}
```

---

## Deferred Actions

KW-E06 (keyword restructuring) is out of scope for this skill. The spec lives in `KEYWORD_OPTIMIZER_FUTURE.md` at project root. Restructuring requires new ad groups, RSA creation, and history-losing keyword moves — it will ship as a dedicated `keyword-restructurer` skill. Do not generate E06 operations here.

---

## Operation JSON Format

Each operation in the `created/keyword-ops/operations-{YYYY-MM-DD}.json` file:

```json
{
  "description": "Keyword optimizer changes — {YYYY-MM-DD}",
  "generated_from": "context/analysis/keyword-audit.md",
  "generated_at": "{ISO timestamp}",
  "total_operations": 23,
  "operations": [
    {
      "type": "update|create|remove",
      "resource": "ad_group_criterion",
      "resource_name": "customers/{cid}/adGroupCriteria/{ag_id}~{criterion_id}",
      "fields": { },
      "meta": {
        "action_id": "KW-E01",
        "category": "pause_non_converting",
        "target": "keyword text [MATCH_TYPE]",
        "campaign": "Campaign Name",
        "ad_group": "Ad Group Name",
        "rationale": "142 clicks, 0 conversions, $284 spend (1.4x target)"
      }
    }
  ]
}
```

**Required meta fields for every operation:**
- `action_id` — which execute action generated this (KW-E01 through KW-E08, excluding KW-E06)
- `category` — machine-readable category for grouping in dry-run table
- `target` — human-readable keyword or campaign identifier
- `campaign` — campaign name for context
- `ad_group` — ad group name for context (null for campaign-level ops)
- `rationale` — why this change is being made (shown to user in dry-run)

**Additional meta fields by action:**
- KW-E03: `from_match_type`, `to_match_type`
- KW-E04: winner/loser performance comparison in rationale
- KW-E05: `match_type` (always EXACT for cross-negatives)
- KW-E08: `bid_strategy_type`, `bid_strategy_field`, `old_value`, `new_value`, `is_portfolio`, `portfolio_shared_campaigns` (array), `conversions_last_30d`

---

## Execution Order

mutate.js applies operations in this strict order:

1. **Campaign bid-strategy target updates (KW-E08)** — raise the ceiling before any keyword touches, giving throttled keywords a chance to recover
2. **Creates (negatives)** — cross-negatives must exist before pauses so traffic routing is preserved
3. **Removes** — old match type keywords (KW-E03 swap step 1)
4. **Creates (positive)** — new match type keywords (KW-E03 swap step 2)
5. **Updates (pause)** — pause zombies, villains, duplicates last

This ordering ensures:
- Bid ceilings are raised before any pruning, so smart bidding can react before the keyword set changes
- Traffic has somewhere to go before keywords are paused
- The old keyword is removed before the new one is created (avoids temporary duplicate)
- Pauses happen last so all routing changes are in place

---

## Scoped Execution

Command routing is defined in `SKILL.md`. When scoped, only generate operations for the specified action IDs. Pre-flight checks still run in full regardless of scope.

---

## Dry-Run Flow

1. Generate operations.json from audit findings
2. Run `mutate.js --mode=dry-run` — validates all operations against the API
3. Present the dry-run table to user with full rationale per operation
4. Wait for explicit "yes" approval before proceeding to live mode
5. On approval: run `mutate.js --mode=live`
6. Log changes to `context/analysis/keyword-changelog.md` and `context/memory/{YYYY-MM-DD}.md`

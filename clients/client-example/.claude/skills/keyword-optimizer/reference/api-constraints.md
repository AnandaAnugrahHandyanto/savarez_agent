# API Constraints — Keyword Optimizer

Google Ads API constraints and safety rails for keyword mutation operations. Reference this file when generating operations to ensure all mutations are valid.

---

## Resource Types and Services

| Resource | Service | Create | Update | Remove | Notes |
|----------|---------|--------|--------|--------|-------|
| `ad_group_criterion` (keyword) | AdGroupCriterionService | Yes | status, bid | Yes | Match type is immutable — swap = remove + create |
| `ad_group_criterion` (negative) | AdGroupCriterionService | Yes | -- | Yes | Create/remove only. No status updates on negatives. |
| `campaign_criterion` (negative) | CampaignCriterionService | Yes | -- | Yes | Campaign-level negatives. Create/remove only. |
| `shared_set` (negative KW list) | SharedSetService | Yes | name only | Yes | Do not remove if `reference_count > 0`. |
| `shared_criterion` (list items) | SharedCriterionService | Yes | -- | Yes | Items inside shared negative keyword lists. |
| `campaign_shared_set` (linkage) | CampaignSharedSetService | Yes | -- | Yes | Links a shared set to a campaign. |
| `campaign` (bid strategy target) | CampaignService | **No** | target fields only | **No** | KW-E08 only. Never creates/removes a campaign. Never changes bid strategy type. |

---

## Key Constraints

### Match Type Immutability
- `keyword.match_type` is **IMMUTABLE** after creation
- To change match type: remove the old keyword, create a new one with the desired match type
- The recreated keyword **loses all history** — Quality Score, performance stats, and learning data reset to zero
- Always warn the user about history loss in the dry-run table

### Negative Keyword Limits
- **5,000 negatives per campaign** (campaign_criterion)
- **5,000 negatives per ad group** (ad_group_criterion with negative=true)
- **20 shared negative keyword lists per account**
- **5,000 items per shared negative keyword list**
- Check capacity before generating create operations for negatives

### Validation
- `validate_only: true` works on all mutate operations — used by dry-run mode
- Validation catches field format errors, resource name issues, and constraint violations
- Does NOT catch logical conflicts (e.g., creating a negative that blocks a positive)

### Status Changes
- Valid status values: `ENABLED`, `PAUSED`, `REMOVED`
- This skill restricts to `PAUSED` only — never sets `REMOVED`
- Pausing is reversible; removing is permanent
- mutate.js enforces this constraint at the validation layer

### Bid Strategy Target Updates (KW-E08)
- Only the following field paths may be mutated on a `campaign` resource:
  - `target_cpa.target_cpa_micros`
  - `target_roas.target_roas`
  - `maximize_conversions.target_cpa_micros`
  - `maximize_conversion_value.target_roas`
- Supported bid strategy types (anything else is rejected): `TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSIONS`, `MAXIMIZE_CONVERSION_VALUE`
- Never mutate `campaign.bidding_strategy_type` — strategy-type changes route to `/strategy-specialist`
- Never mutate `campaign.campaign_budget` — budget is out of scope for this skill
- Portfolio bid strategies (where `campaign.bidding_strategy` is set) require `--confirm-portfolio`; v1 routes portfolio operations to `/strategy-specialist` instead of applying them directly
- See `bid-strategy-safety.md` for full safety rails (learning period, conversion floor, budget-cap joint constraint, max-change caps)

---

## Resource Name Formats

### Positive/Negative Keyword (ad group level)
```
customers/{customer_id}/adGroupCriteria/{ad_group_id}~{criterion_id}
```
Used for: pause operations, remove operations (match type swap), and negative keyword creates at ad group level.

### Campaign Negative Keyword
```
customers/{customer_id}/campaignCriteria/{campaign_id}~{criterion_id}
```
Used for: campaign-level negative keyword operations.

### Campaign (bid strategy target updates — KW-E08)
```
customers/{customer_id}/campaigns/{campaign_id}
```
Used for: KW-E08 campaign bid-strategy target updates. Update operations only — never create or remove.

### Shared Set (negative keyword list)
```
customers/{customer_id}/sharedSets/{shared_set_id}
```

### Shared Criterion (item in shared list)
```
customers/{customer_id}/sharedCriteria/{shared_set_id}~{criterion_id}
```

### Ad Group (for create operations)
```
customers/{customer_id}/adGroups/{ad_group_id}
```
Used in `fields.ad_group` when creating new keywords or negatives.

---

## Create Operation Field Requirements

### Positive Keyword
```json
{
  "ad_group": "customers/{cid}/adGroups/{ag_id}",
  "keyword": {
    "text": "keyword text here",
    "match_type": "EXACT|PHRASE|BROAD"
  },
  "status": "ENABLED",
  "negative": false
}
```

### Negative Keyword (ad group level)
```json
{
  "ad_group": "customers/{cid}/adGroups/{ag_id}",
  "keyword": {
    "text": "keyword text here",
    "match_type": "EXACT"
  },
  "status": "ENABLED",
  "negative": true
}
```

### Negative Keyword (campaign level)
```json
{
  "campaign": "customers/{cid}/campaigns/{campaign_id}",
  "keyword": {
    "text": "keyword text here",
    "match_type": "EXACT|PHRASE|BROAD"
  },
  "negative": true
}
```

---

## Safety Rails (enforced by mutate.js)

### Required Flags
| Flag | Behavior |
|------|----------|
| `--mode=dry-run\|live` | **Required.** No default mode — must be explicit. |
| `--customer-id` | **Required.** Target account. |
| `--operations-file` | **Required.** Path to operations JSON. |
| `--login-customer-id` | Optional. MCC account ID if operating under a manager. |
| `--max-ops=N` | Default: 100. Rejects if operation count exceeds limit. |
| `--allow-remove` | **Required** for any `type=remove` operations. Match type swaps always include removes. |
| `--confirm-portfolio` | **Required** for any KW-E08 operation on a portfolio bid strategy (`meta.is_portfolio === true`). Portfolio changes cascade across every campaign sharing the portfolio. |

### Enforcement Rules
1. **No default mode** — script exits with error if `--mode` is missing
2. **Max operations cap** — default 100, override with `--max-ops=N`. Keywords are high-value assets; lower default than placement-optimizer's 200.
3. **Remove guard** — any `type=remove` operation requires `--allow-remove` flag. Without it, script exits with error explaining why.
4. **Status guard** — only `PAUSED` is allowed for status updates (on `ad_group_criterion`). Script exits with error if any operation sets a different status.
5. **Campaign resource guard** — campaign operations must be `type=update`, bid strategy type must be supported, and only the 4 allow-listed target field paths may be mutated. Any violation exits immediately.
6. **Portfolio guard** — any campaign op with `meta.is_portfolio === true` requires `--confirm-portfolio`. Without it, script exits and prints the shared-scope campaign list.
7. **Batch size** — 200 operations per API call (internal to mutate.js). Operations exceeding this are batched automatically.

### Dry-Run Behavior
- Sends all operations with `validate_only: true`
- Reports API validation pass/fail
- Renders a formatted table with all operations grouped by category
- Match type fixes display the "history loss" warning
- User must explicitly approve before live execution

### Live Mode Behavior
- Executes operations in strict order: negatives -> removes -> creates -> pauses
- Logs results per batch
- Writes changelog entry to `context/analysis/keyword-changelog.md`
- Reports summary: applied count, failed count, error details

---

## Operation Ordering

mutate.js sorts operations into this strict execution order:

1. **Campaign bid-strategy target updates (KW-E08)** — raise bid ceilings before touching any keywords
2. **Creates (negatives)** — cross-negatives must exist before pauses to maintain traffic routing
3. **Removes** — old match type keywords (part of E03 swap)
4. **Creates (positive)** — new match type keywords (part of E03 swap)
5. **Updates (pause)** — pause zombies, villains, duplicates last

This ordering is enforced by the `sortOperations()` function in mutate.js. Operations within each group execute in the order they appear in the operations file.

---

## Common Error Scenarios

| Error | Cause | Resolution |
|-------|-------|------------|
| `MUTATE_ERROR_INVALID_RESOURCE_NAME` | Malformed resource name (bad ID format) | Verify customer_id, ad_group_id, criterion_id from source data |
| `DUPLICATE_KEYWORD` | Creating a keyword that already exists in the ad group | Check existing keywords before creating (pre-flight) |
| `NEGATIVE_KEYWORD_ALREADY_EXISTS` | Creating a negative that already exists | Check existing negatives before creating (pre-flight) |
| `QUOTA_ERROR` | Too many mutations in a short window | Reduce batch size or add delay between batches |
| `AUTHORIZATION_ERROR` | Token expired or insufficient permissions | Re-authenticate via config/.env |
| `CRITERION_NOT_FOUND` | Removing a keyword that was already removed | Verify keyword status is not REMOVED before generating remove operation |
| `BIDDING_STRATEGY_NOT_SUPPORTED` | KW-E08 tried to mutate a Manual/ECPC/MaxClicks/TIS campaign | Route to /strategy-specialist — not in scope for keyword-optimizer |
| `INVALID_LEARNING_PERIOD_CHANGE` | Bid target raised beyond per-run cap during learning | Split into multiple runs ≥ 7 days apart |
| `CANNOT_UPDATE_PORTFOLIO_WITHOUT_CONFIRM` | KW-E08 portfolio op run without `--confirm-portfolio` | Review shared-scope warning, re-run with `--confirm-portfolio` |

---

## API Version

All operations target Google Ads API **V23** (current as of this skill's build date). The `google-ads-api` npm package in `scripts/node_modules/` handles version negotiation.
